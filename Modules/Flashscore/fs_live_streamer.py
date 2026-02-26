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
from Core.Intelligence.aigo_suite import AIGOSuite
from Modules.Flashscore.fs_extractor import extract_all_matches, expand_all_leagues as ensure_content_expanded

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
# Logic moved to Data.Access.db_helpers.evaluate_market_outcome
from Data.Access.db_helpers import evaluate_market_outcome


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
                    oc = evaluate_market_outcome(
                        row.get('prediction', ''),
                        row.get('home_score', ''),
                        row.get('away_score', ''),
                        row.get('home_team', ''),
                        row.get('away_team', '')
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
                    oc = evaluate_market_outcome(
                        row.get('prediction', ''),
                        row.get('home_score', ''),
                        row.get('away_score', ''),
                        row.get('home_team', ''),
                        row.get('away_team', '')
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
# Logic consolidated into Modules.Flashscore.fs_extractor


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
# Logic consolidated into Modules.Flashscore.fs_extractor.expand_all_leagues


# ---------------------------------------------------------------------------
# Main streaming loop (unchanged except _touch_heartbeat is now guaranteed)
# ---------------------------------------------------------------------------
@AIGOSuite.aigo_retry(max_retries=2, delay=30.0, use_aigo=False)
async def live_score_streamer(playwright: Playwright, user_data_dir: str = None):
    """
    Main streaming loop v3.2 (Mobile Optimized).
    - Headless browser session with iPhone 12 emulation.
    - 60s extraction interval.
    - Robust dropdown + league expansion.
    - Immediate DB + CSV upserts.
    - RECYCLING: Restarts browser every 3 cycles to prevent memory bloat/crashes.
    """
    print(f"\n   [Streamer] 🔴 Mobile Live Score Streamer v3.2 starting (Headless, 60s, isolation={'ON' if user_data_dir else 'OFF'})...")
    log_audit_event("STREAMER_START", f"Mobile live score streamer v3.2 initialized (Isolation: {bool(user_data_dir)}).")

    RECYCLE_INTERVAL = 3
    cycle = 0
    sync = SyncManager()

    while True:
        browser = None
        context = None
        try:
            # 1. Launch/Restart Browser Session
            print(f"   [Streamer] Starting fresh browser session (Cycle {cycle + 1})...")
            iphone_12 = playwright.devices['iPhone 12']
            
            if user_data_dir:
                # Use persistent context for full process isolation
                context = await playwright.chromium.launch_persistent_context(
                    user_data_dir,
                    headless=True,
                    args=["--disable-dev-shm-usage", "--no-sandbox"],
                    **iphone_12,
                    timezone_id="Africa/Lagos"
                )
                page = context.pages[0] if context.pages else await context.new_page()
            else:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage", "--no-sandbox"]
                )
                context = await browser.new_context(
                    **iphone_12,
                    timezone_id="Africa/Lagos"
                )
                page = await context.new_page()

            # 2. Initial Setup for the Session
            print("   [Streamer] Navigating to Flashscore (Mobile view, up to 3 mins)...")
            await page.goto(FLASHSCORE_URL, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
            
            try:
                sport_sel = SelectorManager.get_selector_strict("fs_home_page", "sport_container")
                await page.wait_for_selector(sport_sel, timeout=60000)
            except:
                print("   [Streamer] Warning: sportName container not found, proceeding anyway...")
            
            await asyncio.sleep(2)
            await fs_universal_popup_dismissal(page, "fs_home_page")
            await _click_all_tab(page)
            await ensure_content_expanded(page)

            # 3. Inner Loop: Run for N cycles before recycling session
            session_cycle = 0
            while session_cycle < RECYCLE_INTERVAL:
                cycle += 1
                session_cycle += 1
                _touch_heartbeat()
                now_ts = dt.now().strftime("%H:%M:%S")

                try:
                    # Extraction
                    all_matches = await extract_all_matches(page, label="Streamer")
                    
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
                        _propagate_status_updates([], [])
                        print(f"   [Streamer] {now_ts} — No active/resolved matches found (Cycle {cycle}). Fallback check performed.")

                    # Sleep before next cycle
                    await asyncio.sleep(STREAM_INTERVAL)

                except Exception as e:
                    if "Target crashed" in str(e) or "Page crashed" in str(e):
                        print(f"   [Streamer] 🛑 CRITICAL: Browser process crashed in cycle {cycle}. Recycling session now...")
                        break # Break inner loop, outer loop will restart browser
                    else:
                        print(f"   [Streamer] ⚠ Extraction Error in cycle {cycle}: {e}")
                        await asyncio.sleep(STREAM_INTERVAL)

            # End of session (either interval reached or crash)
            print(f"   [Streamer] Recycling browser session (Sessions per interval: {RECYCLE_INTERVAL})...")

        except Exception as e:
            print(f"   [Streamer] Loop Error: {e}. Retrying in 10s...")
            await asyncio.sleep(10)
        finally:
            if context:
                try: await context.close()
                except: pass
            if browser:
                try: await browser.close()
                except: pass

    print("   [Streamer] 🔴 Streamer stopped.")