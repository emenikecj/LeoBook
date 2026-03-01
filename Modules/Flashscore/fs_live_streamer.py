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
    files_and_headers, evaluate_market_outcome,
    transform_streamer_match_to_schedule
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
_last_push_sig = None  # Delta detection: (frozenset(live_ids), sched_count, pred_count)
_missed_cycles = {}    # Persistence trace: {fixture_id: missed_count}

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


def _parse_match_start(date_val, time_val):
    """Parse DD.MM.YYYY or YYYY-MM-DD date + HH:MM time into a datetime."""
    import re
    if not date_val or not time_val:
        return None
    # Convert DD.MM.YYYY → YYYY-MM-DD
    m = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', date_val)
    if m:
        date_val = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    try:
        return dt.fromisoformat(f"{date_val}T{time_val}:00")
    except Exception:
        return None


def _propagate_status_updates(live_matches, resolved_matches, force_finished_ids=None):
    """
    Propagate live scores and resolved results into schedules.csv and predictions.csv.
    """
    resolved_matches = resolved_matches or []
    force_finished_ids = force_finished_ids or set()
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
    sched_dirty_ids = set()  # Track which fixture_ids actually changed
    for row in sched_rows:
        fid = row.get('fixture_id', '')

        if fid in live_ids:
            lm = live_map[fid]
            if row.get('status', '').lower() != 'live':
                row['status'] = 'live'
                sched_changed = True
                sched_dirty_ids.add(fid)
            if lm.get('home_score') and str(lm['home_score']) != str(row.get('home_score')):
                row['home_score'] = lm['home_score']
                row['away_score'] = lm['away_score']
                sched_changed = True
                sched_dirty_ids.add(fid)
            if lm.get('minute') and str(lm['minute']) != str(row.get('live_minute')):
                row['live_minute'] = lm['minute']
                sched_changed = True
                sched_dirty_ids.add(fid)

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
                sched_dirty_ids.add(fid)


        # Safety Check: Enforce 2.5hr Rule (Gold Rule)
        # Any match marked 'live' that is > 2.5hr past its start time must be 'finished'
        if row.get('status', '').lower() == 'live':
            match_start = _parse_match_start(row.get('date', ''), row.get('match_time', ''))
            if match_start and now > match_start + timedelta(minutes=150):
                row['status'] = 'finished'
                sched_changed = True
                sched_dirty_ids.add(fid)
                # If it was in live_ids, remove it so it's treated as resolved
                if fid in live_ids:
                    live_ids.remove(fid)
                    live_matches = [m for m in live_matches if m['fixture_id'] != fid]

    # --- Upsert Logic: Add missing matches to schedules ---
    existing_sched_ids = {r['fixture_id'] for r in sched_rows if r.get('fixture_id')}
    new_sched_entries = []
    for m in live_matches + resolved_matches:
        fid = m.get('fixture_id')
        if fid and fid not in existing_sched_ids:
            new_entry = transform_streamer_match_to_schedule(m)
            new_sched_entries.append(new_entry)
            sched_dirty_ids.add(fid)
            sched_changed = True
    
    if new_sched_entries:
        print(f"   [Streamer] Discovery: Found {len(new_sched_entries)} new matches missing from schedules. Adding them.")
        sched_rows.extend(new_sched_entries)

    sched_updates = []
    if sched_changed:
        _write_csv(SCHEDULES_CSV, sched_rows, sched_headers)
        sched_updates = [r for r in sched_rows if r.get('fixture_id') in sched_dirty_ids]

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
                row['match_status'] = 'live'
                row_changed = True
            
            # Update score if provided
            h_score = lm.get('home_score')
            a_score = lm.get('away_score')
            if h_score is not None and str(h_score) != str(row.get('home_score')):
                row['home_score'] = h_score
                row_changed = True
            if a_score is not None and str(a_score) != str(row.get('away_score')):
                row['away_score'] = a_score
                row_changed = True
            
            if row_changed:
                pred_changed = True
                pred_updates.append(row)

        elif fid in resolved_ids or fid in force_finished_ids:
            terminal_status = resolved_map[fid].get('status', 'finished') if fid in resolved_ids else 'finished'
            if cur_status != terminal_status:
                row['status'] = terminal_status
                row['match_status'] = terminal_status
                
                # Update final score from resolved map if available
                if fid in resolved_ids:
                    rm = resolved_map[fid]
                    if rm.get('home_score') is not None:
                        row['home_score'] = rm['home_score']
                    if rm.get('away_score') is not None:
                        row['away_score'] = rm['away_score']
                    row['actual_score'] = f"{rm.get('home_score', '')}-{rm.get('away_score', '')}"
                    if rm.get('stage_detail'):
                        row['stage_detail'] = rm['stage_detail']
                else: # fid in force_finished_ids but not resolved_ids
                    row['home_score'] = row.get('home_score', '')
                    row['away_score'] = row.get('away_score', '')
                    row['actual_score'] = f"{row.get('home_score', '')}-{row.get('away_score', '')}"

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

        # Safety Check: Enforce 2.5hr Rule (Gold Rule)
        if cur_status == 'live':
            match_start = _parse_match_start(row.get('date', ''), row.get('match_time', ''))
            if match_start and now > match_start + timedelta(minutes=150):
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
                if fid not in pred_updates:
                    pred_updates.append(row)
    if pred_changed:
        _write_csv(PREDICTIONS_CSV, pred_rows, pred_headers)
        
    return sched_updates, pred_updates


def _review_pending_backlog():
    """
    Scans predictions.csv for 'pending' entries and attempts to resolve them
    using finished data from schedules.csv.
    """
    if not os.path.exists(PREDICTIONS_CSV) or not os.path.exists(SCHEDULES_CSV):
        return []

    preds = _read_csv(PREDICTIONS_CSV)
    scheds = {s['fixture_id']: s for s in _read_csv(SCHEDULES_CSV) if s.get('fixture_id')}
    
    updates = []
    changed = False
    
    for p in preds:
        if p.get('status', '').lower() == 'pending':
            fid = p.get('fixture_id')
            if fid in scheds:
                s = scheds[fid]
                s_status = s.get('match_status', '').lower()
                h_score = s.get('home_score', '').strip()
                a_score = s.get('away_score', '').strip()
                
                # If finished and has valid scores, resolve
                if s_status in ('finished', 'aet', 'pen') and h_score.isdigit() and a_score.isdigit():
                    p['status'] = 'finished'
                    p['home_score'] = h_score
                    p['away_score'] = a_score
                    p['actual_score'] = f"{h_score}-{a_score}"
                    
                    oc = evaluate_market_outcome(
                        p.get('prediction', ''),
                        h_score,
                        a_score,
                        p.get('home_team', ''),
                        p.get('away_team', '')
                    )
                    if oc:
                        p['outcome_correct'] = oc
                    
                    p['last_updated'] = dt.now().isoformat()
                    updates.append(p)
                    changed = True
                    print(f"   [Streamer-Review] Resolved backlog match: {p.get('home_team')} vs {p.get('away_team')} -> {p['actual_score']}")

    if changed:
        _write_csv(PREDICTIONS_CSV, preds, files_and_headers[PREDICTIONS_CSV])
        print(f"   [Streamer-Review] Successfully resolved {len(updates)} pending backlog predictions.")
    
    return updates


# ---------------------------------------------------------------------------
# Purge stale live_scores: remove matches no longer in the LIVE tab
# ---------------------------------------------------------------------------
def _purge_stale_live_scores(current_live_ids: set, resolved_ids: set):
    """
    Remove any fixture from live_scores.csv that is NOT in the current LIVE set.
    Matches have a 3-cycle grace period unless explicitly resolved.
    """
    global _missed_cycles
    live_headers = files_and_headers.get(LIVE_SCORES_CSV, [])
    existing_rows = _read_csv(LIVE_SCORES_CSV)
    if not existing_rows:
        return set(), set()
    
    existing_ids = {r.get('fixture_id', '') for r in existing_rows}
    
    # Logic:
    # 1. Matches in 'current_live_ids' or 'resolved_ids' -> reset missed cycles to 0
    # 2. Matches in 'stale_potential' (existing but not in current scan) -> increment missed cycles
    # 3. Matches with missed_cycles >= 3 OR in 'resolved_ids' -> PURGE
    
    stale_potential = existing_ids - (current_live_ids | resolved_ids)
    
    # Reset missed count for matches found
    for fid in (current_live_ids | resolved_ids):
        _missed_cycles[fid] = 0
        
    # Increment for missing matches
    for fid in stale_potential:
        _missed_cycles[fid] = _missed_cycles.get(fid, 0) + 1
        
    # Identify IDs to purge
    purged_for_misses = {fid for fid, count in _missed_cycles.items() if count >= 3 and fid in existing_ids}
    purged_for_resolution = existing_ids & resolved_ids
    
    final_stale_ids = purged_for_misses | purged_for_resolution
    
    if final_stale_ids:
        kept_rows = [r for r in existing_rows if r.get('fixture_id', '') not in final_stale_ids]
        _write_csv(LIVE_SCORES_CSV, kept_rows, live_headers)
        # Clear from tracking
        for fid in final_stale_ids:
            if fid in _missed_cycles: del _missed_cycles[fid]
            
    return final_stale_ids, purged_for_misses



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

    global _last_push_sig
    RECYCLE_INTERVAL = 3
    cycle = 0
    sync = SyncManager()

    while True:
        browser = None
        context = None
        try:
            # 1. Launch/Restart Browser Session
            print(f"   [Streamer] Starting fresh browser session (Cycle {cycle + 1})...")
            iphone_12 = {k: v for k, v in playwright.devices['iPhone 12'].items()
                         if k != 'default_browser_type'}
            
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
                    current_resolved_ids = {m['fixture_id'] for m in resolved_matches}

                    # Save & Sync
                    final_stale_ids, force_finished_ids = _purge_stale_live_scores(current_live_ids, current_resolved_ids)
                    if final_stale_ids:
                        print(f"   [Streamer] Decision: Purged {len(final_stale_ids)} stale matches from local state (Missed: {len(force_finished_ids)}).")
                    
                    if live_matches or resolved_matches or force_finished_ids:
                        msg = f"   [Streamer] Process: Upserting {len(live_matches)} live entries"
                        if resolved_matches: msg += f" and {len(resolved_matches)} resolved entries"
                        if force_finished_ids: msg += f" and {len(force_finished_ids)} force-finished entries"
                        print(msg + ".")

                        # Update local CSVs
                        for m in live_matches:
                            save_live_score_entry(m)
                        
                        sched_upd, pred_upd = _propagate_status_updates(live_matches, resolved_matches, force_finished_ids=force_finished_ids)
                        print(f"   [Streamer] Status: Propagation updated {len(sched_upd)} schedule rows and {len(pred_upd)} prediction rows.")

                        # Delta detection — skip push if nothing changed from last cycle
                        current_sig = (frozenset(current_live_ids), len(sched_upd), len(pred_upd))
                        if current_sig == _last_push_sig:
                            print(f"   [Streamer] Cycle {cycle} complete at {now_ts}. Summary: {len(live_matches)} Live | {len(resolved_matches)} Resolved | {len(all_matches)} Scanned. (No delta — sync skipped)")
                        else:
                            _last_push_sig = current_sig
                            # Immediate Supabase Sync
                            if sync.supabase:
                                print(f"   [Streamer] Sync: Pushing updates to Supabase...")
                                if live_matches: await sync.batch_upsert('live_scores', live_matches)
                                if pred_upd: await sync.batch_upsert('predictions', pred_upd)
                                if sched_upd: await sync.batch_upsert('schedules', sched_upd)
                                if final_stale_ids:
                                    try:
                                        print(f"   [Streamer] Sync: Deleting {len(final_stale_ids)} stale entries from Supabase.")
                                        sync.supabase.table('live_scores').delete().in_('fixture_id', list(final_stale_ids)).execute()
                                    except Exception as e:
                                        print(f"   [Streamer] Sync Warning: Supabase deletion failed: {e}")

                            print(f"   [Streamer] Cycle {cycle} complete at {now_ts}. Summary: {len(live_matches)} Live | {len(resolved_matches)} Resolved | {len(all_matches)} Scanned.")
                    else:
                        _propagate_status_updates([], [])
                        print(f"   [Streamer] {now_ts} — No active/resolved matches found (Cycle {cycle}). Fallback check performed.")

                    # 4. Periodically Review Backlog (Every 5 cycles)
                    if cycle % 5 == 0:
                        backlog_upds = _review_pending_backlog()
                        if backlog_upds and sync.supabase:
                            print(f"   [Streamer] Sync: Pushing {len(backlog_upds)} backlog resolutions to Supabase...")
                            await sync.batch_upsert('predictions', backlog_upds)

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