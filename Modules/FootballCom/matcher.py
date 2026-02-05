# matcher.py: Multi-stage team name matching logic.
# Refactored for Clean Architecture (v2.7)
# This script combines difflib and LLM matching to resolve fixture URLs.

"""
Matcher Module
Handles matching predictions.csv data with extracted Football.com matches using Leo AI.
"""

import csv
import difflib
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from pathlib import Path
from Data.Access.db_helpers import PREDICTIONS_CSV, update_prediction_status
# Import LLM matcher conditionally
try:
    import Core.Intelligence.llm_matcher as llm_module
    HAS_LLM = True
except ImportError:
    llm_module = None
    HAS_LLM = False
    print("  [Matcher] Warning: LLM dependencies not found. Falling back to simple fuzzy matching.")

# Import RapidFuzz for faster and more accurate fuzzy matching
try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    print("  [Matcher] Warning: RapidFuzz not found. Falling back to difflib.")


async def filter_pending_predictions() -> List[Dict]:
    """Load and filter predictions that are pending booking."""
    pending_predictions = []
    csv_path = Path(PREDICTIONS_CSV)
    if csv_path.exists():
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            pending_predictions = [row for row in reader if row.get('status') == 'pending']
    print(f"  [Matcher] Found {len(pending_predictions)} pending predictions.")
    return pending_predictions


def normalize_team_name(name: str) -> str:
    """Basic normalization: lower, strip, remove common suffixes/prefixes."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common suffixes like FC, AFC, CF, etc. and Brazilian state abbreviations
    suffixes = [
        'fc', 'afc', 'cf', 'sc', 'ac', 'club', 'united', 'city', 'athletic', 'fb',
        'sp', 'rj', 'mg', 'rs', 'pr', 'ba', 'ce', 'pe', 'go', 'sc', 'pb', 'rn', 'al', 'se', 'mt', 'ms', 'pa', 'am'
    ]
    for suffix in suffixes:
        if name.endswith(' ' + suffix):
            name = name[:-len(suffix)-1].strip()
        elif name.endswith(' ' + suffix + ')'): # handle (SP)
             name = name[:-len(suffix)-2].strip()
        elif name == suffix:
            name = ""
    return name


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity using RapidFuzz (token_set_ratio) or fallback to difflib."""
    if not str1 or not str2:
        return 0.0
    norm1 = normalize_team_name(str1)
    norm2 = normalize_team_name(str2)
    if HAS_RAPIDFUZZ:
        try:
            from rapidfuzz import fuzz
            return fuzz.token_set_ratio(norm1, norm2) / 100.0
        except ImportError:
            return difflib.SequenceMatcher(None, norm1, norm2).ratio()
    else:
        return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def build_match_string(region_league: str, home: str, away: str, date: str, time: str) -> str:
    """
    Build a canonical full match string for holistic comparison:
    "Region - League: Home Team vs Away Team - Date - Time"
    """
    return f"{region_league}: {home} vs {away} - {date} - {time}".strip().lower()


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


from Core.Intelligence.unified_matcher import UnifiedBatchMatcher

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
    
    # Execute batch matching
    try:
        mapping = await matcher.match_batch(target_date, day_predictions, site_matches)
        
        # Verify and log results
        matched_count = len(mapping)
        print(f"  [Matcher] Batch matching complete: {matched_count}/{len(day_predictions)} matches resolved.")
        
        # Log individual matches for visibility (Commented out for cleaner logs)
        # for fid, url in mapping.items():
        #     pred = next((p for p in day_predictions if str(p.get('fixture_id')) == fid), None)
        #     if pred:
        #         print(f"    [OK] AI Matched: {pred.get('home_team')} vs {pred.get('away_team')} -> {url}")

        return mapping
    except Exception as e:
        print(f"  [Matcher Error] Unified batch matching failed: {e}")
        return {}
