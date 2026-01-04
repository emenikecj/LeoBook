"""
Football.com Main Orchestrator
Coordinates all sub-modules to execute the complete booking workflow.
"""

import asyncio
import os
from datetime import datetime as dt, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from playwright.async_api import Browser, Playwright

from Helpers.constants import WAIT_FOR_LOAD_STATE_TIMEOUT

from .navigator import load_or_create_session, navigate_to_schedule, select_target_date, extract_balance, log_page_title
from .extractor import extract_league_matches
from .matcher import match_predictions_with_site, filter_pending_predictions
from .booker import place_bets_for_matches, finalize_accumulator, clear_bet_slip
from Helpers.DB_Helpers.db_helpers import (
    PREDICTIONS_CSV, 
    update_prediction_status, 
    load_site_matches, 
    save_site_matches, 
    update_site_match_status,
    get_site_match_id
)
from Helpers.utils import log_error_state
from Helpers.monitor import PageMonitor


async def run_football_com_booking(playwright: Playwright):
    """
    Main function to handle Football.com login, match mapping, and bet placement.
    Orchestrates the entire booking workflow using modular components.
    """
    print("\n--- Running Football.com Booking ---")

    # 1. Filter pending predictions
    pending_predictions = await filter_pending_predictions()
    if not pending_predictions:
        print("  [Info] No pending predictions to book.")
        return

    # Group predictions by date (only future dates)
    predictions_by_date = {}
    today = dt.now().date()
    for pred in pending_predictions:
        date_str = pred.get('date')
        if date_str:
            try:
                pred_date = dt.strptime(date_str, "%d.%m.%Y").date()
                if pred_date >= today:
                    if date_str not in predictions_by_date:
                        predictions_by_date[date_str] = []
                    predictions_by_date[date_str].append(pred)
            except ValueError:
                continue  # Skip invalid dates

    if not predictions_by_date:
        print("  [Info] No predictions found.")
        return

    print(f"  [Info] Dates with predictions: {sorted(predictions_by_date.keys())}")

    user_data_dir = Path("DB/ChromeData_v3").absolute()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"  [System] Launching Persistent Context for Football.com... (Data Dir: {user_data_dir})")
    
    # Pre-emptive lock cleanup
    lock_file = user_data_dir / "SingletonLock"
    if lock_file.exists():
         print("  [System] Found existing SingletonLock. Removing it before launch...")
         try:
             lock_file.unlink()
         except Exception as e:
             print(f"  [Warning] Could not remove SingletonLock: {e}")

    context = None
    page = None
    
    try:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            args=[
                "--disable-dev-shm-usage", 
                "--no-sandbox", 
                "--disable-gpu",
                "--disable-extensions",
                "--disable-blink-features=AutomationControlled" 
            ],
            viewport={'width': 375, 'height': 812}, # Taller viewport for modern mobile
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
            timeout=120000 # Further increased timeout
        )
    except Exception as launch_e:
        print(f"  [CRITICAL ERROR] Failed to launch browser: {launch_e}")
        
        # Automatic Lock Cleanup
        lock_file = user_data_dir / "SingletonLock"
        if lock_file.exists():
            print("  [Auto-Fix] detected Chrome SingletonLock. removing...")
            try:
                lock_file.unlink()
                print("  [Auto-Fix] Lock file removed. Please restart.")
                return 
            except Exception as lock_e:
                 print(f"  [Auto-Fix Failed] Could not remove lock file: {lock_e}")

        print("  [Action Required] Please ensure no other Chrome/Playwright instances are running.")
        print("  [Info] Try 'taskkill /F /IM chrome.exe /T' if this persists.")
        return

    try:
        # 2. Load or create session
        # Note: navigator now accepts context directly
        _, page = await load_or_create_session(context)
        await log_page_title(page, "Session Loaded")
        
        # Activate Vigilance
        PageMonitor.attach_listeners(page)

        # 2b. Clear any existing bets in the slip
        await clear_bet_slip(page)

        # 3. Extract balance
        balance = await extract_balance(page)
        print(f"  [Balance] Current balance: NGN {balance}")

        # 4. Process each day's predictions
        for target_date, day_predictions in sorted(predictions_by_date.items()):
            if not page or page.is_closed():
                print("  [Fatal] Browser connection lost or page closed. Aborting cycle.")
                break

            print(f"\n--- Booking Process for Date: {target_date} ---")

            # --- REGISTRY CHECK (Optimization) ---
            cached_site_matches = load_site_matches(target_date)
            matched_urls = {} # fixture_id -> url
            unmatched_predictions = []

            for pred in day_predictions:
                fid = str(pred.get('fixture_id'))
                # Check if this prediction is already matched in our registry
                cached_match = next((m for m in cached_site_matches if m.get('fixture_id') == fid), None)
                
                if cached_match and cached_match.get('url'):
                    if cached_match.get('booking_status') == 'booked':
                         print(f"  [Registry] Prediction {fid} already booked. Skipping.")
                    else:
                         matched_urls[fid] = cached_match.get('url')
                         print(f"  [Registry] Found cached URL for {fid}: {cached_match.get('url')}")
                else:
                    unmatched_predictions.append(pred)

            # If we still have unmatched predictions, we MUST scrape
            if unmatched_predictions:
                print(f"  [Registry] {len(unmatched_predictions)} predictions need matching. Scraping schedule...")
                try:
                    await navigate_to_schedule(page)
                    if not await select_target_date(page, target_date):
                        print(f"  [Info] Date {target_date} not available. Skipping.")
                        continue

                    # Extract & Save to Registry
                    site_matches = await extract_league_matches(page, target_date)
                    if site_matches:
                        save_site_matches(site_matches)
                        # Refresh cache after save
                        cached_site_matches = load_site_matches(target_date)
                except Exception as nav_e:
                    print(f"  [Error] Extraction failed for {target_date}: {nav_e}")
                    continue

                # Run Matcher on the newly extracted/stored matches
                new_mappings = await match_predictions_with_site(unmatched_predictions, cached_site_matches)
                
                # Update Registry with newly matched fixture_ids
                for fid, url in new_mappings.items():
                    matched_urls[fid] = url
                    # Find which site match this belongs to and update it
                    site_match = next((m for m in cached_site_matches if m.get('url') == url), None)
                    if site_match:
                        update_site_match_status(site_match['site_match_id'], 'pending', fixture_id=fid)

            # --- BET PLACEMENT ---
            if matched_urls:
                print(f"  [Action] Proceeding to book {len(matched_urls)} matched predictions...")
                # We need to pass the full prediction dicts for those that are matched
                to_book_preds = [p for p in day_predictions if str(p.get('fixture_id')) in matched_urls]
                
                # Execute Booking
                # Note: place_bets_for_matches returns results or updates status
                await place_bets_for_matches(page, matched_urls, to_book_preds, target_date)
                
                # Final Sync: Update our local registry if booking were successful
                # (This is also handled inside place_bets_for_matches usually, 
                # but we ensure the registry reflects the 'booked' status)
                for fid in matched_urls.keys():
                    # We check predictions.csv status to see if it changed to 'booked'
                    # Or we could have place_bets_for_matches return the status.
                    # For now, let's assume if it finished without error, we check later.
                    pass 
            else:
                print(f"  [Info] No matches to book for {target_date}.")
                
    except Exception as e:
        print(f"[FATAL BOOKING ERROR] {e}")
        if page:
            await log_error_state(page, "football_com_fatal", e)
    finally:
        if context:
            await context.close()
