# outcome_reviewer.py: Post-match results extraction and accuracy reporting.
# Refactored for Clean Architecture (v2.7)
# This script updates predictions with final scores to calculate model performance.

"""
Outcome Reviewer Module
Core review processing and outcome analysis system.
Responsible for managing the review workflow, CSV operations, and outcome tracking.
"""

import asyncio
import csv
import os
from datetime import datetime as dt, timedelta
from typing import List, Dict, Any

from .prediction_evaluator import evaluate_prediction
from .health_monitor import HealthMonitor
from playwright.async_api import Playwright


# --- CONFIGURATION ---
BATCH_SIZE = 10      # How many matches to review at the same time
LOOKBACK_LIMIT = 5000 # Only check the last 500 eligible matches to prevent infinite backlogs
ENRICHMENT_CONCURRENCY = 10 # Concurrency for enriching past H2H matches

# --- PRODUCTION CONFIGURATION ---
PRODUCTION_MODE = True  # Set to True in production environment
MAX_RETRIES = 3          # Maximum retry attempts for failed operations
HEALTH_CHECK_INTERVAL = 300  # Health check every 5 minutes
ERROR_THRESHOLD = 10     # Alert if more than 10 errors in health check window

# Version and compatibility
VERSION = "2.6.0"
COMPATIBLE_MODELS = ["2.5", "2.6"]  # Compatible with these model versions

# --- IMPORTS ---
from .db_helpers import PREDICTIONS_CSV, SCHEDULES_CSV, save_schedule_entry, REGION_LEAGUE_CSV, FB_MATCHES_CSV, files_and_headers
from .csv_operations import upsert_entry, _read_csv, _write_csv
from Core.Intelligence.intelligence import get_selector_auto, get_selector


def _load_schedule_db() -> Dict[str, Dict]:
    """Loads the schedules.csv into a dictionary for quick lookups."""
    schedule_db = {}
    if not os.path.exists(SCHEDULES_CSV):
        return {}
    with open(SCHEDULES_CSV, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('fixture_id'):
                schedule_db[row['fixture_id']] = row
    return schedule_db


def get_predictions_to_review() -> List[Dict]:
    """
    Reads the predictions CSV and returns a list of matches that are in the past
    and have not yet been reviewed.
    """
    if not os.path.exists(PREDICTIONS_CSV):
        print(f"[Error] Predictions file not found at: {PREDICTIONS_CSV}")
        return []

    to_review = []
    today = dt.now().date()

    # Load the schedule DB once to avoid repeated file I/O
    schedule_db = _load_schedule_db()

    with open(PREDICTIONS_CSV, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    for row in reversed(all_rows):
        if len(to_review) >= LOOKBACK_LIMIT:
            break

        try:
            match_date_str = row.get('Date') or row.get('date')
            if not match_date_str:
                continue

            # Check for invalid time -> cancel match
            match_time = row.get('match_time')
            if not match_time or match_time == 'N/A':
                if row.get('status') != 'match_canceled':
                    save_single_outcome(row, 'match_canceled')
                continue

            match_date = dt.strptime(match_date_str, "%d.%m.%Y").date()
            status = row.get('status')

            # Check eligibility: Date is past OR (Date is today AND Time is 4+ hours ago)
            is_eligible = False
            now = dt.now()

            if match_date < today:
                is_eligible = True
            elif match_date == today:
                try:
                    match_dt = dt.combine(match_date, dt.strptime(match_time, "%H:%M").time())
                    if now >= match_dt + timedelta(hours=4):
                        is_eligible = True
                except (ValueError, TypeError):
                    pass

            if is_eligible and status not in ['reviewed', 'match_canceled', 'review_failed', 'match_postponed']:
                fixture_id = row.get('fixture_id')
                # --- OPTIMIZATION: Check local DB first ---
                if fixture_id and fixture_id in schedule_db:
                    db_entry = schedule_db[fixture_id]
                    if db_entry.get('match_status') == 'finished' and db_entry.get('home_score'):
                        row['actual_score'] = f"{db_entry['home_score']}-{db_entry['away_score']}"
                        row['source'] = 'db' # Mark as found in DB
                        to_review.append(row)
                        continue # Move to next prediction

                # Fallback to web scraping if not in DB or not finished
                match_link = row.get('match_link')
                if match_link and "flashscore" in match_link:
                        to_review.append(row)
        except (ValueError, TypeError):
            continue

    print(f"[Review] Found {len(to_review)} past predictions to review (Limit: {LOOKBACK_LIMIT}).")
    return to_review


def save_single_outcome(match_data: Dict, new_status: str):
    """
    Atomic Upsert to save the review result.
    """
    temp_file = PREDICTIONS_CSV + '.tmp'
    updated = False
    row_id_key = 'ID' if 'ID' in match_data else 'fixture_id'
    target_id = match_data.get(row_id_key)

    try:
        with open(PREDICTIONS_CSV, 'r', encoding='utf-8', newline='') as infile, \
             open(temp_file, 'w', encoding='utf-8', newline='') as outfile:

            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            if fieldnames is None: # Handle empty file case
                fieldnames = []

            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                current_id = row.get('ID') or row.get('fixture_id')

                if current_id == target_id:
                    row['status'] = new_status
                    row['actual_score'] = match_data.get('actual_score', 'N/A')

                    if new_status == 'reviewed':
                        prediction = row.get('prediction', '')
                        actual_score = row.get('actual_score', '')
                        home_team = row.get('home_team', '')
                        away_team = row.get('away_team', '')
                        is_correct = evaluate_prediction(prediction, actual_score, home_team, away_team)
                        # Only update if evaluation was successful
                        if is_correct is not None:
                            row['outcome_correct'] = str(is_correct)

                    updated = True

                writer.writerow(row)

        if updated:
            os.replace(temp_file, PREDICTIONS_CSV)
            # --- v2.7 synchronization to football_com_matches.csv ---
            if new_status == 'reviewed' and target_id:
                _sync_outcome_to_site_registry(target_id, match_data)
        else:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    except Exception as e:
        HealthMonitor.log_error("csv_save_error", f"Failed to save CSV: {e}", "high")
        print(f"    [File Error] Failed to write CSV: {e}")


def _sync_outcome_to_site_registry(fixture_id: str, match_data: Dict):
    """v2.7 Sync: Updates fb_matches.csv when a prediction is reviewed."""
    if not os.path.exists(FB_MATCHES_CSV):
        return

    try:
        # 1. Determine WON/LOST
        actual_score = match_data.get('actual_score', '')
        prediction = match_data.get('prediction', '')
        home_team = match_data.get('home_team', '')
        away_team = match_data.get('away_team', '')
        
        is_correct = evaluate_prediction(prediction, actual_score, home_team, away_team)
        if is_correct is None: return
        
        outcome_status = "WON" if is_correct else "LOST"
        
        # 2. Update site registry
        rows = _read_csv(FB_MATCHES_CSV)
        sync_count = 0
        for row in rows:
            if str(row.get('fixture_id')) == str(fixture_id):
                row['status'] = outcome_status
                sync_count += 1
        
        if sync_count > 0:
            _write_csv(FB_MATCHES_CSV, rows, files_and_headers[FB_MATCHES_CSV])
            print(f"    [Sync] Updated {sync_count} records in fb_matches.csv to {outcome_status}")
            
    except Exception as e:
        print(f"    [Sync Error] Failed to sync outcome: {e}")


async def process_review_task(match: Dict, browser, semaphore: asyncio.Semaphore) -> None:
    """
    Worker function for a single match review.
    Includes a retry mechanism with progressive delays for transient errors.
    """
    async with semaphore:
        # Import here to avoid circular imports
        from playwright.async_api import async_playwright
        from Core.Browser.site_helpers import fs_universal_popup_dismissal
        from Core.Utils.utils import log_error_state
        from Core.Intelligence.intelligence import get_selector_auto, get_selector

        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        # Block images and fonts for speed
        await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda route: route.abort())
        page = await context.new_page()

        match_id = match.get('fixture_id')
        home_team = match.get('home_team', 'Unknown')
        away_team = match.get('away_team', 'Unknown')

        # --- OPTIMIZATION: Handle DB-sourced scores directly ---
        if match.get('source') == 'db':
            print(f"  [DB Check] {home_team} vs {away_team} -> Score: {match['actual_score']}")
            save_single_outcome(match, 'reviewed')
            await context.close()
            return

        # --- Web Scraping Fallback with Retry Logic ---
        url = match.get('match_link')
        if not url:
            
            save_single_outcome({'fixture_id': match_id}, 'no_url')
            await context.close()
            return

        if not url.startswith('http'):
            url = f"https://www.flashscore.com{url}"

        # Progressive retry delays: 5s, 10s, 15s
        retry_delays = [5, 10, 15]
        max_retries = len(retry_delays)

        for attempt in range(max_retries):
            try:
                print(f"  [Score Check] {home_team} vs {away_team} (Attempt {attempt + 1})")
                await page.goto(url, wait_until="domcontentloaded", timeout=180000) 
                await fs_universal_popup_dismissal(page)

                # Extract league URL and update region_league.csv if applicable
                league_url = await get_league_url(page)
                region_league = match.get('region_league')
                if league_url and region_league:
                    update_region_league_url(region_league, league_url)

                final_score = await get_final_score(page)

                if final_score == "NOT_FINISHED":
                    print(f"    [Skip]  {home_team} vs {away_team} Match not finished yet.")
                    # Don't mark as pending, just skip for now - will be retried in future runs
                    save_single_outcome({'fixture_id': match_id}, 'pending')
                    await context.close()
                    return
                elif final_score == "Match_POSTPONED":
                    print(f"    [Skip]  {home_team} vs {away_team} Match postponed.")
                    save_single_outcome({'fixture_id': match_id}, 'match_postponed')
                    await context.close()
                    return
                elif final_score == "Error":
                    print(f"    [Fail] {home_team} vs {away_team} Could not extract score from page.")
                    # Continue to retry
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        print(f"      Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Max retries reached, will handle after loop
                        break
                else:
                    print(f"    [Success] {home_team} vs {away_team} -> Score: {final_score}")
                    match['actual_score'] = final_score
                    save_single_outcome(match, 'reviewed')
                    await context.close()
                    return

            except Exception as e:
                HealthMonitor.log_error("review_task_error", f"Review failed for {match_id}: {e}", "medium")
                print(f"    [Attempt {attempt + 1} Failed] Error for {match_id}: {e}")
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    print(f"      Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    # Max retries reached, will handle after loop
                    break

        # After all retries exhausted, check final status
        try:
            ERROR_HEADER = page.get_by_text("Error:", exact=True)
            ERROR_MESSAGE = page.get_by_text("The requested page can't be displayed. Please try again later.")
            is_error_visible = (await ERROR_HEADER.is_visible()) and (await ERROR_MESSAGE.is_visible())
            if is_error_visible:
                print(f"    [Match Canceled] {home_team} vs {away_team}")
                save_single_outcome({'fixture_id': match_id}, 'match_canceled')
            else:
                print(f"    [Review Failed] {home_team} vs {away_team}")
                save_single_outcome({'fixture_id': match_id}, 'review_failed')
        except Exception as e:
            print(f"    [Review Failed] {home_team} vs {away_team}")
            save_single_outcome({'fixture_id': match_id}, 'review_failed')

        await context.close()


async def get_league_url(page):
    """
    Extracts the league URL from the match page. Returns empty string if not found.
    """
    try:
        # Look for breadcrumb links to league
        league_link_sel = "a[href*='/football/'][href$='/']"
        league_link = page.locator(league_link_sel).first
        # Use shorter timeout to prevent hanging
        LEAGUE_TIMEOUT = 10000  # 10 seconds
        href = await league_link.get_attribute('href', timeout=LEAGUE_TIMEOUT)
        if href:
            return href
    except:
        pass
    return ""


async def get_final_score(page):
    """
    Extracts the final score. Returns 'Error' if not found.
    """
    try:
        # Check Status
        status_selector = get_selector("fs_match_page", "meta_match_status") or "div.fixedHeaderDuel__detailStatus"
        try:
            from Core.Utils.constants import WAIT_FOR_LOAD_STATE_TIMEOUT
            status_text = await page.locator(status_selector).first.inner_text(timeout=30000)
            ERROR_HEADER = page.get_by_text("Error:", exact=True)
            ERROR_MESSAGE = page.get_by_text("The requested page can't be displayed. Please try again later.")
            
            if "postponed" in status_text.lower():
                return "Match_POSTPONED"   

            # Check if both are visible
            is_error_visible = (await ERROR_HEADER.is_visible()) and (await ERROR_MESSAGE.is_visible())
            if is_error_visible:
                return "Error"
            
        except:             
            status_text = "finished"

        if "finished" not in status_text.lower() and "aet" not in status_text.lower() and "pen" not in status_text.lower():
            return "NOT_FINISHED"

        # Extract Score
        home_score_sel = get_selector("fs_match_page", "header_score_home") or "div.detailScore__wrapper > span:nth-child(1)"
        away_score_sel = get_selector("fs_match_page", "header_score_away") or "div.detailScore__wrapper > span:nth-child(3)"

        # Use shorter timeout for score extraction to prevent hanging
        SCORE_TIMEOUT = 30000  # 30 seconds
        home_score = await page.locator(home_score_sel).first.inner_text(timeout=SCORE_TIMEOUT)
        away_score = await page.locator(away_score_sel).first.inner_text(timeout=SCORE_TIMEOUT)

        final_score = f"{home_score.strip() if home_score else ''}-{away_score.strip() if away_score else ''}"
        return final_score

    except Exception as e:
        HealthMonitor.log_error("score_extraction_error", f"Failed to extract score: {e}", "medium")
        return "Error"


def update_region_league_url(region_league: str, url: str):
    """
    Updates the url for a region_league in region_league.csv.
    Parses the region_league string to create proper region_league_id.
    """
    if not region_league or not url or " - " not in region_league:
        return

    # Ensure URL is absolute
    if url.startswith('/'):
        url = f"https://www.flashscore.com{url}"

    # Parse region and league from "REGION - LEAGUE" format
    region, league_name = region_league.split(" - ", 1)

    # Create composite ID matching the save_region_league_entry format
    region_league_id = f"{region}_{league_name}".replace(' ', '_').replace('-', '_').upper()

    entry = {
        'region_league_id': region_league_id,
        'region': region.strip(),
        'league_name': league_name.strip(),
        'url': url
    }
    upsert_entry(REGION_LEAGUE_CSV, entry, files_and_headers[REGION_LEAGUE_CSV], 'region_league_id')


async def run_review_process(playwright: Playwright):
    """Main review process orchestration"""
    print("--- LEO V2.6: Outcome Review Engine (Concurrent) ---")
    matches_to_review = get_predictions_to_review()

    if not matches_to_review:
        print("--- No new past matches to review. ---")
        return

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
    )

    try:
        sem = asyncio.Semaphore(BATCH_SIZE)
        tasks = []

        print(f"[Processing] Starting batch review for {len(matches_to_review)} matches...")

        for match in matches_to_review:
            task = asyncio.create_task(process_review_task(match, browser, sem))
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Update learning weights based on reviewed outcomes
        try:
            from Core.Intelligence.model import update_learning_weights
            updated_weights = update_learning_weights()
            print(f"--- Learning Engine: Updated {len(updated_weights)-1} rule weights ---")
        except Exception as e:
            HealthMonitor.log_error("learning_update_error", f"Failed to update learning weights: {e}", "medium")
            print(f"--- Learning Engine Error: {e} ---")
            
    finally:
        await browser.close()

    print("--- Review Process Complete ---")