# fs_live_streamer.py: Continuous live score streaming from Flashscore ALL tab.
# Runs in parallel with the main Leo cycle via asyncio.create_task().
# v3: Uses the ALL tab as single source of truth for live, finished, postponed,
#     cancelled, FRO statuses. 15s refresh. 2.5hr fallback deprecated (last-resort).

"""
Live Score Streamer v3
Scrapes the Flashscore ALL tab every 15 seconds using its own browser context.
Extracts live, finished, postponed, cancelled, and FRO match statuses.
Saves results to live_scores.csv and upserts to Supabase.
Propagates status to schedules.csv and predictions.csv.
Purges matches no longer live from live_scores.csv and Supabase.
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

STREAM_INTERVAL = 15  # seconds (was 60 in v2)
FLASHSCORE_URL = "https://www.flashscore.com/football/"
_STREAMER_HEARTBEAT_FILE = os.path.join(os.path.dirname(LIVE_SCORES_CSV), '.streamer_heartbeat')


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


def _is_streamer_alive() -> bool:
    """Check if streamer heartbeat file is recent (<30 min). If not, 2.5hr fallback is allowed."""
    try:
        if os.path.exists(_STREAMER_HEARTBEAT_FILE):
            mtime = dt.fromtimestamp(os.path.getmtime(_STREAMER_HEARTBEAT_FILE))
            return (dt.now() - mtime) < timedelta(minutes=30)
    except Exception:
        pass
    return False


def _touch_heartbeat():
    """Update heartbeat file to signal streamer is alive."""
    try:
        with open(_STREAMER_HEARTBEAT_FILE, 'w') as f:
            f.write(dt.now().isoformat())
    except Exception:
        pass


def _propagate_status_updates(live_matches: list, resolved_matches: list = None):
    """
    Propagate live scores and resolved results into schedules.csv and predictions.csv.
    1. Mark matching fixtures as 'live' with current score.
    2. Mark resolved matches with their terminal status (finished/cancelled/postponed/fro).
    3. For cancelled/postponed/fro: clear scores (show 'vs' in UI).
    4. 2.5hr fallback ONLY if streamer has been down >30 min (last-resort).
    """
    resolved_matches = resolved_matches or []
    live_ids = {m['fixture_id'] for m in live_matches}
    live_map = {m['fixture_id']: m for m in live_matches}
    resolved_ids = {m['fixture_id'] for m in resolved_matches}
    resolved_map = {m['fixture_id']: m for m in resolved_matches}
    now = dt.now()
    streamer_alive = _is_streamer_alive()

    # Statuses that should NOT show scores
    NO_SCORE_STATUSES = {'cancelled', 'postponed', 'fro', 'abandoned'}

    # --- Update schedules.csv ---
    sched_headers = files_and_headers.get(SCHEDULES_CSV, [])
    sched_rows = _read_csv(SCHEDULES_CSV)
    sched_changed = False
    for row in sched_rows:
        fid = row.get('fixture_id', '')

        # Live match
        if fid in live_ids:
            lm = live_map[fid]
            if row.get('status', '').lower() != 'live':
                row['status'] = 'live'
                sched_changed = True
            if lm.get('home_score'):
                row['home_score'] = lm['home_score']
                row['away_score'] = lm['away_score']
                sched_changed = True
            if lm.get('minute'):
                row['live_minute'] = lm['minute']
                sched_changed = True

        # Resolved match (from ALL tab — finished/cancelled/postponed/fro)
        elif fid in resolved_ids:
            rm = resolved_map[fid]
            terminal_status = rm.get('status', 'finished')
            if row.get('status', '').lower() != terminal_status:
                row['status'] = terminal_status
                # For cancelled/postponed/fro: clear scores
                if terminal_status in NO_SCORE_STATUSES:
                    row['home_score'] = ''
                    row['away_score'] = ''
                else:
                    row['home_score'] = rm.get('home_score', row.get('home_score', ''))
                    row['away_score'] = rm.get('away_score', row.get('away_score', ''))
                if rm.get('stage_detail'):
                    row['stage_detail'] = rm['stage_detail']
                sched_changed = True

        # LAST-RESORT: Was live but gone — only if streamer has been down >30 min
        elif row.get('status', '').lower() == 'live' and fid not in live_ids and not streamer_alive:
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
        sched_updates = [r for r in sched_rows if r.get('fixture_id') in (live_ids | finished_ids)]

    # --- Update predictions.csv ---
    pred_headers = files_and_headers.get(PREDICTIONS_CSV, [])
    pred_rows = _read_csv(PREDICTIONS_CSV)
    pred_changed = False
    pred_updates = []
    
    for row in pred_rows:
        fid = row.get('fixture_id', '')
        cur_status = row.get('status', row.get('match_status', '')).lower()

        # Live match
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

        # Resolved match (from ALL tab)
        elif fid in resolved_ids:
            rm = resolved_map[fid]
            terminal_status = rm.get('status', 'finished')
            if cur_status != terminal_status:
                row['status'] = terminal_status
                if terminal_status in NO_SCORE_STATUSES:
                    row['home_score'] = ''
                    row['away_score'] = ''
                    row['actual_score'] = ''
                else:
                    row['home_score'] = rm.get('home_score', row.get('home_score', ''))
                    row['away_score'] = rm.get('away_score', row.get('away_score', ''))
                    row['actual_score'] = f"{rm.get('home_score', '')}-{rm.get('away_score', '')}"
                if rm.get('stage_detail'):
                    row['stage_detail'] = rm['stage_detail']
                # Compute outcome_correct only for truly finished matches
                if terminal_status not in NO_SCORE_STATUSES:
                    oc = _compute_outcome_correct(
                        row.get('prediction', ''),
                        row.get('home_score', ''),
                        row.get('away_score', '')
                    )
                    if oc:
                        row['outcome_correct'] = oc
                pred_changed = True
                pred_updates.append(row)

        # LAST-RESORT: Was live but gone — only if streamer down >30 min
        elif cur_status == 'live' and fid not in live_ids and not streamer_alive:
            try:
                date_val = row.get('date', '2000-01-01')
                time_val = row.get('match_time', '00:00')
                match_start = dt.fromisoformat(f"{date_val}T{time_val}:00")
                if now > match_start + timedelta(minutes=150):
                    row['status'] = 'finished'
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
# Purge stale live_scores: remove matches no longer in the LIVE tab
# ---------------------------------------------------------------------------
def _purge_stale_live_scores(current_live_ids: set):
    """
    Remove any fixture from live_scores.csv that is NOT in the current LIVE set.
    Returns the set of stale fixture_ids that were removed.
    """
    live_headers = files_and_headers.get(LIVE_SCORES_CSV, [])
    existing_rows = _read_csv(LIVE_SCORES_CSV)
    if not existing_rows:
        return set()
    
    existing_ids = {r.get('fixture_id', '') for r in existing_rows}
    stale_ids = existing_ids - current_live_ids
    
    if stale_ids:
        kept_rows = [r for r in existing_rows if r.get('fixture_id', '') not in stale_ids]
        _write_csv(LIVE_SCORES_CSV, kept_rows, live_headers)
    
    return stale_ids


# ---------------------------------------------------------------------------
# JS: Expand all collapsed league headers
# ---------------------------------------------------------------------------
EXPAND_COLLAPSED_JS = """() => {
    const buttons = document.querySelectorAll('.wcl-accordion_7Fi80');
    let clicked = 0;
    buttons.forEach(btn => {
        const parent = btn.closest('.wcl-trigger_CGiIV');
        if (parent && parent.getAttribute('data-state') === 'delayed-open') {
            btn.click();
            clicked++;
        }
    });
    return clicked;
}"""


# ---------------------------------------------------------------------------
# Flashscore LIVE tab extraction
# ---------------------------------------------------------------------------
async def _extract_live_matches(page) -> list:
    """
    Extracts all live matches from the currently visible LIVE tab.
    Expands collapsed league headers first.
    """
    # Expand collapsed headers
    try:
        expanded = await page.evaluate(EXPAND_COLLAPSED_JS)
        if expanded:
            print(f"   [Streamer] Expanded {expanded} collapsed league headers (LIVE)")
            await asyncio.sleep(1)
    except Exception:
        pass

    matches = await page.evaluate(r"""() => {
        const matches = [];
        const container = document.querySelector('.sportName.soccer') || document.body;
        if (!container) return [];

        const allElements = container.querySelectorAll(
            '.headerLeague__wrapper, .event__match--live'
        );

        let currentRegion = '';
        let currentLeague = '';

        allElements.forEach((el) => {
            if (el.classList.contains('headerLeague__wrapper')) {
                const catEl = el.querySelector('.headerLeague__category-text');
                const titleEl = el.querySelector('.headerLeague__title-text');
                currentRegion = catEl ? catEl.innerText.trim() : '';
                currentLeague = titleEl ? titleEl.innerText.trim() : '';
                return;
            }

            if (el.classList.contains('event__match--live')) {
                const rowId = el.getAttribute('id');
                const cleanId = rowId ? rowId.replace('g_1_', '') : null;
                if (!cleanId) return;

                const homeNameEl = el.querySelector('.event__homeParticipant .wcl-name_jjfMf');
                const awayNameEl = el.querySelector('.event__awayParticipant .wcl-name_jjfMf');
                const homeScoreEl = el.querySelector('span.event__score--home');
                const awayScoreEl = el.querySelector('span.event__score--away');
                const stageEl = el.querySelector('.event__stage--block');
                const linkEl = el.querySelector('a.eventRowLink');

                if (homeNameEl && awayNameEl) {
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


# ---------------------------------------------------------------------------
# Flashscore ALL tab extraction (replaces FINISHED tab in v3)
# ---------------------------------------------------------------------------
async def _extract_all_matches(page) -> list:
    """
    Extracts ALL matches from the ALL tab — the single source of truth.
    Returns a list of dicts with 'category' field:
      - 'live': currently playing (has live minute)
      - 'finished': completed normally (FT, Pen, AET, WO)
      - 'cancelled': cancelled/abandoned
      - 'postponed': postponed
      - 'fro': frozen/suspended
      - 'scheduled': upcoming (has time, no score)
    """
    # Expand collapsed headers
    try:
        expanded = await page.evaluate(EXPAND_COLLAPSED_JS)
        if expanded:
            print(f"   [Streamer] Expanded {expanded} collapsed league headers (ALL)")
            await asyncio.sleep(1)
    except Exception:
        pass

    matches = await page.evaluate(r"""() => {
        const matches = [];
        const container = document.querySelector('.sportName.soccer') || document.body;
        if (!container) return [];

        const allElements = container.querySelectorAll(
            '.headerLeague__wrapper, .event__match'
        );

        let currentRegion = '';
        let currentLeague = '';

        allElements.forEach((el) => {
            if (el.classList.contains('headerLeague__wrapper')) {
                const catEl = el.querySelector('.headerLeague__category-text');
                const titleEl = el.querySelector('.headerLeague__title-text');
                currentRegion = catEl ? catEl.innerText.trim() : '';
                currentLeague = titleEl ? titleEl.innerText.trim() : '';
                return;
            }

            const rowId = el.getAttribute('id');
            const cleanId = rowId ? rowId.replace('g_1_', '') : null;
            if (!cleanId) return;

            const homeNameEl = el.querySelector('.event__homeParticipant .wcl-name_jjfMf');
            const awayNameEl = el.querySelector('.event__awayParticipant .wcl-name_jjfMf');
            if (!homeNameEl || !awayNameEl) return;

            const homeScoreEl = el.querySelector('span.event__score--home');
            const awayScoreEl = el.querySelector('span.event__score--away');
            const stageEl = el.querySelector('.event__stage--block');
            const timeEl = el.querySelector('.event__time');
            const linkEl = el.querySelector('a.eventRowLink');

            const isLive = el.classList.contains('event__match--live');
            const stageText = stageEl ? stageEl.innerText.trim() : '';
            const stageLower = stageText.toLowerCase();
            const rawTime = timeEl ? timeEl.innerText.trim() : '';

            let status = 'scheduled';
            let stageDetail = '';
            let minute = '';
            let homeScore = homeScoreEl ? homeScoreEl.innerText.trim() : '';
            let awayScore = awayScoreEl ? awayScoreEl.innerText.trim() : '';

            if (isLive) {
                status = 'live';
                minute = stageText.replace(/\s+/g, '');
                const minLower = minute.toLowerCase();
                if (minLower.includes('half')) status = 'halftime';
                else if (minLower.includes('break')) status = 'break';
                else if (minLower.includes('pen')) { status = 'penalties'; stageDetail = 'Pen'; }
                else if (minLower.includes('et')) { status = 'extra_time'; stageDetail = 'ET'; }
            } else if (stageLower.includes('postp') || stageLower.includes('pp')) {
                status = 'postponed'; stageDetail = 'Postp';
                homeScore = ''; awayScore = '';
            } else if (stageLower.includes('canc')) {
                status = 'cancelled'; stageDetail = 'Canc';
                homeScore = ''; awayScore = '';
            } else if (stageLower.includes('abn') || stageLower.includes('abd')) {
                status = 'cancelled'; stageDetail = 'Abn';
                homeScore = ''; awayScore = '';
            } else if (stageLower.includes('fro') || stageLower.includes('susp')) {
                status = 'fro'; stageDetail = 'FRO';
                homeScore = ''; awayScore = '';
            } else if (homeScoreEl && awayScoreEl) {
                const scoreState = homeScoreEl.getAttribute('data-state');
                if (scoreState === 'final' || stageLower.includes('fin') || stageLower === '') {
                    status = 'finished';
                    if (stageLower.includes('pen')) stageDetail = 'Pen';
                    else if (stageLower.includes('aet') || stageLower.includes('et')) stageDetail = 'AET';
                    else if (stageLower.includes('wo') || stageLower.includes('w.o')) stageDetail = 'WO';
                }
            }

            const regionLeague = currentRegion
                ? currentRegion + ' - ' + currentLeague
                : currentLeague || 'Unknown';

            matches.push({
                fixture_id: cleanId,
                home_team: homeNameEl.innerText.trim(),
                away_team: awayNameEl.innerText.trim(),
                home_score: homeScore,
                away_score: awayScore,
                minute: minute,
                status: status,
                stage_detail: stageDetail,
                region_league: regionLeague,
                match_link: linkEl ? linkEl.getAttribute('href') : '',
                match_time: rawTime,
                timestamp: new Date().toISOString()
            });
        });
        return matches;
    }""")
    return matches or []


# ---------------------------------------------------------------------------
# Tab clicking helpers
# ---------------------------------------------------------------------------
async def _click_all_tab(page) -> bool:
    """Clicks the ALL tab on the Flashscore football page (default/first tab)."""
    try:
        tab = page.locator('.filters__tab[data-analytics-alias="summary"]')
        if await tab.count() > 0:
            await tab.first.click()
            await asyncio.sleep(1.5)
            return True
    except Exception:
        pass
    try:
        # Fallback: click the first tab (ALL is always first)
        tab = page.locator('.filters__tab').first
        if await tab.count() > 0:
            await tab.click()
            await asyncio.sleep(1.5)
            return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main streaming loop
# ---------------------------------------------------------------------------
async def live_score_streamer(playwright: Playwright):
    """
    Main streaming loop v3. Runs independently in its own browser context.
    Scrapes the ALL tab every 15 seconds as single source of truth.
    Separates live, finished, cancelled, postponed, FRO matches.
    Never crashes — errors are logged and retried.
    """
    print("\n   [Streamer] 🔴 Live Score Streamer v3 starting (ALL tab, 15s)...")
    log_audit_event("STREAMER_START", "Live score streamer v3 initialized (ALL tab, 15s).")

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

        # Ensure ALL tab is active (default, but be explicit)
        await _click_all_tab(page)

        sync = SyncManager()
        cycle = 0

        while True:
            cycle += 1
            _touch_heartbeat()
            try:
                # Refresh the page periodically (every 40 cycles ≈ 10 min at 15s)
                if cycle % 40 == 0:
                    await page.reload(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                    await asyncio.sleep(3)
                    await fs_universal_popup_dismissal(page, "fs_home_page")
                    await _click_all_tab(page)

                # ── SINGLE PHASE: ALL TAB ──
                all_matches = await _extract_all_matches(page)
                now = dt.now().strftime("%H:%M:%S")

                # Separate by category
                LIVE_STATUSES = {'live', 'halftime', 'break', 'penalties', 'extra_time'}
                RESOLVED_STATUSES = {'finished', 'cancelled', 'postponed', 'fro', 'abandoned'}

                live_matches = [m for m in all_matches if m.get('status') in LIVE_STATUSES]
                resolved_matches = [m for m in all_matches if m.get('status') in RESOLVED_STATUSES]
                current_live_ids = {m['fixture_id'] for m in live_matches}

                # ── PURGE STALE LIVE SCORES ──
                stale_ids = _purge_stale_live_scores(current_live_ids)
                if stale_ids:
                    print(f"   [Streamer] 🧹 Purged {len(stale_ids)} stale entries from live_scores")

                # ── PROCESS & SYNC ──
                if live_matches or resolved_matches:
                    parts = []
                    if live_matches:
                        parts.append(f"{len(live_matches)} live")
                    if resolved_matches:
                        fin_count = sum(1 for m in resolved_matches if m['status'] == 'finished')
                        other_count = len(resolved_matches) - fin_count
                        if fin_count:
                            parts.append(f"{fin_count} finished")
                        if other_count:
                            parts.append(f"{other_count} cancelled/postp/fro")
                    total = len(all_matches)
                    parts.append(f"{total} total")
                    print(f"   [Streamer] {now} — {', '.join(parts)} (cycle {cycle})")

                    # Save live matches locally
                    for m in live_matches:
                        save_live_score_entry(m)

                    # Propagate status to schedules + predictions
                    sched_upd, pred_upd = _propagate_status_updates(live_matches, resolved_matches)

                    # Sync everything to Supabase
                    if sync.supabase:
                        try:
                            if live_matches:
                                await sync.batch_upsert('live_scores', live_matches)
                            if stale_ids:
                                try:
                                    sync.supabase.table('live_scores').delete().in_(
                                        'fixture_id', list(stale_ids)
                                    ).execute()
                                except Exception as e:
                                    print(f"   [Streamer] Stale purge sync error: {e}")
                            if pred_upd:
                                await sync.batch_upsert('predictions', pred_upd)
                            if sched_upd:
                                await sync.batch_upsert('schedules', sched_upd)
                        except Exception as e:
                            print(f"   [Streamer] Cloud sync error: {e}")
                else:
                    # Even with no data, check last-resort transitions
                    sched_upd, pred_upd = _propagate_status_updates([], [])

                    if sync.supabase and (pred_upd or sched_upd):
                        try:
                            if pred_upd:
                                await sync.batch_upsert('predictions', pred_upd)
                            if sched_upd:
                                await sync.batch_upsert('schedules', sched_upd)
                        except Exception as e:
                            print(f"   [Streamer] Cloud sync error (empty): {e}")

                    if stale_ids and sync.supabase:
                        try:
                            sync.supabase.table('live_scores').delete().in_(
                                'fixture_id', list(stale_ids)
                            ).execute()
                        except Exception:
                            pass

                    if cycle % 20 == 1:  # Less frequent logging at 15s intervals
                        print(f"   [Streamer] {now} — No matches (cycle {cycle})")

            except Exception as e:
                print(f"   [Streamer] ⚠ Extraction error (cycle {cycle}): {e}")
                try:
                    await page.goto(FLASHSCORE_URL, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    await fs_universal_popup_dismissal(page, "fs_home_page")
                    await _click_all_tab(page)
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
