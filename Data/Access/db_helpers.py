# db_helpers.py: High-level database access layers for LeoBook.
# Refactored for Clean Architecture (v2.7)
# This script manages CSV initialization and structured data saving.

"""
Database Helpers Module
High-level database operations for managing match data and predictions.
Responsible for saving predictions, schedules, standings, teams, and region-leagues.
"""

import os
import csv
from datetime import datetime as dt
from typing import Dict, Any, List, Optional

from .csv_operations import _read_csv, _append_to_csv, _write_csv, upsert_entry

# --- Data Store Paths ---
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, "..", ".."))
DB_DIR = os.path.join(_project_root, "Data", "Store")
PREDICTIONS_CSV = os.path.join(DB_DIR, "predictions.csv")
SCHEDULES_CSV = os.path.join(DB_DIR, "schedules.csv")
STANDINGS_CSV = os.path.join(DB_DIR, "standings.csv")
TEAMS_CSV = os.path.join(DB_DIR, "teams.csv")
REGION_LEAGUE_CSV = os.path.join(DB_DIR, "region_league.csv")
FB_MATCHES_CSV = os.path.join(DB_DIR, "fb_matches.csv")
AUDIT_LOG_CSV = os.path.join(DB_DIR, "audit_log.csv")


def init_csvs():
    """Initializes all CSV database files."""
    print("     Initializing databases...")
    os.makedirs(DB_DIR, exist_ok=True)

    files_and_headers = {
        PREDICTIONS_CSV: [
            'fixture_id', 'date', 'match_time', 'region_league', 'home_team', 'away_team',
            'home_team_id', 'away_team_id', 'prediction', 'confidence', 'reason', 'xg_home',
            'xg_away', 'btts', 'over_2.5', 'best_score', 'top_scores', 'home_form_n',
            'away_form_n', 'home_tags', 'away_tags', 'h2h_tags', 'standings_tags',
            'h2h_count', 'form_count', 'actual_score', 'outcome_correct',
            'generated_at', 'status', 'match_link'
        ],
        SCHEDULES_CSV: [
            'fixture_id', 'date', 'match_time', 'region_league', 'home_team', 'away_team',
            'home_team_id', 'away_team_id', 'home_score', 'away_score', 'match_status', 'match_link'
        ],
        STANDINGS_CSV: [
            'region_league', 'position', 'team_name', 'team_id', 'played', 'wins', 'draws',
            'losses', 'goals_for', 'goals_against', 'goal_difference', 'points', 'last_updated', 'url', 'standings_key'
        ],
        TEAMS_CSV: ['team_id', 'team_name', 'region_league', 'team_url'],
    REGION_LEAGUE_CSV: ['region_league_id', 'region', 'league_name', 'url'],
        FB_MATCHES_CSV: [
            'site_match_id', 'date', 'time', 'home_team', 'away_team', 'league', 'url', 
            'last_extracted', 'fixture_id', 'matched', 'booking_status', 'booking_details',
            'booking_code', 'booking_url', 'status'
        ],
        AUDIT_LOG_CSV: [
            'timestamp', 'event_type', 'description', 'balance_before', 'balance_after', 'stake', 'status'
        ]
    }

    for filepath, headers in files_and_headers.items():
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            print(f"    [Init] Creating {os.path.basename(filepath)}...")
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

def log_audit_event(event_type: str, description: str, balance_before: Optional[float] = None, balance_after: Optional[float] = None, stake: Optional[float] = None, status: str = 'success'):
    """Logs a financial or system event to audit_log.csv."""
    row = {
        'timestamp': dt.now().strftime("%Y-%m-%d %H:%M:%S"),
        'event_type': event_type,
        'description': description,
        'balance_before': balance_before if balance_before is not None else '',
        'balance_after': balance_after if balance_after is not None else '',
        'stake': stake if stake is not None else '',
        'status': status
    }
    _append_to_csv(AUDIT_LOG_CSV, row, ['timestamp', 'event_type', 'description', 'balance_before', 'balance_after', 'stake', 'status'])

def save_prediction(match_data: Dict[str, Any], prediction_result: Dict[str, Any]):
    """UPSERTs a prediction into the predictions.csv file."""
    fixture_id = match_data.get('id', 'unknown')
    date = match_data.get('date', dt.now().strftime("%d.%m.%Y"))

    new_row_data = {
        'fixture_id': fixture_id,
        'date': date,
        'match_time': match_data.get('time', '00:00'),
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
        'match_link': f"{match_data.get('match_link', '')}"
    }

    upsert_entry(PREDICTIONS_CSV, new_row_data, files_and_headers[PREDICTIONS_CSV], 'fixture_id')

def update_prediction_status(match_id: str, date: str, new_status: str):
    """
    Updates the status of a specific prediction in the CSV.
    Finds the row by match_id and date, then rewrites the file.
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
                    updated = True
                rows.append(row)

        if updated and fieldnames is not None:
            _write_csv(PREDICTIONS_CSV, rows, list(fieldnames))
    except Exception as e:
        print(f"    [Warning] Failed to update status for {match_id}: {e}")

def save_schedule_entry(match_info: Dict[str, Any]):
    """Saves or updates a single match entry in schedules.csv."""
    fixture_id = match_info.get('fixture_id')
    if not fixture_id: return

    upsert_entry(SCHEDULES_CSV, match_info, files_and_headers[SCHEDULES_CSV], 'fixture_id')

def save_standings(standings_data: List[Dict[str, Any]], region_league: str):
    """UPSERTs standings data for a specific league in standings.csv."""
    if not standings_data or not region_league: return

    last_updated = dt.now().isoformat()
    updated_count = 0

    for row in standings_data:
        row['region_league'] = region_league
        row['last_updated'] = last_updated

        # Create composite unique key from region_league + team_name
        team_name = row.get('team_name', '').strip()
        if team_name:
            unique_key = f"{region_league}_{team_name}".replace(' ', '_').replace('-', '_').upper()
            row['standings_key'] = unique_key
            upsert_entry(STANDINGS_CSV, row, files_and_headers[STANDINGS_CSV], 'standings_key')
            updated_count += 1

    if updated_count > 0:
        print(f"      [DB] UPSERTed {updated_count} standings entries for {region_league}")

def save_region_league_entry(region_league_info: Dict[str, Any]):
    """Saves or updates a single region-league entry in region_league.csv."""
    region = region_league_info.get('region')
    league_name = region_league_info.get('league_name')

    # Create a composite ID from region + league
    region_league_id = f"{region}_{league_name}".replace(' ', '_').replace('-', '_').upper()

    entry = {
        'region_league_id': region_league_id,
        'region': region,
        'league_name': league_name
    }

    upsert_entry(REGION_LEAGUE_CSV, entry, files_and_headers[REGION_LEAGUE_CSV], 'region_league_id')


def save_team_entry(team_info: Dict[str, Any]):
    """Saves or updates a single team entry in teams.csv."""
    team_id = team_info.get('team_id')
    if not team_id or team_id == 'unknown': return

    upsert_entry(TEAMS_CSV, team_info, files_and_headers[TEAMS_CSV], 'team_id')

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
            'status': match.get('status', '')
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

def update_site_match_status(site_match_id: str, status: str, fixture_id: Optional[str] = None, details: Optional[str] = None, booking_code: Optional[str] = None, booking_url: Optional[str] = None, matched: Optional[str] = None):
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

# To be accessible from other modules, we need to define the headers dict here
files_and_headers = {
    PREDICTIONS_CSV: [
        'fixture_id', 'date', 'match_time', 'region_league', 'home_team', 'away_team', 
        'home_team_id', 'away_team_id', 'prediction', 'confidence', 'reason', 'xg_home', 
        'xg_away', 'btts', 'over_2.5', 'best_score', 'top_scores', 'home_form_n', 
        'away_form_n', 'home_tags', 'away_tags', 'h2h_tags', 'standings_tags', 
        'h2h_count', 'form_count', 'actual_score', 'outcome_correct', 
        'generated_at', 'status', 'match_link'
    ],
    SCHEDULES_CSV: [
        'fixture_id', 'date', 'match_time', 'region_league', 'home_team', 'away_team',
        'home_team_id', 'away_team_id', 'home_score', 'away_score', 'match_status', 'match_link'
    ],
    STANDINGS_CSV: [
        'region_league', 'position', 'team_name', 'team_id', 'played', 'wins', 'draws',
        'losses', 'goals_for', 'goals_against', 'goal_difference', 'points', 'last_updated', 'url', 'standings_key'
    ],
    TEAMS_CSV: ['team_id', 'team_name', 'region_league', 'team_url'],
    REGION_LEAGUE_CSV: ['region_league_id', 'region', 'league_name', 'url'],
    FB_MATCHES_CSV: [
        'site_match_id', 'date', 'time', 'home_team', 'away_team', 'league', 'url', 
        'last_extracted', 'fixture_id', 'matched', 'booking_status', 'booking_details',
        'booking_code', 'booking_url', 'status'
    ],
    AUDIT_LOG_CSV: [
        'timestamp', 'event_type', 'description', 'balance_before', 'balance_after', 'stake', 'status'
    ]
}
