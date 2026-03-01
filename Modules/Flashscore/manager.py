# manager.py: manager.py: Orchestration layer for Flashscore data extraction.
# Part of LeoBook Modules — Flashscore
#
# Functions: run_flashscore_analysis()

"""
Flashscore Orchestrator
Pure coordinator of Chapter 1A and 1B logic.
"""

import asyncio
import os
from datetime import datetime as dt, timedelta
from zoneinfo import ZoneInfo
from playwright.async_api import Playwright

from Data.Access.db_helpers import (
    get_last_processed_info, save_schedule_entry, save_team_entry
)
from Core.Browser.site_helpers import fs_universal_popup_dismissal, click_next_day
from Core.Utils.utils import BatchProcessor
from Core.Intelligence.selector_manager import SelectorManager
from Core.Utils.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT
from Core.Intelligence.aigo_suite import AIGOSuite

# Modular Imports
from .fs_schedule import extract_matches_from_page
from .fs_processor import process_match_task
from .fs_offline import run_flashscore_offline_repredict

NIGERIA_TZ = ZoneInfo("Africa/Lagos")

@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_flashscore_analysis(playwright: Playwright, refresh: bool = False, target_dates: list = None):
    """
    Main function to handle Flashscore data extraction and analysis.
    Coordinates browser launch, navigation, schedule extraction, and batch processing.
    """
    print("\n--- Running Chapter 1A/1B: Data Extraction & Analysis ---")

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
    )

    context = None
    try:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            timezone_id="Africa/Lagos"
        )
        page = await context.new_page()
        
        # Concurrency strictly from .env MAX_CONCURRENCY
        from Core.Utils.constants import MAX_CONCURRENCY

        total_cycle_predictions = 0

        # --- Navigation ---
        print("  [Navigation] Going to Flashscore...")
        for attempt in range(5):
            try:
                await page.goto("https://www.flashscore.com/football/", wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                print("  [Navigation] Flashscore loaded successfully.")
                break 
            except Exception as e:
                print(f"  [Navigation Error] Attempt {attempt + 1}/5 failed: {e}")
                if attempt < 4:
                    await asyncio.sleep(5)
                else:
                    print(f"  [Critical] All navigation attempts failed.")
                    await context.close()
                    return
                    
        await fs_universal_popup_dismissal(page, "fs_home_page")

        last_processed_info = get_last_processed_info()
        
        # Bypass resume if refresh=True
        resume_date = last_processed_info.get('date_obj') if not refresh else None
        
        if resume_date and resume_date > (dt.now(NIGERIA_TZ) + timedelta(days=7)).date():
            print(f"  [Chapter 1A] Resume date {resume_date} is beyond 7-day window. All caught up — skipping forward scan.")
        else:
            if target_dates:
                 print(f"  [Chapter 1A] Starting analysis loop for specific dates: {target_dates}")
                 processing_dates = [(dt.strptime(d, "%d.%m.%Y"), d) for d in target_dates]
            else:
                 print(f"  [Chapter 1A] Starting analysis loop for 7 days (Refresh: {refresh})...")
                 processing_dates = [(dt.now(NIGERIA_TZ) + timedelta(days=i), (dt.now(NIGERIA_TZ) + timedelta(days=i)).strftime("%d.%m.%Y")) for i in range(7)]

            current_day_offset = 0
            for target_dt, target_full in processing_dates:
                # Calculate necessary clicks to reach the date if we are in sequential scan
                # If we have specific target_dates, we might need to jump.
                # Simplification: we only support jumps if they are in the near future/past relative to today.
                today = dt.now(NIGERIA_TZ).date()
                target_date_obj = target_dt.date()
                diff_days = (target_date_obj - today).days

                # Navigation logic (compensate for day_offset if sequential, or diff_days if specific)
                if target_dates:
                    # For specific dates, we reset to home and click diff_days times
                    await page.goto("https://www.flashscore.com/football/", wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                    await asyncio.sleep(2)
                    await fs_universal_popup_dismissal(page, "fs_home_page")
                    if diff_days > 0:
                        for _ in range(diff_days):
                            match_row_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "match_rows")
                            if not match_row_sel or not await click_next_day(page, match_row_sel): break
                            await asyncio.sleep(1)
                    elif diff_days < 0:
                         # click_prev_day not implemented yet, but we could add it if needed.
                         # For now, let's assume future/today dates.
                         pass
                else:
                    if current_day_offset > 0:
                        match_row_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "match_rows")
                        if not match_row_sel or not await click_next_day(page, match_row_sel):
                            break
                        await asyncio.sleep(2)
                    current_day_offset += 1

                if resume_date and target_dt.date() < resume_date:
                    continue

                print(f"\n--- ANALYZING DATE: {target_full} ---")
                await fs_universal_popup_dismissal(page, "fs_home_page")

                try:
                    scheduled_tab_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "tab_scheduled")
                    if scheduled_tab_sel and await page.locator(scheduled_tab_sel).is_visible(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT):
                        await page.click(scheduled_tab_sel)
                        await asyncio.sleep(2.0)
                except Exception:
                    pass

                await fs_universal_popup_dismissal(page, "fs_home_page")
                matches_data = await extract_matches_from_page(page)
                
                # --- Cleaning & Sorting ---
                for m in matches_data:
                    original_time_str = m.get('match_time')
                    if original_time_str:
                        clean_time_str = original_time_str.split('\n')[0].strip()
                        m['match_time'] = clean_time_str if clean_time_str and clean_time_str != 'N/A' else 'N/A'

                matches_data.sort(key=lambda x: x.get('match_time', '23:59'))

                # --- Load existing predictions for robust resume ---
                from Data.Access.db_helpers import PREDICTIONS_CSV
                import csv
                existing_ids = set()
                if os.path.exists(PREDICTIONS_CSV) and not refresh:
                    try:
                        with open(PREDICTIONS_CSV, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            existing_ids = {row['fixture_id'] for row in reader if row.get('fixture_id')}
                    except Exception:
                        pass

                # --- Save to DB & Filter ---
                valid_matches = []
                now_time = dt.now(NIGERIA_TZ).time()
                is_today = target_date.date() == dt.now(NIGERIA_TZ).date()

                def is_time_parsable(t_str):
                    try:
                        dt.strptime(t_str, '%H:%M')
                        return True
                    except (ValueError, TypeError):
                        return False

                for m in matches_data:
                    fixture_id = m.get('fixture_id') or m.get('id')
                    m['fixture_id'] = fixture_id # Standardize in dict
                    m['date'] = target_full
                    save_schedule_entry({
                        'fixture_id': fixture_id, 'date': m.get('date'), 'match_time': m.get('match_time') or m.get('time'),
                        'region_league': m.get('region_league'), 'home_team': m.get('home_team'),
                        'away_team': m.get('away_team'), 'home_team_id': m.get('home_team_id'),
                        'away_team_id': m.get('away_team_id'), 'match_status': 'scheduled',
                        'match_link': m.get('match_link')
                    })
                    save_team_entry({'team_id': m.get('home_team_id'), 'team_name': m.get('home_team'), 'region_league': m.get('region_league'), 'team_url': m.get('home_team_url')})
                    save_team_entry({'team_id': m.get('away_team_id'), 'team_name': m.get('away_team'), 'region_league': m.get('region_league'), 'team_url': m.get('away_team_url')})

                    # Robust Resume: Skip if already predicted
                    if fixture_id in existing_ids:
                        continue

                    if is_today:
                        time_str = m.get('time')
                        if is_time_parsable(time_str):
                            if dt.strptime(time_str, '%H:%M').time() > now_time:
                                valid_matches.append(m)
                        else:
                            # Non-parsable time (Postponed, etc) - Keep it in valid_matches for analysis
                            # unless it's explicitly 'N/A' or 'Fin'
                            if time_str not in ('N/A', 'Fin', 'Finished', 'CAN'):
                                valid_matches.append(m)
                    else:
                        valid_matches.append(m)

                # --- MANDATORY: Enrich ALL unenriched teams/leagues BEFORE predictions ---
                # (One-shot enrichment gate — prevents browser idle death during match processing)
                try:
                    from Scripts.build_search_dict import enrich_batch_teams_search_dict
                    from Data.Access.db_helpers import TEAMS_CSV
                    import csv as _csv
                    unenriched_teams = []
                    if os.path.exists(TEAMS_CSV):
                        with open(TEAMS_CSV, 'r', encoding='utf-8') as f:
                            for row in _csv.DictReader(f):
                                st = (row.get('search_terms') or '').strip()
                                abbr = (row.get('abbreviations') or '').strip()
                                tid = row.get('team_id', '')
                                tname = row.get('team_name', '')
                                if tid and tname and (not st or st == '[]' or not abbr or abbr == '[]'):
                                    unenriched_teams.append({'team_id': tid, 'team_name': tname})
                    if unenriched_teams:
                        # Cap to prevent gate from blocking on thousands of teams.
                        # Per-match enrichment handles the rest incrementally.
                        gate_cap = min(len(unenriched_teams), 100)
                        print(f"\n    [SearchDict Gate] Enriching {gate_cap}/{len(unenriched_teams)} unenriched teams before predictions...")
                        await enrich_batch_teams_search_dict(unenriched_teams[:gate_cap])
                        print(f"    [SearchDict Gate] ✓ Team enrichment complete.")
                    else:
                        print(f"    [SearchDict Gate] All teams already enriched.")
                except Exception as e:
                    print(f"    [SearchDict Gate] Non-fatal error: {e}")

                # --- Batch Processing (Concurrency from .env MAX_CONCURRENCY) ---
                if valid_matches:
                    print(f"    [Batching] Processing {len(valid_matches)} matches (Concurrency: {MAX_CONCURRENCY})...")

                    async def _run_batch_processing():
                        """Batch match processing — each match runs the full pipeline:
                        H2H → Standings → League Enrichment → Search Dict → Predict"""
                        nonlocal total_cycle_predictions
                        processor = BatchProcessor(max_concurrent=MAX_CONCURRENCY)
                        analysis_chunk_size = 10
                        for i in range(0, len(valid_matches), analysis_chunk_size):
                            chunk = valid_matches[i:i + analysis_chunk_size]
                            chunk_results = await processor.run_batch(chunk, process_match_task, browser=browser)
                            successful_in_chunk = sum(1 for r in chunk_results if r)
                            total_cycle_predictions += successful_in_chunk
                            if successful_in_chunk > 0:
                                print(f"\n   [Analytics Sync] {total_cycle_predictions} predictions generated. Triggering micro-batch sync...")
                                from Data.Access.sync_manager import run_full_sync
                                await run_full_sync()
                                # Retry enrichment for teams that were skipped earlier (LLM was unavailable)
                                try:
                                    from Core.Intelligence.llm_health_manager import health_manager
                                    from Data.Access.db_helpers import TEAMS_CSV
                                    if health_manager._gemini_active:
                                        import csv as _rtcsv
                                        retry_teams = []
                                        if os.path.exists(TEAMS_CSV):
                                            with open(TEAMS_CSV, 'r', encoding='utf-8') as f:
                                                for row in _rtcsv.DictReader(f):
                                                    st = (row.get('search_terms') or '').strip()
                                                    abbr = (row.get('abbreviations') or '').strip()
                                                    tid = row.get('team_id', '')
                                                    tname = row.get('team_name', '')
                                                    if tid and tname and (not st or st == '[]' or not abbr or abbr == '[]'):
                                                        retry_teams.append({'team_id': tid, 'team_name': tname})
                                        if retry_teams and len(retry_teams) <= 50:
                                            print(f"    [SearchDict Retry] LLM recovered — enriching {len(retry_teams)} remaining teams...")
                                            await enrich_batch_teams_search_dict(retry_teams)
                                except Exception:
                                    pass  # Non-fatal

                    # Run the per-match pipeline (v3.6)
                    # Each match: H2H → Standings → League Enrichment → Search Dict → Predict
                    # MAX_CONCURRENCY controls how many matches run in parallel
                    await _run_batch_processing()
                else:
                    print("    [Info] No new matches to process.")

    finally:
        if context is not None:
            await context.close()
        if 'browser' in locals():
             await browser.close()
             
    print(f"\n--- Data Extraction & Analysis Complete: {total_cycle_predictions} new predictions found. ---")


@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_flashscore_schedule_only(playwright: Playwright, refresh: bool = False, extract_all: bool = False, target_dates: list = None):
    """
    Schedule-only mode: extract match schedules, save to DB + sync.
    No predictions, no match-page analysis.
    If refresh=True, ignore resume date and start from today.
    If extract_all=True, also extract H2H + standings per match.
      - extract_all alone = today only
      - extract_all + refresh = 7 days
    """
    days = 7  # default
    if extract_all and not refresh:
        days = 1
    
    mode_label = "Schedule + H2H + Standings" if extract_all else "Schedule Only"
    print(f"\n--- Running {mode_label} ({days} day{'s' if days > 1 else ''}) ---")

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
    )

    context = None
    total_saved = 0
    total_deep = 0
    try:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            timezone_id="Africa/Lagos"
        )
        page = await context.new_page()

        # Concurrency strictly from .env MAX_CONCURRENCY
        from Core.Utils.constants import MAX_CONCURRENCY

        # Navigation
        print("  [Navigation] Going to Flashscore...")
        for attempt in range(5):
            try:
                await page.goto("https://www.flashscore.com/football/", wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                print("  [Navigation] Flashscore loaded successfully.")
                break
            except Exception as e:
                print(f"  [Navigation Error] Attempt {attempt + 1}/5 failed: {e}")
                if attempt < 4:
                    await asyncio.sleep(5)
                else:
                    print("  [Critical] All navigation attempts failed.")
                    return

        await fs_universal_popup_dismissal(page, "fs_home_page")

        # Resume logic (skipped if refresh=True or extract_all=True)
        resume_date = None
        if not refresh and not extract_all:
            last_processed_info = get_last_processed_info()
            resume_date = last_processed_info.get('date_obj')
            if resume_date and resume_date > (dt.now(NIGERIA_TZ) + timedelta(days=7)).date():
                print(f"  [Schedule] Resume date {resume_date} is beyond 7-day window. All caught up.")
                return
        else:
            msg = "Refresh mode" if refresh else "Full Extraction mode"
            print(f"  [Schedule] {msg} — bypassing resume logic.")

        if target_dates:
            print(f"  [Schedule] Processing specific dates: {target_dates}")
            processing_dates = [(dt.strptime(d, "%d.%m.%Y"), d) for d in target_dates]
        else:
            processing_dates = [(dt.now(NIGERIA_TZ) + timedelta(days=i), (dt.now(NIGERIA_TZ) + timedelta(days=i)).strftime("%d.%m.%Y")) for i in range(days)]

        current_day_offset = 0
        for target_dt, target_full in processing_dates:
            today = dt.now(NIGERIA_TZ).date()
            target_date_obj = target_dt.date()
            diff_days = (target_date_obj - today).days

            if target_dates:
                # Reset and jump for specific dates
                await page.goto("https://www.flashscore.com/football/", wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                await asyncio.sleep(2)
                await fs_universal_popup_dismissal(page, "fs_home_page")
                if diff_days > 0:
                    for _ in range(diff_days):
                        match_row_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "match_rows")
                        if not match_row_sel or not await click_next_day(page, match_row_sel): break
                        await asyncio.sleep(1)
            else:
                if current_day_offset > 0:
                    match_row_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "match_rows")
                    if not match_row_sel or not await click_next_day(page, match_row_sel):
                        break
                    await asyncio.sleep(2)
                current_day_offset += 1

            if resume_date and target_dt.date() < resume_date:
                continue

            print(f"\n--- EXTRACTING SCHEDULE: {target_full} ---")
            await fs_universal_popup_dismissal(page, "fs_home_page")
            # extract_matches_from_page handles expansion + extraction + batch save + sync
            matches_data = await extract_matches_from_page(page)

            # Stamp date on all matches for this day
            for m in matches_data:
                m['date'] = target_full

            total_saved += len(matches_data)
            print(f"  [Schedule] {len(matches_data)} matches for {target_full}.")

            # --- Deep Extraction: H2H + Standings per match ---
            if extract_all and matches_data:
                # Filter: deep extraction only for matches at least X hours in the future
                buffer_h = 1.5 if os.getenv('CODESPACES') == 'true' else 0.5
                now_limit = dt.now(NIGERIA_TZ) + timedelta(hours=buffer_h)
                
                deep_eligible = []
                for m in matches_data:
                    if not m.get('match_link'): continue
                    
                    # Parse match time to check if it's far enough in the future
                    try:
                        m_dt = dt.strptime(f"{m['date']} {m['match_time']}", "%d.%m.%Y %H:%M").replace(tzinfo=NIGERIA_TZ)
                        if m_dt >= now_limit:
                            deep_eligible.append(m)
                    except:
                        # If parsing fails, skip deep extraction for safety
                        continue

                print(f"\n  [Deep] Eligible for Analysis & Prediction: {len(deep_eligible)}/{len(matches_data)} matches (Buffer: {buffer_h}h)")

                # --- Batch Processing (v3.8: Unified extraction + prediction) ---
                async def _run_deep_batch_processing():
                    nonlocal total_deep
                    processor = BatchProcessor(max_concurrent=MAX_CONCURRENCY)
                    
                    # Process in chunks of 5 for more frequent syncs
                    chunk_size = 5
                    for i in range(0, len(deep_eligible), chunk_size):
                        chunk = deep_eligible[i:i + chunk_size]
                        print(f"    [Batch] Analyzing chunk {i//chunk_size + 1} ({len(chunk)} matches)...")
                        
                        chunk_results = await processor.run_batch(chunk, process_match_task, browser=browser)
                        successful_in_chunk = sum(1 for r in chunk_results if r)
                        total_deep += successful_in_chunk
                        
                        if successful_in_chunk > 0:
                            print(f"\n    [Cloud Sync] {total_deep} matches processed. Triggering sync...")
                            from Data.Access.sync_manager import run_full_sync
                            await run_full_sync(session_name=f"Schedule Deep Logic {total_deep}")
                
                await _run_deep_batch_processing()
                print(f"  [Deep] Completed: {total_deep} matches analyzed and predicted for {target_full}.")

                # Return to Flashscore home for the next day's navigation
                if day_offset < days - 1:
                    await page.goto("https://www.flashscore.com/football/", wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                    await asyncio.sleep(2)
                    await fs_universal_popup_dismissal(page, "fs_home_page")
                    # Re-advance to the correct day
                    for _ in range(day_offset + 1):
                        match_row_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "match_rows")
                        if not match_row_sel or not await click_next_day(page, match_row_sel):
                            break
                        await asyncio.sleep(1)

    finally:
        if context is not None:
            await context.close()
        if 'browser' in locals():
            await browser.close()

    # Cloud sync
    from Data.Access.sync_manager import run_full_sync
    await run_full_sync(session_name="Schedule Extraction")
    suffix = f" | {total_deep} deep-enriched" if extract_all else ""
    print(f"\n--- Schedule Extraction Complete: {total_saved} matches saved{suffix}. ---")
