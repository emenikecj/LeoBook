# monitoring.py: monitoring.py: Chapter 3 - Chief Engineer Oversight System
# Part of LeoBook Core — System
#
# Functions: run_chapter_3_oversight(), perform_health_check(), _count_predictions_for_date(), _get_bet_success_rate(), generate_oversight_report()

import os
import csv
from datetime import datetime as dt
from pathlib import Path
from Core.System.lifecycle import state
from Data.Access.db_helpers import log_audit_event

async def run_chapter_3_oversight():
    """
    Chapter 3: Chief Engineer Monitoring.
    Runs health checks, generates report, logs to Supabase.
    """
    print("\n   [Chapter 3] Chief Engineer performing oversight...")
    
    health_status = perform_health_check()
    report = generate_oversight_report(health_status)

    # Print report to console
    print(f"\n{report}")

    # Persist report to Supabase via audit log
    log_audit_event("OVERSIGHT_REPORT", report, status="success")

    return health_status

def perform_health_check():
    """Checks various system components for issues."""
    issues = []
    
    # 1. Check Data Store integrity
    store_path = Path("Data/Store")
    if not store_path.exists():
        issues.append("❌ Data store directory missing.")
    else:
        pred_file = store_path / "predictions.csv"
        if pred_file.exists():
            import time
            mtime = os.path.getmtime(pred_file)
            if (time.time() - mtime) > 86400: # 24 hours
                issues.append("⚠️ `predictions.csv` hasn't been updated in 24h.")
        else:
            issues.append("❌ `predictions.csv` missing.")

    # 2. Check Error Log
    error_count = len(state.get("error_log", []))
    if error_count > 0:
        issues.append(f"⚠️ {error_count} errors logged this cycle.")

    # 3. Check Balance Stagnation
    if state.get("current_balance", 0) <= 0:
         issues.append("⚠️ Account balance is zero or unknown.")

    # 4. Prediction Volume (new v2.8)
    today_str = dt.now().strftime("%Y-%m-%d")
    today_preds = _count_predictions_for_date(today_str)
    if today_preds < 5:
        issues.append(f"⚠️ Low prediction volume today: {today_preds} (expected ≥5).")

    # 5. Bet Success Rate (new v2.8)
    success_rate = _get_bet_success_rate()
    if success_rate is not None and success_rate < 50.0:
        issues.append(f"⚠️ Bet placement success rate is low: {success_rate:.0f}%.")

    return issues if issues else ["✅ System is healthy and operational."]

def _count_predictions_for_date(date_str: str) -> int:
    """Count predictions for a given date from predictions.csv."""
    pred_file = Path("Data/Store/predictions.csv")
    if not pred_file.exists():
        return 0
    try:
        with open(pred_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return sum(1 for row in reader if row.get("date", "").startswith(date_str))
    except Exception:
        return 0

def _get_bet_success_rate() -> float | None:
    """Calculate today's bet placement success rate from audit_log.csv."""
    audit_file = Path("Data/Store/audit_log.csv")
    if not audit_file.exists():
        return None
    try:
        today_str = dt.now().strftime("%Y-%m-%d")
        total = 0
        successful = 0
        with open(audit_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("event_type") == "BET_PLACEMENT" and today_str in row.get("timestamp", ""):
                    total += 1
                    if row.get("status", "").lower() == "success":
                        successful += 1
        if total == 0:
            return None  # No bets placed today — nothing to report
        return (successful / total) * 100
    except Exception:
        return None

def generate_oversight_report(health_status):
    """Formats the oversight findings into a readable string."""
    status_summary = "\n".join(health_status)
    
    report = (
        f"═══ Chief Engineer Oversight Report ═══\n"
        f"Cycle Count: #{state.get('cycle_count', 0)}\n"
        f"Uptime: {dt.now() - state.get('cycle_start_time', dt.now())}\n"
        f"Current Balance: ₦{state.get('current_balance', 0):,.2f}\n"
        f"Booked: {state.get('booked_this_cycle', 0)}\n"
        f"Failed: {state.get('failed_this_cycle', 0)}\n\n"
        f"Health Check:\n{status_summary}"
    )
    return report
