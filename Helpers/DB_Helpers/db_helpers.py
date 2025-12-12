# Helpers/db_helpers.py

import os
import csv
from datetime import datetime as dt
from typing import Dict, Any, List, Optional

# --- CSV File Paths ---
DB_DIR = "DB"
PREDICTIONS_CSV = os.path.join(DB_DIR, "predictions.csv")
SCHEDULES_CSV = os.path.join(DB_DIR, "schedules.csv")
STANDINGS_CSV = os.path.join(DB_DIR, "standings.csv")
TEAMS_CSV = os.path.join(DB_DIR, "teams.csv")
REGION_LEAGUE_CSV = os.path.join(DB_DIR, "region_league.csv")


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
            'losses', 'goals_for', 'goals_against', 'goal_difference', 'points', 'last_updated', 'url'
        ],
        TEAMS_CSV: ['team_id', 'team_name', 'region_league', 'team_url'],
    REGION_LEAGUE_CSV: ['region_league_id', 'region', 'league_name', 'url']
    }

    for filepath, headers in files_and_headers.items():
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            print(f"    [Init] Creating {os.path.basename(filepath)}...")
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

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

def _write_csv(filepath: str, data: List[Dict], fieldnames: List[str]):
    """Safely writes a list of dictionaries to a CSV file, overwriting it."""
    # This function is kept for operations that require a full rewrite, like updating statuses.
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
    except Exception as e:
        print(f"    [File Error] Failed to write to {filepath}: {e}")

def upsert_entry(filepath: str, data_row: Dict, fieldnames: List[str], unique_key: str):
    """
    Performs a robust UPSERT (Update or Insert) operation on a CSV file.
    It reads the file, updates the row if it exists, or appends it if it's new.
    """
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
    """Overwrites the standings for a specific league in standings.csv."""
    if not standings_data or not region_league: return

    last_updated = dt.now().isoformat()
    for row in standings_data:
        row['region_league'] = region_league
        row['last_updated'] = last_updated

    other_leagues_rows = [row for row in _read_csv(STANDINGS_CSV) if row.get('region_league') != region_league]
    all_rows = other_leagues_rows + standings_data
    fieldnames = files_and_headers[STANDINGS_CSV]
    _write_csv(STANDINGS_CSV, all_rows, fieldnames)
    print(f"      [DB] Updated standings for {region_league}")

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
        'losses', 'goals_for', 'goals_against', 'goal_difference', 'points', 'last_updated', 'url'
    ],
    TEAMS_CSV: ['team_id', 'team_name', 'region_league', 'team_url'],
    REGION_LEAGUE_CSV: ['region_league_id', 'region', 'league_name', 'url']
}
