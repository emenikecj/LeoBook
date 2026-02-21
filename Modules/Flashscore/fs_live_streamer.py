# fs_live_streamer.py: fs_live_streamer.py: Continuous live score streaming from Flashscore ALL tab.
# Part of LeoBook Modules — Flashscore
#
# Functions: _read_csv(), _write_csv(), _compute_outcome_correct(), _is_streamer_alive(), _touch_heartbeat(), _propagate_status_updates(), _purge_stale_live_scores(), _extract_all_matches() (+2 more)

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
from Core.Intelligence.selector_manager import SelectorManager

STREAM_INTERVAL = 60  # seconds
FLASHSCORE_URL = "https://www.flashscore.com/football/"
_STREAMER_HEARTBEAT_FILE = os.path.join(os.path.dirname(LIVE_SCORES_CSV), '.streamer_heartbeat')

# JS to expand the "Show More" dropdown found in mobile/collapsed views
EXPAND_DROPDOWN_JS = """
(selector) => {
    const btn = document.querySelector(selector);
    if (btn) {
        btn.click();
        return true;
    }
    return false;
}
"""

# ---------------------------------------------------------------------------
# CSV helper: read all rows from a CSV (unchanged)
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
    """
    resolved_matches = resolved_matches or []
    live_ids = {m['fixture_id'] for m in live_matches}
    live_map = {m['fixture_id']: m for m in live_matches}
    resolved_ids = {m['fixture_id'] for m in resolved_matches}
    resolved_map = {m['fixture_id']: m for m in resolved_matches}
    now = dt.now()
    streamer_alive = _is_streamer_alive()

    NO_SCORE_STATUSES = {'cancelled', 'postponed', 'fro', 'abandoned'}

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
            if lm.get('minute'):
                row['live_minute'] = lm['minute']
                sched_changed = True

        elif fid in resolved_ids:
            rm = resolved_map[fid]
            terminal_status = rm.get('status', 'finished')
            if row.get('status', '').lower() != terminal_status:
                row['status'] = terminal_status
                if terminal_status in NO_SCORE_STATUSES:
                    row['home_score'] = ''
                    row['away_score'] = ''
                else:
                    row['home_score'] = rm.get('home_score', row.get('home_score', ''))
                    row['away_score'] = rm.get('away_score', row.get('away_score', ''))
                if rm.get('stage_detail'):
                    row['stage_detail'] = rm['stage_detail']
                sched_changed = True

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
        sched_updates = [r for r in sched_rows if r.get('fixture_id') in (live_ids | resolved_ids)]

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
# Flashscore ALL tab extraction – only 4 selector keys updated
# ---------------------------------------------------------------------------
async def _extract_all_matches(page) -> list:
    """
    Extracts ALL matches from the ALL tab — the single source of truth.
    """
    selectors = SelectorManager.get_all_selectors_for_context("fs_home_page")

    result = await page.evaluate(r"""(sel) => {
        const matches = [];
        const debug = {total_elements: 0, headers: 0, no_id: 0, no_teams: 0, matched: 0};
        const combinedSel = sel.league_header_wrapper + ', ' + sel.match_rows;
        let container = document.querySelector(sel.sport_container_soccer);
        let allElements = container ? container.querySelectorAll(combinedSel) : [];
        // Mobile layout: .sportName.soccer only wraps a small subset — fall back to full DOM
        if (allElements.length < 50) {
            container = document.body;
            allElements = container.querySelectorAll(combinedSel);
            debug.fallback = true;
        }
        debug.total_elements = allElements.length;

        let currentRegion = '';
        let currentLeague = '';

        allElements.forEach((el) => {
            if (el.matches(sel.league_header_wrapper)) {
                debug.headers++;
                const catEl = el.querySelector(sel.league_country_text);
                const titleEl = el.querySelector(sel.league_title_text);
                currentRegion = catEl ? catEl.innerText.trim() : '';
                currentLeague = titleEl ? titleEl.innerText.trim() : '';
                return;
            }

            const rowId = el.getAttribute('id');
            const cleanId = rowId ? rowId.replace(sel.match_id_prefix, '') : null;
            if (!cleanId) { debug.no_id++; return; }

            const homeNameEl = el.querySelector(sel.match_row_home_team_name);
            const awayNameEl = el.querySelector(sel.match_row_away_team_name);
            if (!homeNameEl || !awayNameEl) {
                debug.no_teams++;
                return;
            }

            debug.matched++;

            const homeScoreEl = el.querySelector(sel.live_match_home_score);
            const awayScoreEl = el.querySelector(sel.live_match_away_score);
            const stageEl = el.querySelector(sel.live_match_stage_block);
            const timeEl = el.querySelector(sel.match_row_time);
            const linkEl = el.querySelector(sel.event_row_link);

            const isLive = el.classList.contains(sel.live_match_row.replace('.', ''));
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
                if (scoreState === sel.score_final_state || stageLower.includes('fin') || stageLower === '') {
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
        return {matches, debug};
    }""", selectors)

    matches = result.get('matches', [])
    debug = result.get('debug', {})
    print(f"   [Streamer] Found {len(matches)} matches.")
    #print(f"   [Streamer] Debug: {debug}")

    # Status breakdown
    status_counts = {}
    for m in matches:
        s = m.get('status', 'unknown')
        status_counts[s] = status_counts.get(s, 0) + 1
    if status_counts:
        print(f"   [Streamer] Status breakdown: {status_counts}")

    # Sample first 3 for quick sanity check
    for m in matches[:3]:
        print(f"   [DEBUG] {m['home_team']} vs {m['away_team']} | status={m['status']} score={m['home_score']}-{m['away_score']} minute={m['minute']} stage={m['stage_detail']} time={m['match_time']}")

    return matches or []


# ---------------------------------------------------------------------------
# Tab clicking helpers – MINIMAL CHANGE 2: added fallback
# ---------------------------------------------------------------------------
async def _click_all_tab(page) -> bool:
    """Verify the ALL tab is selected; click it only if it isn't."""
    try:
        all_tab_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "all_tab")
        if not all_tab_sel:
            return True  # no selector — likely fine by default

        tab = page.locator(all_tab_sel)
        if not await tab.is_visible(timeout=3000):
            return True  # tab not visible — page may not use tabs

        # Check if already selected (Flashscore adds "selected" class)
        cls = await tab.get_attribute("class") or ""
        if "selected" in cls:
            return True  # already active, nothing to do

        # Not selected — click to activate
        print(f"   [Streamer] ALL tab not selected, clicking...")
        await page.click(all_tab_sel, force=True, timeout=3000)
        await asyncio.sleep(0.5)
        return True
    except Exception as e:
        print(f"   [Streamer] Error verifying ALL tab: {e}")
    return False


# ---------------------------------------------------------------------------
# ensure_content_expanded – MINIMAL CHANGE 3: added smart league expansion
# ---------------------------------------------------------------------------
async def ensure_content_expanded(page):
    """
    Bulk-expand all collapsed leagues via a single JS call.
    ~2s instead of ~3min for 347 headers.
    """
    try:
        down_arrow_sel = SelectorManager.get_selector("fs_home_page", "league_expand_icon_collapsed")

        expanded = await page.evaluate(r"""(arrowSel) => {
            const arrows = document.querySelectorAll(arrowSel);
            let count = 0;
            arrows.forEach(a => {
                const header = a.closest('[class*="event__header"]') || a.parentElement;
                if (header) { header.click(); count++; }
            });
            return count;
        }""", down_arrow_sel)

        if expanded > 0:
            await asyncio.sleep(1.0)  # single settle wait
            print(f"   [Streamer] Bulk-expanded {expanded} leagues.")
        else:
            print(f"   [Streamer] All leagues already expanded.")
    except Exception as e:
        print(f"   [Streamer] Expansion warning: {e}")

    return True


# ---------------------------------------------------------------------------
# Main streaming loop (unchanged except _touch_heartbeat is now guaranteed)
# ---------------------------------------------------------------------------
async def live_score_streamer(playwright: Playwright):
    """
    Main streaming loop v3.2 (Mobile Optimized).
    - Headless browser session with iPhone 12 emulation.
    - 60s extraction interval.
    - Robust dropdown + league expansion.
    - Immediate DB + CSV upserts.
    """
    print("\n   [Streamer] 🔴 Mobile Live Score Streamer v3.2 starting (Headless, 60s)...")
    log_audit_event("STREAMER_START", "Mobile live score streamer v3.2 initialized (Headless, 60s).")

    browser = None
    try:
        # Launch headless Chromium
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"]
        )

        # Emulate iPhone 12
        iphone_12 = playwright.devices['iPhone 12']
        context = await browser.new_context(
            **iphone_12,
            timezone_id="Africa/Lagos"
        )
        page = await context.new_page()

        # Initial navigation (wait up to 3 mins)
        print("   [Streamer] Navigating to Flashscore (Mobile view, up to 3 mins)...")
        await page.goto(FLASHSCORE_URL, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
        
        # Target a visible element to ensure page has actual content before proceeding
        try:
            sport_sel = SelectorManager.get_selector_strict("fs_home_page", "sport_container")
            await page.wait_for_selector(sport_sel, timeout=60000)
        except:
            print("   [Streamer] Warning: sportName container not found, proceeding anyway...")
        
        await asyncio.sleep(2)
        
        # Handle cookies/popups
        await fs_universal_popup_dismissal(page, "fs_home_page")
        
        # Ensure ALL tab is active
        await _click_all_tab(page)
        
        # Initial expansion
        await ensure_content_expanded(page)

        EXPANSION_INTERVAL = 5  # re-expand every Nth cycle

        sync = SyncManager()
        cycle = 0

        while True:
            cycle += 1
            _touch_heartbeat()   # now always defined
            now_ts = dt.now().strftime("%H:%M:%S")
            
            try:
                # Periodic expansion check (every Nth cycle — leagues stay expanded)
                if cycle % EXPANSION_INTERVAL == 0:
                    await ensure_content_expanded(page)

                # Extraction
                all_matches = await _extract_all_matches(page)
                
                # Separate by category
                LIVE_STATUSES = {'live', 'halftime', 'break', 'penalties', 'extra_time'}
                RESOLVED_STATUSES = {'finished', 'cancelled', 'postponed', 'fro', 'abandoned'}

                live_matches = [m for m in all_matches if m.get('status') in LIVE_STATUSES]
                resolved_matches = [m for m in all_matches if m.get('status') in RESOLVED_STATUSES]
                current_live_ids = {m['fixture_id'] for m in live_matches}

                # Save & Sync
                stale_ids = _purge_stale_live_scores(current_live_ids)
                if stale_ids:
                    print(f"   [Streamer] Decision: Purged {len(stale_ids)} stale matches from local state.")
                
                if live_matches or resolved_matches:
                    print(f"   [Streamer] Process: Upserting {len(live_matches)} live entries and {len(resolved_matches)} resolved entries.")
                    # Update local CSVs
                    for m in live_matches:
                        save_live_score_entry(m)
                    
                    sched_upd, pred_upd = _propagate_status_updates(live_matches, resolved_matches)
                    print(f"   [Streamer] Status: Propagation updated {len(sched_upd)} schedule rows and {len(pred_upd)} prediction rows.")

                    # Immediate Supabase Sync
                    if sync.supabase:
                        print(f"   [Streamer] Sync: Pushing updates to Supabase...")
                        if live_matches: await sync.batch_upsert('live_scores', live_matches)
                        if pred_upd: await sync.batch_upsert('predictions', pred_upd)
                        if sched_upd: await sync.batch_upsert('schedules', sched_upd)
                        if stale_ids:
                            try:
                                print(f"   [Streamer] Sync: Deleting {len(stale_ids)} stale entries from Supabase.")
                                sync.supabase.table('live_scores').delete().in_('fixture_id', list(stale_ids)).execute()
                            except Exception as e:
                                print(f"   [Streamer] Sync Warning: Supabase deletion failed: {e}")

                    print(f"   [Streamer] Cycle {cycle} complete at {now_ts}. Summary: {len(live_matches)} Live | {len(resolved_matches)} Resolved | {len(all_matches)} Scanned.")
                else:
                    # Fallback check
                    _propagate_status_updates([], [])
                    print(f"   [Streamer] {now_ts} — No active/resolved matches found (Cycle {cycle}). Fallback check performed.")

            except Exception as e:
                print(f"   [Streamer] ⚠ Extraction Error in cycle {cycle}: {e}")
                # Try to recover session
                try:
                    print("   [Streamer] Recovery: Reloading page and re-authenticating state...")
                    await page.reload(wait_until="networkidle")
                    await fs_universal_popup_dismissal(page, "fs_home_page")
                    await _click_all_tab(page)
                except Exception as re:
                    print(f"   [Streamer] Recovery Failed: {re}")

            await asyncio.sleep(STREAM_INTERVAL)

    except asyncio.CancelledError:
        print("   [Streamer] Streamer cancelled.")
    except Exception as e:
        print(f"   [Streamer] Fatal error: {e}")
    finally:
        if browser:
            try:
                await browser.close()
            except: pass
        print("   [Streamer] 🔴 Streamer stopped.")