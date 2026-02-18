# fs_live_streamer.py: Continuous live score streaming from Flashscore LIVE tab.
# Runs in parallel with the main Leo cycle via asyncio.create_task().

"""
Live Score Streamer
Scrapes the Flashscore LIVE tab every 60 seconds using its own browser context.
Saves results to live_scores.csv and upserts to Supabase.
Propagates live/finished status to schedules.csv and predictions.csv.
"""

import asyncio
import csv
import os
from datetime import datetime as dt, timedelta
from playwright.async_api import Playwright

from Data.Access.db_helpers import (
    save_live_score_entry, log_audit_event,
    SCHEDULES_CSV, PREDICTIONS_CSV, LIVE_SCORES_CSV,
    files_and_headers
)
from Data.Access.sync_manager import SyncManager
from Core.Browser.site_helpers import fs_universal_popup_dismissal
from Core.Utils.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT

STREAM_INTERVAL = 60  # seconds
FLASHSCORE_URL = "https://www.flashscore.com/football/"


# ---------------------------------------------------------------------------
# CSV helper: read all rows from a CSV
# ---------------------------------------------------------------------------
def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _write_csv(path, rows, fieldnames):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Status propagation: update schedules + predictions when matches go live/finish
# ---------------------------------------------------------------------------
def _compute_outcome_correct(prediction_str, home_score, away_score):
    """Check if a prediction was correct given the final score."""
    try:
        hs = int(home_score)
        aws = int(away_score)
    except (ValueError, TypeError):
        return ''
    p = (prediction_str or '').lower()
    if 'home win' in p:
        return 'True' if hs > aws else 'False'
    if 'away win' in p:
        return 'True' if aws > hs else 'False'
    if 'draw' in p:
        return 'True' if hs == aws else 'False'
    if 'over 2.5' in p:
        return 'True' if (hs + aws) > 2 else 'False'
    if 'under 2.5' in p:
        return 'True' if (hs + aws) < 3 else 'False'
    if 'btts' in p or 'both teams to score' in p:
        return 'True' if hs > 0 and aws > 0 else 'False'
    return ''


def _propagate_status_updates(live_matches: list):
    """
    Propagate live scores into schedules.csv and predictions.csv.
    1. Mark any matching fixture as 'live' with current score.
    2. Detect fixtures that are past 2.5hrs → mark 'finished' + compute outcome_correct.
    """
    live_ids = {m['fixture_id'] for m in live_matches}
    live_map = {m['fixture_id']: m for m in live_matches}
    now = dt.now()

    # --- Update schedules.csv ---
    sched_headers = files_and_headers.get(SCHEDULES_CSV, [])
    sched_rows = _read_csv(SCHEDULES_CSV)
    sched_changed = False
    for row in sched_rows:
        fid = row.get('fixture_id', '')
        if fid in live_ids:
            lm = live_map[fid]
            if row.get('status', '').lower() != 'live':
                row['status'] = 'live'
                sched_changed = True
            if lm.get('home_score'):
                row['home_score'] = lm['home_score']
                row['away_score'] = lm['away_score']
                sched_changed = True
        elif row.get('status', '').lower() == 'live' and fid not in live_ids:
            # Was live but no longer in LIVE list → check if should be finished
            try:
                match_time_str = f"{row.get('date','2000-01-01')}T{row.get('match_time','00:00')}:00"
                match_start = dt.fromisoformat(match_time_str)
                if now > match_start + timedelta(minutes=150):
                    row['status'] = 'finished'
                    sched_changed = True
            except Exception:
                pass
    sched_updates = []
    if sched_changed:
        _write_csv(SCHEDULES_CSV, sched_rows, sched_headers)
        # Collect only the changed ones for cloud sync (optional, but cleaner)
        sched_updates = [r for r in sched_rows if r.get('fixture_id') in live_ids]

    # --- Update predictions.csv ---
    pred_headers = files_and_headers.get(PREDICTIONS_CSV, [])
    pred_rows = _read_csv(PREDICTIONS_CSV)
    pred_changed = False
    pred_updates = []
    
    for row in pred_rows:
        fid = row.get('fixture_id', '')
        cur_status = row.get('status', row.get('match_status', '')).lower()

        if fid in live_ids:
            lm = live_map[fid]
            row_changed = False
            if cur_status != 'live':
                row['status'] = 'live'
                row_changed = True
            
            new_hs = lm.get('home_score', '')
            new_as = lm.get('away_score', '')
            if row.get('home_score') != new_hs or row.get('away_score') != new_as:
                row['home_score'] = new_hs
                row['away_score'] = new_as
                row['actual_score'] = f"{new_hs}-{new_as}"
                row_changed = True
            
            if row_changed:
                pred_changed = True
                pred_updates.append(row)
        elif cur_status == 'live' and fid not in live_ids:
            try:
                date_val = row.get('date', '2000-01-01')
                time_val = row.get('match_time', '00:00')
                match_start = dt.fromisoformat(f"{date_val}T{time_val}:00")
                if now > match_start + timedelta(minutes=150):
                    row['status'] = 'finished'
                    # Compute outcome_correct
                    oc = _compute_outcome_correct(
                        row.get('prediction', ''),
                        row.get('home_score', ''),
                        row.get('away_score', '')
                    )
                    if oc:
                        row['outcome_correct'] = oc
                    pred_changed = True
                    pred_updates.append(row)
            except Exception:
                pass
    if pred_changed:
        _write_csv(PREDICTIONS_CSV, pred_rows, pred_headers)
        
    return sched_updates, pred_updates


# ---------------------------------------------------------------------------
# Flashscore LIVE tab extraction
# ---------------------------------------------------------------------------
async def _extract_live_matches(page) -> list:
    """
    Extracts all live matches from the currently visible LIVE tab.
    Uses the actual Flashscore DOM structure with headerLeague__wrapper for
    league grouping and event__match--live for match rows.
    """
    matches = await page.evaluate(r"""() => {
        const matches = [];
        // All elements live inside div.sportName.soccer (or the body if absent)
        const container = document.querySelector('.sportName.soccer') || document.body;
        if (!container) return [];

        // Collect all league headers and match rows in DOM order
        const allElements = container.querySelectorAll(
            '.headerLeague__wrapper, .event__match--live'
        );

        let currentRegion = '';
        let currentLeague = '';

        allElements.forEach((el) => {
            // League header: div.headerLeague__wrapper
            if (el.classList.contains('headerLeague__wrapper')) {
                const catEl = el.querySelector('.headerLeague__category-text');
                const titleEl = el.querySelector('.headerLeague__title-text');
                currentRegion = catEl ? catEl.innerText.trim() : '';
                currentLeague = titleEl ? titleEl.innerText.trim() : '';
                return;
            }

            // Live match row: div.event__match--live
            if (el.classList.contains('event__match--live')) {
                const rowId = el.getAttribute('id');
                const cleanId = rowId ? rowId.replace('g_1_', '') : null;
                if (!cleanId) return;

                // Team names via wcl-name within participant containers
                const homeNameEl = el.querySelector('.event__homeParticipant .wcl-name_jjfMf');
                const awayNameEl = el.querySelector('.event__awayParticipant .wcl-name_jjfMf');
                // Scores via data-testid="wcl-matchRowScore"
                const homeScoreEl = el.querySelector('span.event__score--home');
                const awayScoreEl = el.querySelector('span.event__score--away');
                // Match minute from event__stage--block
                const stageEl = el.querySelector('.event__stage--block');
                // Detail link
                const linkEl = el.querySelector('a.eventRowLink');

                if (homeNameEl && awayNameEl) {
                    // Clean minute text — strip blinking character
                    let minute = stageEl ? stageEl.innerText.trim().replace(/\s+/g, '') : '';

                    let status = 'live';
                    const minuteLower = minute.toLowerCase();
                    if (minuteLower.includes('half')) status = 'halftime';
                    else if (minuteLower.includes('break')) status = 'break';
                    else if (minuteLower.includes('pen')) status = 'penalties';
                    else if (minuteLower.includes('et')) status = 'extra_time';

                    const regionLeague = currentRegion
                        ? currentRegion + ' - ' + currentLeague
                        : currentLeague || 'Unknown';

                    matches.push({
                        fixture_id: cleanId,
                        home_team: homeNameEl.innerText.trim(),
                        away_team: awayNameEl.innerText.trim(),
                        home_score: homeScoreEl ? homeScoreEl.innerText.trim() : '0',
                        away_score: awayScoreEl ? awayScoreEl.innerText.trim() : '0',
                        minute: minute,
                        status: status,
                        region_league: regionLeague,
                        match_link: linkEl ? linkEl.getAttribute('href') : '',
                        timestamp: new Date().toISOString()
                    });
                }
            }
        });
        return matches;
    }""")
    return matches or []


async def _click_live_tab(page) -> bool:
    """Clicks the LIVE tab on the Flashscore football page using the exact
    data-analytics-alias attribute from knowledge.json."""
    try:
        tab = page.locator('.filters__tab[data-analytics-alias="live"]')
        if await tab.count() > 0:
            await tab.first.click()
            await asyncio.sleep(2)
            return True
    except Exception:
        pass

    # Fallback: text-based click
    try:
        await page.get_by_text("LIVE", exact=False).first.click()
        await asyncio.sleep(2)
        return True
    except Exception:
        return False


async def live_score_streamer(playwright: Playwright):
    """
    Main streaming loop. Runs independently in its own browser context.
    Scrapes the LIVE tab every 60 seconds and saves results.
    Never crashes — errors are logged and retried.
    """
    print("\n   [Streamer] 🔴 Live Score Streamer starting...")
    log_audit_event("STREAMER_START", "Live score streamer initialized.")

    browser = None
    try:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            timezone_id="Africa/Lagos"
        )
        page = await context.new_page()

        # Initial navigation
        print("   [Streamer] Navigating to Flashscore...")
        await page.goto(FLASHSCORE_URL, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await fs_universal_popup_dismissal(page, "fs_home_page")

        # Click LIVE tab
        if not await _click_live_tab(page):
            print("   [Streamer] ⚠ Could not find LIVE tab. Will retry on next cycle.")

        sync = SyncManager()
        cycle = 0

        while True:
            cycle += 1
            try:
                # Refresh the page periodically (every 10 cycles = ~10 min)
                if cycle % 10 == 0:
                    await page.reload(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                    await asyncio.sleep(3)
                    await fs_universal_popup_dismissal(page, "fs_home_page")
                    await _click_live_tab(page)

                # Extract live matches
                live_matches = await _extract_live_matches(page)
                now = dt.now().strftime("%H:%M:%S")

                if live_matches:
                    print(f"   [Streamer] {now} — {len(live_matches)} live matches found (cycle {cycle})")

                    # Save each match locally
                    for m in live_matches:
                        save_live_score_entry(m)

                    # Propagate status to schedules + predictions
                    sched_upd, pred_upd = _propagate_status_updates(live_matches)

                    # Sync everything to Supabase
                    if sync.supabase:
                        try:
                            # 1. Push raw live scores
                            await sync.batch_upsert('live_scores', live_matches)
                            # 2. Push modified predictions (for Realtime listeners)
                            if pred_upd:
                                await sync.batch_upsert('predictions', pred_upd)
                            # 3. Push modified schedules
                            if sched_upd:
                                await sync.batch_upsert('schedules', sched_upd)
                        except Exception as e:
                            print(f"   [Streamer] Cloud sync error: {e}")
                else:
                    # Even with no live matches, check for matches that should be finished
                    sched_upd, pred_upd = _propagate_status_updates([])
                    
                    if sync.supabase and (pred_upd or sched_upd):
                        try:
                            if pred_upd:
                                await sync.batch_upsert('predictions', pred_upd)
                            if sched_upd:
                                await sync.batch_upsert('schedules', sched_upd)
                        except Exception as e:
                            print(f"   [Streamer] Cloud sync error (empty live): {e}")

                    if cycle % 5 == 1:  # Log "no matches" every 5 cycles to reduce noise
                        print(f"   [Streamer] {now} — No live matches (cycle {cycle})")

            except Exception as e:
                print(f"   [Streamer] ⚠ Extraction error (cycle {cycle}): {e}")
                # Try to recover by reloading
                try:
                    await page.goto(FLASHSCORE_URL, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    await fs_universal_popup_dismissal(page, "fs_home_page")
                    await _click_live_tab(page)
                except Exception:
                    pass

            await asyncio.sleep(STREAM_INTERVAL)

    except asyncio.CancelledError:
        print("   [Streamer] Streamer cancelled.")
    except Exception as e:
        print(f"   [Streamer] Fatal error: {e}")
        log_audit_event("STREAMER_ERROR", f"Fatal: {e}", status="failed")
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        print("   [Streamer] 🔴 Streamer stopped.")
