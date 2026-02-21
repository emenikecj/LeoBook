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
from Core.Utils.monitor import PageMonitor
from Core.Intelligence.selector_manager import SelectorManager
from Core.Utils.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT

# Modular Imports
from .fs_schedule import extract_matches_from_page
from .fs_processor import process_match_task
from .fs_offline import run_flashscore_offline_repredict

NIGERIA_TZ = ZoneInfo("Africa/Lagos")

async def run_flashscore_analysis(playwright: Playwright):
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
        PageMonitor.attach_listeners(page)
        
        # Concurrency settings from environment (as baseline)
        env_concurrency = int(os.getenv('FLASHSCORE_CONCURRENCY', 5))

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
        
        # Fix #5: If resume date is already in the future, skip forward scanning
        resume_date = last_processed_info.get('date_obj')
        if resume_date and resume_date > (dt.now(NIGERIA_TZ) + timedelta(days=7)).date():
            print(f"  [Chapter 1A] Resume date {resume_date} is beyond 7-day window. All caught up — skipping forward scan.")
        else:
            print(f"  [Chapter 1A] Starting analysis loop for 7 days...")
            for day_offset in range(7):
                target_date = dt.now(NIGERIA_TZ) + timedelta(days=day_offset)
                target_full = target_date.strftime("%d.%m.%Y")
            
                if day_offset > 0:
                    match_row_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "match_rows")
                    if not match_row_sel or not await click_next_day(page, match_row_sel):
                        break
                    await asyncio.sleep(2)

                if resume_date and target_date.date() < resume_date:
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
                    original_time_str = m.get('time')
                    if original_time_str:
                        clean_time_str = original_time_str.split('\n')[0].strip()
                        m['time'] = clean_time_str if clean_time_str and clean_time_str != 'N/A' else 'N/A'

                matches_data.sort(key=lambda x: x.get('time', '23:59'))

                # --- Load existing predictions for robust resume ---
                from Data.Access.db_helpers import PREDICTIONS_CSV
                import csv
                existing_ids = set()
                if os.path.exists(PREDICTIONS_CSV):
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
                    fixture_id = m.get('id')
                    m['date'] = target_full
                    save_schedule_entry({
                        'fixture_id': fixture_id, 'date': m.get('date'), 'match_time': m.get('time'),
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

                # --- Batch Processing With Dynamic Concurrency ---
                if valid_matches:
                    # Dynamic scaling
                    if len(valid_matches) > 100:
                        max_concurrent = min(env_concurrency + 3, 10) # Aggressive
                    elif len(valid_matches) < 20:
                        max_concurrent = max(env_concurrency - 2, 2) # Conservative
                    else:
                        max_concurrent = env_concurrency             # Standard
                    
                    print(f"    [Batching] Processing {len(valid_matches)} matches concurrently (Scaling: {max_concurrent})...")
                    processor = BatchProcessor(max_concurrent=max_concurrent)
                    
                    # Process in smaller chunks to trigger frequent syncs
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
                else:
                    print("    [Info] No new matches to process.")

    finally:
        if context is not None:
            await context.close()
        if 'browser' in locals():
             await browser.close()
             
    print(f"\n--- Data Extraction & Analysis Complete: {total_cycle_predictions} new predictions found. ---")


async def run_flashscore_schedule_only(playwright: Playwright, refresh: bool = False, extract_all: bool = False):
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
        PageMonitor.attach_listeners(page)

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

        # Resume logic (skipped if refresh=True)
        resume_date = None
        if not refresh:
            last_processed_info = get_last_processed_info()
            resume_date = last_processed_info.get('date_obj')
            if resume_date and resume_date > (dt.now(NIGERIA_TZ) + timedelta(days=7)).date():
                print(f"  [Schedule] Resume date {resume_date} is beyond 7-day window. All caught up.")
                return
        else:
            print("  [Schedule] Refresh mode — starting from today.")

        for day_offset in range(days):
            target_date = dt.now(NIGERIA_TZ) + timedelta(days=day_offset)
            target_full = target_date.strftime("%d.%m.%Y")

            if day_offset > 0:
                match_row_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "match_rows")
                if not match_row_sel or not await click_next_day(page, match_row_sel):
                    break
                await asyncio.sleep(2)

            if resume_date and target_date.date() < resume_date:
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

                print(f"\n  [Deep] Eligible for H2H + Standings: {len(deep_eligible)}/{len(matches_data)} matches (Buffer: {buffer_h}h)")

                from Core.Browser.Extractors.h2h_extractor import activate_h2h_tab, extract_h2h_data, save_extracted_h2h_to_schedules
                from Core.Browser.Extractors.standings_extractor import activate_standings_tab, extract_standings_data
                from Data.Access.db_helpers import save_standings
                from .fs_utils import retry_extraction

                for i, match in enumerate(deep_eligible):
                    label = f"{match.get('home_team', '?')} vs {match.get('away_team', '?')}"
                    try:
                        print(f"    [{i+1}/{len(deep_eligible)}] {label}")
                        await page.goto(match['match_link'], wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                        await asyncio.sleep(2.0)
                        await fs_universal_popup_dismissal(page, "fs_match_page")

                        # --- H2H ---
                        if await activate_h2h_tab(page):
                            try:
                                # Expand "Show more" buttons for deeper history
                                show_more_sel = ".h2h__section .h2h__showMore"
                                for _ in range(2):
                                    buttons = page.locator(show_more_sel)
                                    btn_count = await buttons.count()
                                    for j in range(btn_count):
                                        try:
                                            btn = buttons.nth(j)
                                            if await btn.is_visible():
                                                await btn.click(timeout=5000)
                                                await asyncio.sleep(0.8)
                                        except:
                                            continue

                                await asyncio.sleep(1.0)
                                h2h = await retry_extraction(
                                    extract_h2h_data, page,
                                    match.get('home_team', ''), match.get('away_team', ''),
                                    "fs_h2h_tab"
                                )
                                h2h_total = sum(len(h2h.get(k, [])) for k in ('home_last_10_matches', 'away_last_10_matches', 'head_to_head'))
                                print(f"      [H2H] {h2h_total} records")
                                await save_extracted_h2h_to_schedules(h2h)
                            except Exception as e:
                                print(f"      [H2H Error] {e}")
                        
                        # --- Standings ---
                        if await activate_standings_tab(page):
                            try:
                                s_result = await retry_extraction(extract_standings_data, page)
                                s_data = s_result.get("standings", [])
                                s_league = s_result.get("region_league", "Unknown")
                                if s_league == "Unknown":
                                    s_league = match.get('region_league', 'Unknown')
                                if s_data and s_league != "Unknown":
                                    s_url = s_result.get("league_url", "")
                                    for row in s_data:
                                        row['url'] = s_url
                                    save_standings(s_data, s_league)
                                    print(f"      [Standings] {len(s_data)} rows for {s_league}")
                            except Exception as e:
                                print(f"      [Standings Error] {e}")

                        total_deep += 1

                    except Exception as e:
                        print(f"    [Skip] {label}: {e}")
                        continue
                    
                    # Navigate back to home page for next day (if needed)
                    # No — we stay on match pages, the day loop re-navigates

                print(f"  [Deep] Completed: {total_deep} matches enriched.")

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
