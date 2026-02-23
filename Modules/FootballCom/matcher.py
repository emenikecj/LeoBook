# matcher.py: matcher.py: Multi-stage team name matching logic.
# Part of LeoBook Modules — Football.com
#
# Functions: filter_pending_predictions(), normalize_team_name(), calculate_similarity(), build_match_string(), parse_match_datetime(), match_predictions_with_site()

"""
Matcher Module
Handles matching predictions.csv data with extracted Football.com matches using Leo AI.
"""

import csv
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from Data.Access.db_helpers import PREDICTIONS_CSV, update_prediction_status
from Core.Intelligence.unified_matcher import UnifiedBatchMatcher


async def filter_pending_predictions() -> List[Dict]:
    """Load and filter predictions that are pending booking."""
    pending_predictions = []
    csv_path = Path(PREDICTIONS_CSV)
    if csv_path.exists():
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # v2.8: Pick 'pending' and 'failed_harvest' (to allow retries).
            # Statuses like 'no_site_match', 'added_to_slip', 'booked' are skipped.
            pending_predictions = [row for row in reader if row.get('status') in ['pending', 'failed_harvest']]
    print(f"  [Matcher] Found {len(pending_predictions)} pending predictions.")
    return pending_predictions





def parse_match_datetime(date_str: str, time_str: str, is_site_format: bool = False) -> Optional[datetime]:
    """
    Parse date and time strings into a datetime object (assumed UTC for predictions, displayed UTC+1 for site).
    """
    if not date_str or not time_str:
        return None

    time_str = time_str.strip()
    date_str = date_str.strip()

    if is_site_format:
        # Site time_str can be "14:00", "Live", "45'", or "17 Dec, 20:30"
        try:
            # Case 1: "17 Dec, 20:30"
            if ',' in time_str:
                parts = time_str.split(',', 1)
                site_date_part = parts[0].strip()   # e.g. "17 Dec"
                site_time_part = parts[1].strip()   # e.g. "20:30"
                
                # Try to parse the date part to get day and month
                # Football.com uses "17 Dec"
                dt_site_date = datetime.strptime(site_date_part, "%d %b")
                dt_site_time = datetime.strptime(site_time_part, "%H:%M")
                
                # Use year from date_str (targetDate)
                target_year = datetime.strptime(date_str, "%d.%m.%Y").year
                return datetime(target_year, dt_site_date.month, dt_site_date.day, dt_site_time.hour, dt_site_time.minute)

            # Case 2: "14:00"
            if ':' in time_str:
                dt_time = datetime.strptime(time_str.strip(), "%H:%M")
                dt_date = datetime.strptime(date_str, "%d.%m.%Y")
                return datetime(dt_date.year, dt_date.month, dt_date.day, dt_time.hour, dt_time.minute)

            # Case 3: "Live", "45'", etc. (Treat as "now" on the target date)
            dt_date = datetime.strptime(date_str, "%d.%m.%Y")
            return datetime(dt_date.year, dt_date.month, dt_date.day, datetime.now().hour, datetime.now().minute)

        except Exception as e:
            # print(f"    [Time Parse Error] Failed to parse site time '{time_str}' with date '{date_str}': {e}")
            return None
    else:
        try:
            return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        except ValueError:
            return None




async def match_predictions_with_site(day_predictions: List[Dict], site_matches: List[Dict]) -> Dict[str, str]:
    """
    Match predictions to site matches using the Advanced Unified AI Batch Matcher (v2.8).
    Resolves all matches for a date in a single AI call with Grok/Gemini rotation.
    """
    if not day_predictions or not site_matches:
        return {}

    # Extract target date from the first prediction (safely)
    target_date = day_predictions[0].get('date')
    print(f"  [Matcher] Starting Unified AI Batch Match for {target_date}...")
    print(f"  [Matcher] Input: {len(day_predictions)} predictions and {len(site_matches)} site candidates.")

    # Initialize batch matcher
    matcher = UnifiedBatchMatcher()
    
    # 1. Load Existing Matches (Persistence Check)
    from Data.Access.db_helpers import load_site_matches
    existing_matches = load_site_matches(target_date)
    
    # Filter out predictions that are already matched
    unmatched_predictions = []
    mapping = {} # Start with existing mappings
    
    for pred in day_predictions:
        fid = str(pred.get('fixture_id'))
        # Check if this fixture ID exists in our DB for this date with a valid URL
        existing = next((m for m in existing_matches if str(m.get('fixture_id')) == fid and m.get('url')), None)
        if existing:
            mapping[fid] = existing.get('url')
        else:
            unmatched_predictions.append(pred)
            
    if mapping:
        print(f"  [Matcher] Found {len(mapping)} matches already cached in DB. Skipping AI for these.")

    if not unmatched_predictions:
        print("  [Matcher] All matches already resolved via cache. Skipping AI call.")
        return mapping

    print(f"  [Matcher] Sending {len(unmatched_predictions)} remaining predictions to AI...")

    # Execute batch matching
    try:
        new_mapping = await matcher.match_batch(target_date, unmatched_predictions, site_matches)
        if new_mapping:
            mapping.update(new_mapping)
        
        # PERSISTENCE: Identify predictions that AI could NOT match
        # We only do this if we actually had site candidates.
        if site_matches:
            for pred in unmatched_predictions:
                fid = str(pred.get('fixture_id'))
                if fid not in new_mapping:
                    # Mark as 'no_site_match' so we don't bother AI again for this date
                    print(f"    [Matcher] Fixture {fid} ({pred.get('home_team')} vs {pred.get('away_team')}) -> no_site_match")
                    update_prediction_status(fid, target_date, 'no_site_match')
        
        # Verify and log results
        matched_count = len(mapping)
        print(f"  [Matcher] Batch matching complete: {matched_count}/{len(day_predictions)} matches resolved.")
        
        return mapping
    except Exception as e:
        print(f"  [Matcher Error] Unified batch matching failed: {e}")
        return mapping # Return partial results if we had cache hits
