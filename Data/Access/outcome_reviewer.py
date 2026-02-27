# outcome_reviewer.py: outcome_reviewer.py: Post-match results extraction and accuracy reporting.
# Part of LeoBook Data — Access Layer
#
# Functions: _load_schedule_db(), get_predictions_to_review(), smart_parse_datetime(), save_single_outcome(), sync_schedules_to_predictions(), _sync_outcome_to_site_registry(), process_review_task_offline(), process_review_task_browser() (+4 more)

"""
Outcome Reviewer Module
Core review processing and outcome analysis system.
Responsible for managing the review workflow, CSV operations, and outcome tracking.
"""

import asyncio
import csv
import os
import pandas as pd
import pytz
from datetime import datetime as dt, timedelta
from typing import List, Dict, Any, Optional

from playwright.async_api import Playwright
from Core.Intelligence.aigo_suite import AIGOSuite


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
from .db_helpers import (
    PREDICTIONS_CSV, SCHEDULES_CSV, TEAMS_CSV, REGION_LEAGUE_CSV, ACCURACY_REPORTS_CSV,
    FB_MATCHES_CSV, files_and_headers, save_team_entry, save_region_league_entry,
    evaluate_market_outcome, upsert_entry, log_audit_event
)
from .sync_manager import SyncManager
from Core.Intelligence.selector_manager import SelectorManager
from Core.Intelligence.selector_db import log_selector_failure
from Core.Utils.constants import NAVIGATION_TIMEOUT


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
    Reads the predictions CSV using pandas and returns a list of matches that 
    are in the past (Africa/Lagos timezone) and still have a 'pending' status.
    """
    if not os.path.exists(PREDICTIONS_CSV):
        print(f"[Error] Predictions file not found at: {PREDICTIONS_CSV}")
        return []

    try:
        # 1. Load predictions with pandas
        df = pd.read_csv(PREDICTIONS_CSV, dtype=str).fillna('')
        
        if df.empty:
            return []

        # 2. Filter for 'pending' status
        df = df[df['status'] == 'pending']
        if df.empty:
            return []

        # 3. Handle Date/Time Parsing
        # Format in CSV is 14.02.2026 for date, 15:00 for match_time
        def parse_dt(row):
            try:
                d_str = row.get('date') or row.get('Date')
                t_str = row.get('match_time')
                if not d_str or not t_str or t_str == 'N/A':
                    return pd.NaT
                return dt.strptime(f"{d_str} {t_str}", "%d.%m.%Y %H:%M")
            except:
                return pd.NaT

        df['scheduled_dt'] = df.apply(parse_dt, axis=1)
        df = df.dropna(subset=['scheduled_dt'])

        # 4. Timezone Awareness (Africa/Lagos)
        lagos_tz = pytz.timezone('Africa/Lagos')
        now_lagos = dt.now(lagos_tz)
        
        # Localize scheduled_dt if naive (usually it is)
        df['scheduled_dt'] = df['scheduled_dt'].apply(lambda x: lagos_tz.localize(x) if x.tzinfo is None else x)

        # 5. Filter for FINISHED matches only (scheduled ≥ 2.5h ago)
        # A football match takes ~2h. Adding 30min buffer to avoid visiting
        # matches still in progress — prevents wasted browser time + AIGO fallbacks.
        completion_cutoff = now_lagos - timedelta(hours=2, minutes=30)
        to_review_df = df[df['scheduled_dt'] < completion_cutoff]
        
        skipped = len(df[df['scheduled_dt'] < now_lagos]) - len(to_review_df)
        if skipped > 0:
            print(f"   [Filter] Skipped {skipped} matches still possibly in progress (< 2.5h old).")
        
        # Limit to LOOKBACK_LIMIT
        if len(to_review_df) > LOOKBACK_LIMIT:
            to_review_df = to_review_df.tail(LOOKBACK_LIMIT)

        # Return as list of dicts
        return to_review_df.to_dict('records')

    except Exception as e:
        print(f"[Error] get_predictions_to_review logic failed: {e}")
        return []


def smart_parse_datetime(dt_str: str):
    """
    Attempts to parse date/time which might be merged or in various formats.
    Example: '12.02.2026 15:00' or '12.02.202615:00'
    """
    dt_str = dt_str.strip()
    # Remove day of week if present (e.g. 'Thu 12.02.2026')
    if len(dt_str) > 10 and not dt_str[0].isdigit():
        dt_str = " ".join(dt_str.split()[1:])

    # Handle merged: 12.02.202615:00 -> 12.02.2026 15:00
    if len(dt_str) == 15 and dt_str[10].isdigit():
        dt_str = dt_str[:10] + " " + dt_str[10:]
    
    try:
        # Standard format
        parts = dt_str.split()
        if len(parts) == 2:
            d_part, t_part = parts
            # Keep original DD.MM.YYYY for local CSV compatibility
            # (SyncManager handles YYYY-MM-DD conversion for Supabase)
            return d_part, t_part
    except:
        pass
    return None, None


def save_single_outcome(match_data: Dict, new_status: str):
    """
    Atomic Upsert to save the review result.
    """
    temp_file = PREDICTIONS_CSV + '.tmp'
    os.makedirs(os.path.dirname(PREDICTIONS_CSV), exist_ok=True)
    updated = False
    row_id_key = 'ID' if 'ID' in match_data else 'fixture_id'
    target_id = match_data.get(row_id_key)

    try:
        with open(PREDICTIONS_CSV, 'r', encoding='utf-8', newline='') as infile, \
             open(temp_file, 'w', encoding='utf-8', newline='') as outfile:

            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            if fieldnames is None: 
                fieldnames = files_and_headers[PREDICTIONS_CSV]

            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                current_id = row.get('ID') or row.get('fixture_id')

                if current_id == target_id:
                    row['status'] = new_status
                    row['actual_score'] = match_data.get('actual_score', row.get('actual_score', 'N/A'))
                    
                    # Update scores if available in match_data (from schedules)
                    if 'home_score' in match_data and 'away_score' in match_data:
                        row['actual_score'] = f"{match_data['home_score']}-{match_data['away_score']}"

                    if new_status in ['reviewed', 'finished']:
                        prediction = row.get('prediction', '')
                        actual_score = row.get('actual_score', '')
                        home_team = row.get('home_team', '')
                        away_team = row.get('away_team', '')
                        
                        try:
                            # Robust score parsing
                            import re
                            score_match = re.match(r'(\d+)\s*-\s*(\d+)', actual_score or '')
                            if score_match:
                                h_core, a_core = score_match.group(1), score_match.group(2)
                                res = evaluate_market_outcome(prediction, h_core, a_core, home_team, away_team)
                                row['outcome_correct'] = res if res else '0'
                                
                                # Immediate Sync (Real-time update)
                                print(f"      [Cloud] Immediate sync for {target_id}...")
                                asyncio.create_task(SyncManager().batch_upsert('predictions', [row]))
                            else:
                                print(f"      [Eval Skip] Cannot parse score '{actual_score}' for {target_id}")
                        except Exception as eval_err:
                            print(f"      [Eval Error] {eval_err}")

                    updated = True

                writer.writerow(row)

        if updated:
            os.replace(temp_file, PREDICTIONS_CSV)
            if new_status == 'reviewed' and target_id:
                _sync_outcome_to_site_registry(target_id, match_data)
        else:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    except Exception as e:
        print(f"    [Health] csv_save_error (high): Failed to save CSV: {e}")
        print(f"    [File Error] Failed to write CSV: {e}")

def sync_schedules_to_predictions():
    """
    Ensures all entries in schedules.csv exist in predictions.csv.
    """
    if not os.path.exists(SCHEDULES_CSV) or not os.path.exists(PREDICTIONS_CSV):
        return

    schedules = _read_csv(SCHEDULES_CSV)
    predictions = _read_csv(PREDICTIONS_CSV)
    pred_ids = {p.get('fixture_id') for p in predictions if p.get('fixture_id')}

    added_count = 0
    for s in schedules:
        fid = s.get('fixture_id')
        if fid and fid not in pred_ids:
            # Create a shell prediction entry
            new_pred = {
                'fixture_id': fid,
                'date': s.get('date'),
                'match_time': s.get('match_time'),
                'region_league': s.get('region_league'),
                'home_team': s.get('home_team'),
                'away_team': s.get('away_team'),
                'home_team_id': s.get('home_team_id'),
                'away_team_id': s.get('away_team_id'),
                'prediction': 'PENDING',
                'confidence': 'Low',
                'match_status': s.get('match_status', 'pending'),
                'match_link': s.get('match_link'),
                'actual_score': f"{s.get('home_score', '')}-{s.get('away_score', '')}" if s.get('home_score') else 'N/A'
            }
            upsert_entry(PREDICTIONS_CSV, new_pred, files_and_headers[PREDICTIONS_CSV], 'fixture_id')
            added_count += 1
    
    if added_count > 0:
        print(f"  [Sync] Added {added_count} missing entries from schedules to predictions.")


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
        
        res = evaluate_market_outcome(prediction, actual_score, "", home_team, away_team)
        if not res: return
        
        outcome_status = "WON" if res == '1' else "LOST"
        
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




def process_review_task_offline(match: Dict) -> Optional[Dict]:
    """Review a prediction by reading its result from schedules.csv (no browser)."""
    schedule_db = _load_schedule_db()
    fixture_id = match.get('fixture_id')
    schedule = schedule_db.get(fixture_id, {})

    match_status = schedule.get('match_status', '').upper()
    home_score = schedule.get('home_score', '').strip()
    away_score = schedule.get('away_score', '').strip()

    # Scores must be numeric — dashes/empty/'None' are NOT real scores
    has_valid_scores = home_score.isdigit() and away_score.isdigit()

    if match_status in ('FINISHED', 'AET', 'PEN') and has_valid_scores:
        match['home_score'] = home_score
        match['away_score'] = away_score
        match['actual_score'] = f"{home_score}-{away_score}"
        save_single_outcome(match, 'finished')
        print(f"    [Result] {match.get('home_team')} {match['actual_score']} {match.get('away_team')}")
        return match
    elif match_status == 'POSTPONED':
        save_single_outcome(match, 'match_postponed')
        return None
    elif match_status == 'CANCELED':
        save_single_outcome(match, 'canceled')
        return None
    # Not yet finished — skip
    return None

async def process_review_task_browser(page, match: Dict) -> Optional[Dict]:
    """Review a prediction by visiting the match page (Browser fallback)."""
    match_link = match.get('match_link')
    if not match_link:
        return None

    try:
        print(f"      [Fallback] Visiting {match.get('home_team')} vs {match.get('away_team')}...")
        await page.goto(match_link, timeout=NAVIGATION_TIMEOUT)
        await page.wait_for_load_state("networkidle")

        final_score = await get_final_score(page)
        if final_score and '-' in final_score:
            match['actual_score'] = final_score
            h_score, a_score = final_score.split('-')
            match['home_score'] = h_score
            match['away_score'] = a_score
            save_single_outcome(match, 'finished')
            print(f"    [Result-B] {match.get('home_team')} {final_score} {match.get('away_team')}")
            return match
        elif final_score == "Match_POSTPONED":
            save_single_outcome(match, 'match_postponed')
        elif final_score == "ARCHIVED":
            print(f"      [!] Match {match.get('fixture_id')} appears deleted or archived. Flagging.")
            save_single_outcome(match, 'manual_review_needed')
    except Exception as e:
        print(f"      [Fallback Error] {e}")
    
    return None




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
        status_selector = SelectorManager.get_selector("fs_match_page", "meta_match_status") or "div.fixedHeaderDuel__detailStatus"
        try:
            status_text = await page.locator(status_selector).first.inner_text(timeout=30000)
            # Check for ARCHIVED or INVALID links (Flashscore 404 or Error pages)
            ERROR_PAGE_SEL = "div.errorMessage"
            if await page.locator(ERROR_PAGE_SEL).is_visible():
                return "ARCHIVED"

            error_header = page.get_by_text("Error:", exact=True)
            error_message = page.get_by_text("The requested page can't be displayed. Please try again later.")

            if "postponed" in status_text.lower():
                return "Match_POSTPONED"   

            # Check if both are visible
            if (await error_header.is_visible()) and (await error_message.is_visible()):
                return "ARCHIVED"
            
        except Exception as e:
            # If the page failed to load at all or the selector is missing
            status_text = "finished"

        if "finished" not in status_text.lower() and "aet" not in status_text.lower() and "pen" not in status_text.lower():
            return "NOT_FINISHED"

        # Extract Score (With AIGO-style fallback)
        home_score_sel = SelectorManager.get_selector("fs_match_page", "header_score_home") or "div.detailScore__wrapper > span:nth-child(1)"
        away_score_sel = SelectorManager.get_selector("fs_match_page", "header_score_away") or "div.detailScore__wrapper > span:nth-child(3)"

        try:
            # Use shorter timeout for score extraction to prevent hanging
            SCORE_TIMEOUT = 5000  # 5 seconds
            home_score = await page.locator(home_score_sel).first.inner_text(timeout=SCORE_TIMEOUT)
            away_score = await page.locator(away_score_sel).first.inner_text(timeout=SCORE_TIMEOUT)
            final_score = f"{home_score.strip() if home_score else ''}-{away_score.strip() if away_score else ''}"
            
            if '-' in final_score and final_score.replace('-', '').isdigit():
                return final_score
            else:
                raise ValueError("Malformed score")
                
        except Exception as sel_fail:
            print(f"      [Selector Failure] {sel_fail}. Attempting AIGO healing fallback...")
            # LOG FAILURE FOR HEALING
            failed_key = "header_score_away" if "nth-child(3)" in str(sel_fail) or "away" in str(sel_fail).lower() else "header_score_home"
            log_selector_failure("fs_match_page", failed_key, str(sel_fail))
            
            # Tier 1.5: Universal data-testid selector (works on ALL Flashscore layouts)
            try:
                home_score_t = await page.locator('[data-testid="wcl-matchRowScore"][data-side="1"]').first.inner_text(timeout=3000)
                away_score_t = await page.locator('[data-testid="wcl-matchRowScore"][data-side="2"]').first.inner_text(timeout=3000)
                testid_score = f"{home_score_t.strip()}-{away_score_t.strip()}"
                if testid_score.replace('-', '').isdigit():
                    print(f"      [AIGO HEALED] Extracted score via data-testid: {testid_score}")
                    return testid_score
            except Exception:
                pass  # Fall through to Tier 2

            # Tier 2 Heuristic: Search for team containers and relative score spans
            heuristic_score = await page.evaluate("""() => {
                // Try detailScore spans first
                const home = document.querySelector('.detailScore__home, [data-testid="wcl-matchRowScore"][data-side="1"]');
                const away = document.querySelector('.detailScore__away, [data-testid="wcl-matchRowScore"][data-side="2"]');
                if (home && away) return home.innerText.trim() + '-' + away.innerText.trim();
                // Broad pattern scan
                const spans = Array.from(document.querySelectorAll('span, div'));
                const scorePattern = /^(\\d+)\\s*-\\s*(\\d+)$/;
                for (const s of spans) {
                    if (scorePattern.test(s.innerText.trim())) return s.innerText.trim();
                }
                return null;
            }""")
            
            if heuristic_score:
                print(f"      [AIGO HEALED] Extracted score via heuristics: {heuristic_score}")
                return heuristic_score
                
        return "Error"

    except Exception as e:
        print(f"    [Health] score_extraction_error (medium): Failed to extract score: {e}")
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


@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_review_process(p: Optional[Playwright] = None):
    """
    Orchestrates the outcome review process (Offline version with Browser Fallback).
    """
    print("\n   [Prologue] Starting Prediction Review Engine...")
    try:
        # Load eligible matches
        to_review = get_predictions_to_review()
        if not to_review:
            print("   [Info] No pending predictions found for review.")
            return

        print(f"   [Info] Processing {len(to_review)} predictions for outcome review...")
        
        # Limit to lookback
        to_review = to_review[:LOOKBACK_LIMIT]
        
        processed_matches = []
        needs_browser = []

        for m in to_review:
            result = process_review_task_offline(m)
            if result:
                processed_matches.append(result)
            else:
                # If match is in the past but offline failed, queue for browser
                needs_browser.append(m)
        
        # Fallback to Browser if requested and needed
        if needs_browser and p:
            print(f"   [Info] Triggering Browser Fallback for {len(needs_browser)} unresolved reviews...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            for m in needs_browser:
                result = await process_review_task_browser(page, m)
                if result:
                    processed_matches.append(result)
            
            await browser.close()
        
        if processed_matches:
            print(f"\n   [SUCCESS] Reviewed {len(processed_matches)} match outcomes.")
            
            # Update learning weights based on reviewed outcomes
            try:
                from Core.Intelligence.learning_engine import LearningEngine
                updated_weights = LearningEngine.update_weights()
                print(f"   [Learning] Updated weights for {len(updated_weights)-1} leagues.")
            except Exception as e:
                print(f"   [Learning] Weight update skipped: {e}")
        else:
            print("\n   [Info] All predictions still pending.")

    except Exception as e:
        print(f"   [CRITICAL] Outcome review failed: {e}")


async def run_accuracy_generation():
    """
    Aggregates performance metrics from predictions.csv for the last 24h.
    Logs to audit_log.csv and upserts to Supabase 'accuracy_reports'.
    """
    import uuid
    if not os.path.exists(PREDICTIONS_CSV):
        return

    print("\n   [ACCURACY] Generating performance metrics (Last 24h)...")
    try:
        df = pd.read_csv(PREDICTIONS_CSV, dtype=str).fillna('')
        if df.empty:
            print("   [ACCURACY] No predictions found.")
            return

        # 1. Date Filter (Last 24h)
        lagos_tz = pytz.timezone('Africa/Lagos')
        now_lagos = dt.now(lagos_tz)
        yesterday_lagos = now_lagos - timedelta(days=1)

        def parse_updated(ts):
            try:
                dt_obj = pd.to_datetime(ts)
                if dt_obj.tzinfo is None:
                    return lagos_tz.localize(dt_obj)
                return dt_obj.astimezone(lagos_tz)
            except:
                return pd.NaT

        df['updated_dt'] = df['last_updated'].apply(parse_updated)
        df_24h = df[(df['updated_dt'] >= yesterday_lagos) & (df['status'].isin(['reviewed', 'finished']))].copy()

        if df_24h.empty:
            print("   [ACCURACY] No predictions reviewed in the last 24h.")
            return

        # 2. Aggregates
        volume = len(df_24h)
        correct_count = (df_24h['outcome_correct'] == '1').sum()
        win_rate = (correct_count / volume) * 100 if volume > 0 else 0

        # Return Calculation
        total_return = 0
        for _, row in df_24h.iterrows():
            try:
                odds = float(row.get('odds', 0))
                if odds <= 0: odds = 2.0
                if row['outcome_correct'] == '1':
                    total_return += (odds - 1)
                else:
                    total_return -= 1
            except:
                pass
        
        return_pct = (total_return / volume) * 100 if volume > 0 else 0

        # 3. Persistence
        report_id = str(uuid.uuid4())[:8]
        report_row = {
            'report_id': report_id,
            'timestamp': now_lagos.isoformat(),
            'volume': str(volume),
            'win_rate': f"{win_rate:.2f}",
            'return_pct': f"{return_pct:.2f}",
            'period': 'last_24h',
            'last_updated': now_lagos.isoformat()
        }
        
        upsert_entry(ACCURACY_REPORTS_CSV, report_row, files_and_headers[ACCURACY_REPORTS_CSV], 'report_id')
        log_audit_event('ACCURACY_REPORT', f"Metrics: Vol={volume}, WR={win_rate:.1f}%, ROI={return_pct:.1f}%")

        # 4. Sync
        sync = SyncManager()
        if sync.supabase:
            await sync.batch_upsert('accuracy_reports', [report_row])

    except Exception as e:
        print(f"   [ACCURACY ERROR] {e}")


async def start_review():
    """Legacy entry point."""
    await run_review_process()


