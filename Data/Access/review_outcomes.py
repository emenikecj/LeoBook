# review_outcomes.py: review_outcomes.py: Entry point for reviewing match results (Chapter 0).
# Part of LeoBook Data — Access Layer
#
# Functions: evaluate_prediction(), run_accuracy_generation(), start_review()

"""
LeoBook Review Outcomes System v2.6.0
Modular outcome review and evaluation system.

This module provides a unified interface to the review system components:
- Health monitoring and alerting
- Data validation and quality assurance
- Prediction evaluation for all betting markets
- Core review processing and outcome tracking
"""

# Import all modular components
from .health_monitor import HealthMonitor
from .data_validator import DataValidator
import pandas as pd
from datetime import datetime, timedelta
import pytz
import os
import uuid
from .db_helpers import PREDICTIONS_CSV, ACCURACY_REPORTS_CSV, log_audit_event, upsert_entry, files_and_headers
from .sync_manager import SyncManager

def evaluate_prediction(predicted_type: str, home_score: str, away_score: str) -> int:
    """
    Evaluates if a prediction was correct (1) or not (0).
    Handles all market types used by the LeoBook prediction pipeline.
    """
    try:
        h = int(home_score)
        a = int(away_score)
        total = h + a
        pt = predicted_type.strip()
        pt_upper = pt.upper().replace(' ', '_')
        pt_lower = pt.lower()

        # --- Standard Markets ---
        if pt_upper in ("OVER_2.5", "OVER_2_5"):
            return 1 if total > 2.5 else 0
        if pt_upper in ("UNDER_2.5", "UNDER_2_5"):
            return 1 if total < 2.5 else 0
        if pt_upper in ("BTTS_YES", "BTTS YES") or pt_lower == "btts yes":
            return 1 if h > 0 and a > 0 else 0
        if pt_upper in ("BTTS_NO", "BTTS NO") or pt_lower in ("btts no", "btts_no"):
            return 1 if h == 0 or a == 0 else 0
        if pt_upper in ("HOME_WIN", "HOME WIN", "1"):
            return 1 if h > a else 0
        if pt_upper in ("AWAY_WIN", "AWAY WIN", "2"):
            return 1 if a > h else 0
        if pt_upper in ("DRAW", "X"):
            return 1 if h == a else 0

        # --- Double Chance Markets ---
        if pt_lower in ("draw no bet", "draw_no_bet", "dnb"):
            # Draw No Bet = void on draw, win if predicted team wins
            # Without knowing which team, assume home side (most common)
            return 1 if h >= a else 0  # Home or Draw = refund, Home Win = win
        if pt_lower in ("home or draw", "home_or_draw", "1x"):
            return 1 if h >= a else 0
        if pt_lower in ("away or draw", "away_or_draw", "x2"):
            return 1 if a >= h else 0
        if pt_lower in ("home or away", "home_or_away", "12"):
            return 1 if h != a else 0  # No draw

        # --- Team Goals Over/Under (e.g., "Team Over 0.5", "Team Over 1.5") ---
        import re
        team_over = re.match(r'(?:home\s+)?(?:team\s+)?over\s+([\d.]+)', pt_lower)
        if team_over:
            threshold = float(team_over.group(1))
            # "Team Over X" typically means the home team scores > X goals
            return 1 if h > threshold else 0
        
        team_under = re.match(r'(?:home\s+)?(?:team\s+)?under\s+([\d.]+)', pt_lower)
        if team_under:
            threshold = float(team_under.group(1))
            return 1 if h < threshold else 0

        away_over = re.match(r'away\s+(?:team\s+)?over\s+([\d.]+)', pt_lower)
        if away_over:
            threshold = float(away_over.group(1))
            return 1 if a > threshold else 0

        away_under = re.match(r'away\s+(?:team\s+)?under\s+([\d.]+)', pt_lower)
        if away_under:
            threshold = float(away_under.group(1))
            return 1 if a < threshold else 0

        # --- Total Goals Over/Under (generic) ---
        total_over = re.match(r'over\s+([\d.]+)', pt_lower)
        if total_over:
            threshold = float(total_over.group(1))
            return 1 if total > threshold else 0

        total_under = re.match(r'under\s+([\d.]+)', pt_lower)
        if total_under:
            threshold = float(total_under.group(1))
            return 1 if total < threshold else 0

        # Fallback for complex strings
        return 0
    except:
        return 0


async def run_accuracy_generation():
    """
    Aggregates performance metrics from predictions.csv for the last 24h.
    Logs to audit_log.csv and upserts to Supabase 'accuracy_reports'.
    """
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
        now_lagos = datetime.now(lagos_tz)
        yesterday_lagos = now_lagos - timedelta(days=1)

        def parse_updated(ts):
            try:
                # pandas to_datetime is flexible with ISO formats
                dt = pd.to_datetime(ts)
                if dt.tzinfo is None:
                    return lagos_tz.localize(dt)
                return dt.astimezone(lagos_tz)
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

        # Return Calculation (1-unit flat stake)
        total_return = 0
        for _, row in df_24h.iterrows():
            try:
                odds = float(row.get('odds', 0))
                if odds <= 0: odds = 2.0 # Default conservative odds
                
                if row['outcome_correct'] == '1':
                    total_return += (odds - 1)
                else:
                    total_return -= 1
            except:
                pass
        
        return_pct = (total_return / volume) * 100 if volume > 0 else 0

        # 3. Persistence (Local CSV)
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
        
        # Save to accuracy_reports.csv
        upsert_entry(ACCURACY_REPORTS_CSV, report_row, files_and_headers[ACCURACY_REPORTS_CSV], 'report_id')

        # Log to audit_log.csv
        log_audit_event(
            event_type='ACCURACY_REPORT',
            description=f"Generated report {report_id}: Volume={volume}, WinRate={win_rate:.1f}%, Return={return_pct:.1f}%",
            status='success'
        )

        # 4. Immediate Cloud Sync
        sync = SyncManager()
        if sync.supabase:
            print(f"   [SYNC] Pushing accuracy report {report_id} to Supabase...")
            await sync.batch_upsert('accuracy_reports', [report_row])
            print("   [SUCCESS] Accuracy metrics synchronized.")

    except Exception as e:
        print(f"   [ACCURACY ERROR] {e}")


from .outcome_reviewer import (
    get_predictions_to_review,
    save_single_outcome,
    process_review_task_offline,
    run_review_process
)

# Legacy compatibility - expose main functions at module level
__all__ = [
    'HealthMonitor',
    'DataValidator',
    'evaluate_prediction',
    'get_predictions_to_review',
    'save_single_outcome',
    'process_review_task_offline',
    'run_review_process'
]

# Note: run_review_process no longer requires playwright argument
async def start_review():
    await run_review_process()

# Version information
__version__ = "2.6.0"
__compatible_models__ = ["2.5", "2.6"]
