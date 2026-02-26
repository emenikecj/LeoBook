# db_helpers.py: db_helpers.py: High-level database access layers for LeoBook.
# Part of LeoBook Data — Access Layer
#
# Functions: init_csvs(), log_audit_event(), save_prediction(), update_prediction_status(), backfill_prediction_entry(), save_schedule_entry(), save_live_score_entry(), save_standings() (+12 more)

"""
Database Helpers Module
High-level database operations for managing match data and predictions.
Responsible for saving predictions, schedules, standings, teams, and region-leagues.
"""

import os
import csv
import json
import sys
from datetime import datetime as dt
from typing import Dict, Any, List, Optional
import uuid
import asyncio

# Global lock for synchronizing CSV access across async tasks
CSV_LOCK = asyncio.Lock()

# Increase CSV field size limit to handle large strings (e.g. HTML/JSON blobs)
csv.field_size_limit(sys.maxsize)


# ─── Low-level CSV operations (previously csv_operations.py) ───

def _read_csv(filepath: str) -> List[Dict[str, str]]:
    """Safely reads a CSV file into a list of dictionaries."""
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return []
    try:
        with open(filepath, 'r', newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"    [File Error] Could not read {filepath}: {e}")
        return []

def _append_to_csv(filepath: str, data_row: Dict, fieldnames: List[str]):
    """Safely appends a single dictionary row to a CSV file."""
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    try:
        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_row)
    except Exception as e:
        print(f"    [File Error] Failed to write to {filepath}: {e}")

append_to_csv = _append_to_csv  # Alias for external use

def _write_csv(filepath: str, data: List[Dict], fieldnames: List[str]):
    """Safely writes a list of dictionaries to a CSV file, overwriting it."""
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
    except Exception as e:
        print(f"    [File Error] Failed to write to {filepath}: {e}")

def upsert_entry(filepath: str, data_row: Dict, fieldnames: List[str], unique_key: str):
    """Performs a robust UPSERT (Update or Insert) operation on a CSV file."""
    unique_id = data_row.get(unique_key)
    if not unique_id:
        print(f"    [DB UPSERT Warning] Skipping entry due to missing unique key '{unique_key}'.")
        return

    all_rows = _read_csv(filepath)
    updated = False
    for row in all_rows:
        if row.get(unique_key) == unique_id:
            row.update(data_row)
            updated = True
            break
    if not updated:
        all_rows.append(data_row)
    _write_csv(filepath, all_rows, fieldnames)

def batch_upsert(filepath: str, data_rows: List[Dict], fieldnames: List[str], unique_key: str):
    """Batch UPSERT: reads once, updates/inserts all in memory, writes once.
    Rejects rows with empty/None unique keys to prevent ghost entries."""
    if not data_rows:
        return
    all_rows = _read_csv(filepath)
    # Clean existing rows: remove any with empty unique key (historical ghost rows)
    all_rows = [r for r in all_rows if r.get(unique_key)]
    index = {}
    for i, row in enumerate(all_rows):
        key = row.get(unique_key)
        if key:
            index[key] = i
    new_rows = []
    skipped = 0
    for data_row in data_rows:
        uid = data_row.get(unique_key)
        if not uid:
            skipped += 1
            continue
        if uid in index:
            all_rows[index[uid]].update(data_row)
        else:
            new_rows.append(data_row)
    all_rows.extend(new_rows)
    if skipped:
        print(f"    [DB UPSERT] Skipped {skipped} rows with empty '{unique_key}'.")
    _write_csv(filepath, all_rows, fieldnames)

# --- Async Shared Lock versions for Concurrency ---

async def async_read_csv(filepath: str) -> List[Dict[str, str]]:
    """Thread-safe async read of a CSV file."""
    async with CSV_LOCK:
        return _read_csv(filepath)

async def async_write_csv(filepath: str, data: List[Dict], fieldnames: List[str]):
    """Thread-safe async write of a CSV file."""
    async with CSV_LOCK:
        _write_csv(filepath, data, fieldnames)

async def async_batch_upsert(filepath: str, data_rows: List[Dict], fieldnames: List[str], unique_key: str):
    """Thread-safe async batch UPSERT."""
    async with CSV_LOCK:
        batch_upsert(filepath, data_rows, fieldnames, unique_key)

# --- Data Store Paths ---
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, "..", ".."))
DB_DIR = os.path.join(_project_root, "Data", "Store")
PREDICTIONS_CSV = os.path.join(DB_DIR, "predictions.csv")
SCHEDULES_CSV = os.path.join(DB_DIR, "schedules.csv")
STANDINGS_CSV = os.path.join(DB_DIR, "standings.csv")
TEAMS_CSV = os.path.join(DB_DIR, "teams.csv")
REGION_LEAGUE_CSV = os.path.join(DB_DIR, "region_league.csv")
ACCURACY_REPORTS_CSV = os.path.join(DB_DIR, "accuracy_reports.csv")
FB_MATCHES_CSV = os.path.join(DB_DIR, "fb_matches.csv")
MATCH_REGISTRY_CSV = FB_MATCHES_CSV  # Alias for URL resolution
AUDIT_LOG_CSV = os.path.join(DB_DIR, "audit_log.csv")
PROFILES_CSV = os.path.join(DB_DIR, "profiles.csv")
CUSTOM_RULES_CSV = os.path.join(DB_DIR, "custom_rules.csv")
RULE_EXECUTIONS_CSV = os.path.join(DB_DIR, "rule_executions.csv")
LIVE_SCORES_CSV = os.path.join(DB_DIR, "live_scores.csv")


def init_csvs():
    """Initializes all CSV database files."""
    print("     Initializing databases...")
    os.makedirs(DB_DIR, exist_ok=True)

    files_to_init = files_and_headers.copy()
    for filepath, headers in files_to_init.items():
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            print(f"    [Init] Creating {os.path.basename(filepath)}...")
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

def log_audit_event(event_type: str, description: str, balance_before: Optional[float] = None, balance_after: Optional[float] = None, stake: Optional[float] = None, status: str = 'success'):
    """Logs a financial or system event to audit_log.csv."""
    row = {
        'id': str(uuid.uuid4()),
        'timestamp': dt.now().strftime("%Y-%m-%d %H:%M:%S"),
        'event_type': event_type,
        'description': description,
        'balance_before': balance_before if balance_before is not None else '',
        'balance_after': balance_after if balance_after is not None else '',
        'stake': stake if stake is not None else '',
        'status': status
    }
    _append_to_csv(AUDIT_LOG_CSV, row, ['id', 'timestamp', 'event_type', 'description', 'balance_before', 'balance_after', 'stake', 'status'])

def save_prediction(match_data: Dict[str, Any], prediction_result: Dict[str, Any]):
    """UPSERTs a prediction into the predictions.csv file."""
    fixture_id = match_data.get('fixture_id') or match_data.get('id')
    if not fixture_id or fixture_id == 'unknown':
        print(f"   [Warning] Skipping prediction save: Missing unique fixture_id for {match_data.get('home_team')} v {match_data.get('away_team')}")
        return

    date = match_data.get('date', dt.now().strftime("%d.%m.%Y"))

    new_row_data = {
        'fixture_id': fixture_id,
        'date': date,
        'match_time': match_data.get('match_time') or match_data.get('time', '00:00'),
        'region_league': match_data.get('region_league', 'Unknown'),
        'home_team': match_data.get('home_team', 'Unknown'),
        'away_team': match_data.get('away_team', 'Unknown'),
        'home_team_id': match_data.get('home_team_id', 'unknown'),
        'away_team_id': match_data.get('away_team_id', 'unknown'),
        'prediction': prediction_result.get('type', 'SKIP'),
        'confidence': prediction_result.get('confidence', 'Low'),
        'reason': " | ".join(prediction_result.get('reason', [])),
        'xg_home': str(prediction_result.get('xg_home', 0.0)),
        'xg_away': str(prediction_result.get('xg_away', 0.0)),
        'btts': prediction_result.get('btts', '50/50'),
        'over_2.5': prediction_result.get('over_2.5', '50/50'),
        'best_score': prediction_result.get('best_score', '1-1'),
        'top_scores': "|".join([f"{s['score']}({s['prob']})" for s in prediction_result.get('top_scores', [])]),
        'home_tags': "|".join(prediction_result.get('home_tags', [])),
        'away_tags': "|".join(prediction_result.get('away_tags', [])),
        'h2h_tags': "|".join(prediction_result.get('h2h_tags', [])),
        'standings_tags': "|".join(prediction_result.get('standings_tags', [])),
        'h2h_count': str(prediction_result.get('h2h_n', 0)),
        'home_form_n': str(prediction_result.get('home_form_n', 0)),
        'away_form_n': str(prediction_result.get('away_form_n', 0)),
        'generated_at': dt.now().isoformat(),
        'status': 'pending',
        'match_link': f"{match_data.get('match_link', '')}",
        'odds': str(prediction_result.get('odds', '')),
        'market_reliability_score': str(prediction_result.get('market_reliability', 0.0)),
        'home_crest_url': get_team_crest(match_data.get('home_team_id'), match_data.get('home_team')),
        'away_crest_url': get_team_crest(match_data.get('away_team_id'), match_data.get('away_team')),
        'recommendation_score': str(prediction_result.get('recommendation_score', 0)),
        'h2h_fixture_ids': json.dumps(prediction_result.get('h2h_fixture_ids', [])),
        'form_fixture_ids': json.dumps(prediction_result.get('form_fixture_ids', [])),
        'standings_snapshot': json.dumps(prediction_result.get('standings_snapshot', [])),
        'league_stage': match_data.get('league_stage', ''),
        'last_updated': dt.now().isoformat()
    }

    upsert_entry(PREDICTIONS_CSV, new_row_data, files_and_headers[PREDICTIONS_CSV], 'fixture_id')

def update_prediction_status(match_id: str, date: str, new_status: str, **kwargs):
    """
    Updates the status and optional fields (like odds or booking_code) in predictions.csv.
    """
    if not os.path.exists(PREDICTIONS_CSV):
        return

    rows = []
    updated = False
    try:
        with open(PREDICTIONS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('fixture_id') == match_id and row.get('date') == date:
                    row['status'] = new_status
                    row['last_updated'] = dt.now().isoformat()
                    for key, value in kwargs.items():
                        if key in row:
                            row[key] = value
                    updated = True
                rows.append(row)

        if updated and fieldnames is not None:
            _write_csv(PREDICTIONS_CSV, rows, list(fieldnames))
    except Exception as e:
        print(f"    [Warning] Failed to update status for {match_id}: {e}")

def backfill_prediction_entry(fixture_id: str, updates: Dict[str, str]):
    """
    Partially updates an existing prediction row without overwriting analysis data.
    Only updates fields that are currently empty, 'Unknown', or 'N/A'.
    """
    if not fixture_id or not updates:
        return False

    if not os.path.exists(PREDICTIONS_CSV):
        return False

    rows = []
    updated = False
    try:
        with open(PREDICTIONS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('fixture_id') == fixture_id:
                    for key, value in updates.items():
                        if key in row and value:
                            current = row[key].strip() if row[key] else ''
                            if not current or current in ('Unknown', 'N/A', 'unknown'):
                                row[key] = value
                                row['last_updated'] = dt.now().isoformat()
                                updated = True
                    rows.append(row)
                else:
                    rows.append(row)

        if updated and fieldnames is not None:
            _write_csv(PREDICTIONS_CSV, rows, list(fieldnames))
    except Exception as e:
        print(f"    [Warning] Failed to backfill prediction {fixture_id}: {e}")

    return updated

def save_schedule_entry(match_info: Dict[str, Any]):
    # Ensure last_updated is present
    match_info['last_updated'] = dt.now().isoformat()

    upsert_entry(SCHEDULES_CSV, match_info, files_and_headers[SCHEDULES_CSV], 'fixture_id')

def save_live_score_entry(match_info: Dict[str, Any]):
    """Saves or updates a live score entry in live_scores.csv."""
    match_info['last_updated'] = dt.now().isoformat()
    upsert_entry(LIVE_SCORES_CSV, match_info, files_and_headers[LIVE_SCORES_CSV], 'fixture_id')

def save_standings(standings_data: List[Dict[str, Any]], region_league: str, league_id: str = ""):
    """UPSERTs standings data for a specific league in standings.csv."""
    if not standings_data: return

    last_updated = dt.now().isoformat()
    updated_count = 0

    for row in standings_data:
        row['region_league'] = region_league or row.get('region_league', 'Unknown')
        row['last_updated'] = last_updated
        
        t_id = row.get('team_id', '')
        l_id = league_id or row.get('league_id', '')
        if not l_id and region_league and " - " in region_league:
             l_id = region_league.split(" - ")[1].replace(' ', '_').upper()
        row['league_id'] = l_id

        # Unique key is league_id + team_id
        if t_id and l_id:
            row['standings_key'] = f"{l_id}_{t_id}".upper()
            upsert_entry(STANDINGS_CSV, row, files_and_headers[STANDINGS_CSV], 'standings_key')
            updated_count += 1

    if updated_count > 0:
        print(f"      [DB] UPSERTed {updated_count} standings entries for {region_league or league_id}")

def _standardize_url(url: str, base_type: str = "flashscore") -> str:
    """Ensures URLs are absolute and follow standard patterns."""
    if not url or url == 'N/A' or url.startswith("data:"):
        return url
    
    # Handle relative URLs
    if url.startswith("/"):
        url = f"https://www.flashscore.com{url}"
    
    # Standardize team URLs: https://www.flashscore.com/team/{slug}/{id}/
    if "/team/" in url and "https://www.flashscore.com/team/" not in url:
        clean_path = url.split("team/")[-1].strip("/")
        url = f"https://www.flashscore.com/team/{clean_path}/"
    elif "/team/" in url:
        # Ensure trailing slash for team URLs
        if not url.endswith("/"): url += "/"

    # Standardize league/region URLs: ensure absolute
    if "flashscore.com" not in url and not url.startswith("http"):
        url = f"https://www.flashscore.com{url if url.startswith('/') else '/' + url}"

    return url

def save_region_league_entry(info: Dict[str, Any]):
    """Saves or updates a single region-league entry in region_league.csv."""
    league_id = info.get('league_id')
    
    # Validation: league_id should preferentially be the fragment hash if available
    region = info.get('region', 'Unknown')
    league = info.get('league', 'Unknown')
    if not league_id:
        league_id = f"{region}_{league}".replace(' ', '_').replace('-', '_').upper()

    entry = {
        'league_id': league_id,
        'region': region,
        'region_flag': _standardize_url(info.get('region_flag', '')),
        'region_url': _standardize_url(info.get('region_url', '')),
        'league': league,
        'league_crest': _standardize_url(info.get('league_crest', '')),
        'league_url': _standardize_url(info.get('league_url', '')),
        'date_updated': dt.now().isoformat(),
        'last_updated': dt.now().isoformat()
    }

    upsert_entry(REGION_LEAGUE_CSV, entry, files_and_headers[REGION_LEAGUE_CSV], 'league_id')


def save_team_entry(team_info: Dict[str, Any]):
    """Saves or updates a single team entry in teams.csv with multi-league support."""
    team_id = team_info.get('team_id')
    if not team_id or team_id == 'unknown': return

    # Check for existing entry to merge league_ids
    existing_rows = _read_csv(TEAMS_CSV)
    new_league_id = team_info.get('league_ids', team_info.get('region_league', ''))
    
    merged_league_ids = new_league_id
    for row in existing_rows:
        if row.get('team_id') == team_id:
            existing_league_ids = row.get('league_ids', '').split(';')
            if new_league_id and new_league_id not in existing_league_ids:
                existing_league_ids.append(new_league_id)
            merged_league_ids = ';'.join(filter(None, existing_league_ids))
            break

    entry = {
        'team_id': team_id,
        'team_name': team_info.get('team_name', 'Unknown'),
        'league_ids': merged_league_ids,
        'team_crest': _standardize_url(team_info.get('team_crest', '')),
        'team_url': _standardize_url(team_info.get('team_url', '')),
        'last_updated': dt.now().isoformat()
    }

    upsert_entry(TEAMS_CSV, entry, files_and_headers[TEAMS_CSV], 'team_id')

def get_team_crest(team_id: str, team_name: str = "") -> str:
    """Retrieves the crest URL for a team from teams.csv."""
    if not os.path.exists(TEAMS_CSV):
        return ""
    
    rows = _read_csv(TEAMS_CSV)
    for row in rows:
        if str(row.get('team_id')) == str(team_id) or (team_name and row.get('team_name') == team_name):
            return row.get('team_crest', '')
    return ""

# --- Football.com Registry Helpers ---

def get_site_match_id(date: str, home: str, away: str) -> str:
    """Generate a unique ID for a site match to prevent duplicates."""
    import hashlib
    unique_str = f"{date}_{home}_{away}".lower().strip()
    return hashlib.md5(unique_str.encode()).hexdigest()

def save_site_matches(matches: List[Dict[str, Any]]):
    """UPSERTs a list of matches extracted from Football.com into the registry."""
    if not matches: return
    
    headers = files_and_headers[FB_MATCHES_CSV]
    last_extracted = dt.now().isoformat()
    
    for match in matches:
        site_id = get_site_match_id(match.get('date', ''), match.get('home', ''), match.get('away', ''))
        row = {
            'site_match_id': site_id,
            'date': match.get('date'),
            'time': match.get('time', 'N/A'),
            'home_team': match.get('home'),
            'away_team': match.get('away'),
            'league': match.get('league'),
            'url': match.get('url'),
            'last_extracted': last_extracted,
            'fixture_id': match.get('fixture_id', ''),
            'matched': match.get('matched', 'No_fs_match_found'),
            'booking_status': match.get('booking_status', 'pending'),
            'booking_details': match.get('booking_details', ''),
            'booking_code': match.get('booking_code', ''),
            'booking_url': match.get('booking_url', ''),
            'status': match.get('status', ''),
            'last_updated': dt.now().isoformat()
        }
        upsert_entry(FB_MATCHES_CSV, row, headers, 'site_match_id')

def load_site_matches(target_date: str) -> List[Dict[str, Any]]:
    """Loads all extracted site matches for a specific date."""
    if not os.path.exists(FB_MATCHES_CSV):
        return []
    
    all_matches = _read_csv(FB_MATCHES_CSV)
    return [m for m in all_matches if m.get('date') == target_date]

def load_harvested_site_matches(target_date: str) -> List[Dict[str, Any]]:
    """Loads all harvested site matches for a specific date (v2.7)."""
    if not os.path.exists(FB_MATCHES_CSV):
        return []
    
    all_matches = _read_csv(FB_MATCHES_CSV)
    return [m for m in all_matches if m.get('date') == target_date and m.get('booking_status') == 'harvested']

def update_site_match_status(site_match_id: str, status: str, fixture_id: Optional[str] = None, details: Optional[str] = None, booking_code: Optional[str] = None, booking_url: Optional[str] = None, matched: Optional[str] = None, **kwargs):
    """Updates the booking status, fixture_id, or booking details for a site match."""
    if not os.path.exists(FB_MATCHES_CSV):
        return

    rows = []
    updated = False
    try:
        with open(FB_MATCHES_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('site_match_id') == site_match_id:
                    row['booking_status'] = status
                    if fixture_id: row['fixture_id'] = fixture_id
                    if details: row['booking_details'] = details
                    if booking_code: row['booking_code'] = booking_code
                    if booking_url: row['booking_url'] = booking_url
                    if status: row['status'] = status
                    if matched: row['matched'] = matched
                    if 'odds' in kwargs: row['odds'] = kwargs['odds']
                    updated = True
                rows.append(row)

        if updated and fieldnames is not None:
            _write_csv(FB_MATCHES_CSV, rows, list(fieldnames))
    except Exception as e:
        print(f"    [DB Error] Failed to update site match status: {e}")

def get_last_processed_info() -> Dict:
    """Loads last processed match info once at the start."""
    last_processed_info = {}
    if os.path.exists(PREDICTIONS_CSV):
        try:
            all_predictions = _read_csv(PREDICTIONS_CSV)
            if all_predictions:
                last_prediction = all_predictions[-1]
                date_str = last_prediction.get('date')
                if date_str:
                    last_processed_info = {
                        'date': date_str,
                        'id': last_prediction.get('fixture_id'),
                        'date_obj': dt.strptime(date_str, "%d.%m.%Y").date()
                    }
                    print(f"    [Resume] Last processed: ID {last_processed_info['id']} on {last_processed_info['date']}")
        except Exception as e:
            print(f"    [Warning] Could not read CSV for resume check: {e}")
    return last_processed_info

def get_all_schedules() -> List[Dict[str, Any]]:
    """Loads all match schedules from schedules.csv."""
    return _read_csv(SCHEDULES_CSV)

def get_standings(region_league: str) -> List[Dict[str, Any]]:
    """Loads standings for a specific league from standings.csv."""
    all_standings = _read_csv(STANDINGS_CSV)
    return [s for s in all_standings if s.get('region_league') == region_league]

def evaluate_market_outcome(prediction: str, home_score: str, away_score: str, home_team: str = "", away_team: str = "") -> Optional[str]:
    """
    Unified First-Principles Outcome Evaluator (v3.0).
    Returns '1' (Correct), '0' (Incorrect), or '' (Unknown/Void).
    Handles both market types (Over 2.5) and team-specific predictions (Arsenal to win).
    """
    import re
    try:
        h = int(home_score)
        a = int(away_score)
        total = h + a
    except (ValueError, TypeError):
        return ''

    p = (prediction or '').strip().lower()
    h_lower = (home_team or '').strip().lower()
    a_lower = (away_team or '').strip().lower()

    # 1. Standard Markets (Short Code/Explicit)
    if p in ("over 2.5", "over 2_5", "over_2.5", "over_2_5"): return '1' if total > 2.5 else '0'
    if p in ("under 2.5", "under 2_5", "under_2.5", "under_2_5"): return '1' if total < 2.5 else '0'
    if p in ("btts yes", "btts_yes", "both teams to score yes"): return '1' if h > 0 and a > 0 else '0'
    if p in ("btts no", "btts_no", "both teams to score no"): return '1' if h == 0 or a == 0 else '0'
    if p in ("home win", "home_win", "1"): return '1' if h > a else '0'
    if p in ("away win", "away_win", "2"): return '1' if a > h else '0'
    if p in ("draw", "x"): return '1' if h == a else '0'

    # 2. "Team to win" / "Team or Draw" (Verbose Patterns)
    if p.endswith(" to win"):
        team = p.replace(" to win", "").strip()
        if team == h_lower: return '1' if h > a else '0'
        if team == a_lower: return '1' if a > h else '0'
    
    if " or draw" in p:
        team = p.replace(" or draw", "").strip()
        if team == h_lower or team == '1': return '1' if h >= a else '0'
        if team == a_lower or team == '2': return '1' if a >= h else '0'

    if p.endswith(" (dnb)"):
        team = p.replace(" to win (dnb)", "").replace(" (dnb)", "").strip()
        if h == a: return '' # Void/Refund
        if team == h_lower: return '1' if h > a else '0'
        if team == a_lower: return '1' if a > h else '0'

    # 3. Dynamic Regex Patterns (Over/Under X, Team Over X)
    over_match = re.search(r'over\s+([\d.]+)', p)
    if over_match:
        threshold = float(over_match.group(1))
        if "away" in p: return '1' if a > threshold else '0'
        if "home" in p: return '1' if h > threshold else '0'
        return '1' if total > threshold else '0'

    under_match = re.search(r'under\s+([\d.]+)', p)
    if under_match:
        threshold = float(under_match.group(1))
        if "away" in p: return '1' if a < threshold else '0'
        if "home" in p: return '1' if h < threshold else '0'
        return '1' if total < threshold else '0'

    # 4. Clean Sheet / No Draw
    if "clean sheet" in p:
        team = p.replace(" clean sheet", "").strip()
        if team == h_lower: return '1' if a == 0 else '0'
        if team == a_lower: return '1' if h == 0 else '0'
    
    if p in ("home or away", "12", "double chance 12"): return '1' if h != a else '0'

    return ''

# To be accessible from other modules, we need to define the headers dict here
files_and_headers = {
    PREDICTIONS_CSV: [
        'fixture_id', 'date', 'match_time', 'region_league', 'home_team', 'away_team', 
        'home_team_id', 'away_team_id', 'prediction', 'confidence', 'reason', 'xg_home', 
        'xg_away', 'btts', 'over_2.5', 'best_score', 'top_scores', 'home_form_n', 
        'away_form_n', 'home_tags', 'away_tags', 'h2h_tags', 'standings_tags', 
        'h2h_count', 'actual_score', 'outcome_correct', 
        'status', 'match_link', 'odds', 'market_reliability_score',
        'home_crest_url', 'away_crest_url', 'recommendation_score',
        'h2h_fixture_ids', 'form_fixture_ids', 'standings_snapshot',
        'league_stage', 'last_updated'
    ],
    SCHEDULES_CSV: [
        'fixture_id', 'date', 'match_time', 'region_league', 'league_id',
        'home_team', 'away_team', 'home_team_id', 'away_team_id',
        'home_score', 'away_score', 'match_status', 
        'match_link', 'league_stage', 'last_updated'
    ],
    STANDINGS_CSV: [
        'standings_key', 'league_id', 'team_id', 'team_name', 'position', 'played', 'wins', 'draws',
        'losses', 'goals_for', 'goals_against', 'goal_difference', 'points', 
        'last_updated', 'region_league'
    ],
    TEAMS_CSV: ['team_id', 'team_name', 'league_ids', 'team_crest', 'team_url', 'last_updated', 'country', 'city', 'stadium', 'other_names', 'abbreviations', 'search_terms'],
    REGION_LEAGUE_CSV: ['league_id', 'region', 'region_flag', 'region_url', 'league', 'league_crest', 'league_url', 'date_updated', 'last_updated', 'other_names', 'abbreviations', 'search_terms'],
    ACCURACY_REPORTS_CSV: ['report_id', 'timestamp', 'volume', 'win_rate', 'return_pct', 'period', 'last_updated'],
    FB_MATCHES_CSV: [
        'site_match_id', 'date', 'time', 'home_team', 'away_team', 'league', 'url', 
        'last_extracted', 'fixture_id', 'matched', 'odds', 'booking_status', 'booking_details',
        'booking_code', 'booking_url', 'status', 'last_updated'
    ],
    AUDIT_LOG_CSV: [
        'id', 'timestamp', 'event_type', 'description', 'balance_before', 'balance_after', 'stake', 'status'
    ],
    # User & Rule Engine Tables
    os.path.join(DB_DIR, "profiles.csv"): [
        'id', 'email', 'username', 'full_name', 'avatar_url', 'tier', 'credits', 'created_at', 'updated_at', 'last_updated'
    ],
    os.path.join(DB_DIR, "custom_rules.csv"): [
        'id', 'user_id', 'name', 'description', 'is_active', 'logic', 'priority', 'created_at', 'updated_at', 'last_updated'
    ],
    os.path.join(DB_DIR, "rule_executions.csv"): [
        'id', 'rule_id', 'fixture_id', 'user_id', 'result', 'executed_at', 'last_updated'
    ],
    LIVE_SCORES_CSV: [
        'fixture_id', 'home_team', 'away_team', 'home_score', 'away_score',
        'minute', 'status', 'region_league', 'match_link', 'timestamp', 'last_updated'
    ]
}
