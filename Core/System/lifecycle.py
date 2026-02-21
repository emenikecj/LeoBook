# lifecycle.py: lifecycle.py: Global state management, CLI parsing, and application lifecycle control.
# Part of LeoBook Core — System
#
# Functions: log_state(), log_audit_state(), setup_terminal_logging(), parse_args()

import os
import sys
import argparse
import uuid
from datetime import datetime as dt
from Data.Access.db_helpers import init_csvs
from Core.Utils.utils import Tee, LOG_DIR

state = {
    "cycle_start_time": None, 
    "cycle_count": 0,
    "current_chapter": "Startup",
    "last_action": "Init",
    "next_expected": "Startup Checks",
    "why_this_step": "System initialization",
    "expected_outcome": "Ready to start",
    "ai_server_ready": False,
    "llm_needed_for_this_cycle": False, 
    "pending_count": 0,
    "booked_this_cycle": 0,
    "failed_this_cycle": 0,
    "current_balance": 0.0,
    "last_win_amount": 5000.0, # Heuristic
    "error_log": []
}

def log_state(chapter=None, action=None, next_step=None, why=None, expect=None):
    """Updates and prints the current system state."""
    global state
    if chapter: state["current_chapter"] = chapter
    if action: state["last_action"] = action
    if next_step: state["next_expected"] = next_step
    if why: state["why_this_step"] = why
    if expect: state["expected_outcome"] = expect
    
    print(f"   [STATE] {state['current_chapter']} | Done: {state['last_action']} | Next: {state['next_expected']} | Why: {state['why_this_step']}")

def log_audit_state(chapter: str, action: str, details: str = ""):
    """Central state logger — prints to console and appends to audit_log.csv"""
    timestamp = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"[{timestamp}] [STATE] {chapter} | Action: {action} | {details}"
    print(message)
    
    from Data.Access.db_helpers import append_to_csv
    append_to_csv("audit_log.csv", {
        "id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "event_type": "STATE",
        "description": f"{chapter} - {action} - {details}",
        "balance_before": "",
        "balance_after": "",
        "stake": "",
        "status": "INFO"
    })

def setup_terminal_logging(args):
    """Sets up Tee logging to file with dynamic prefixes."""
    # Set timeout
    if args:
        os.environ["PLAYWRIGHT_TIMEOUT"] = "3600000"

    # Determine prefix
    prefix = "leo_session"
    if args:
        if args.sync: prefix = "leo_sync_session"
        elif args.recommend: prefix = "leo_recommend_session"
        elif args.accuracy: prefix = "leo_accuracy_session"
        elif args.search_dict: prefix = "leo_search_session"
        elif args.review: prefix = "leo_review_session"
        elif args.backtest: prefix = "leo_backtest_session"
        elif args.offline_repredict: prefix = "leo_offline_repredict_session"
        elif args.rule_engine: prefix = "leo_rule_engine_session"
        elif args.streamer: prefix = "leo_streamer_session"
        elif args.schedule: prefix = "leo_schedule_session"
        elif args.prologue: prefix = "leo_prologue_session"
        elif args.chapter: prefix = f"leo_chapter{args.chapter}_session"

    TERMINAL_LOG_DIR = LOG_DIR / "Terminal"
    TERMINAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = TERMINAL_LOG_DIR / f"{prefix}_{timestamp}.log"

    log_file = open(log_file_path, "w", encoding="utf-8")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = Tee(original_stdout, log_file)
    sys.stderr = Tee(original_stderr, log_file)
    
    return log_file, original_stdout, original_stderr

def parse_args():
    """
    Unified CLI for LeoBook. Leo.py is the single entry point.

    Usage examples:
      python Leo.py                       # Full cycle (Prologue → Ch1 → Ch2 → Ch3, loop)
      python Leo.py --prologue            # All prologue pages only
      python Leo.py --prologue --page 1   # Prologue Page 1 only (Sync + Review)
      python Leo.py --chapter 1           # Full Chapter 1
      python Leo.py --chapter 1 --page 2  # Ch1 Page 2 only (Odds Harvesting)
      python Leo.py --sync                # Force full cloud sync
      python Leo.py --recommend           # Generate recommendations only
      python Leo.py --accuracy            # Print accuracy report
    """
    parser = argparse.ArgumentParser(
        description="LeoBook Prediction System — Unified Orchestrator (v3.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Leo.py                            Full cycle (loop)
  python Leo.py --prologue                 All prologue pages (P1+P2+P3)
  python Leo.py --prologue --page 1        Prologue P1: Cloud Handshake & Review
  python Leo.py --prologue --page 2        Prologue P2: Metadata Enrichment
  python Leo.py --prologue --page 3        Prologue P3: Accuracy & Sync
  python Leo.py --chapter 1                Full Chapter 1 (Extraction → Odds → Sync)
  python Leo.py --chapter 1 --page 1       Ch1 P1: Flashscore Extraction & Analysis
  python Leo.py --chapter 1 --page 2       Ch1 P2: Odds Harvesting
  python Leo.py --chapter 1 --page 3       Ch1 P3: Final Sync & Recommendations
  python Leo.py --chapter 2                Full Chapter 2 (Booking & Withdrawal)
  python Leo.py --chapter 3                Chapter 3: Monitoring & Oversight
  python Leo.py --sync                     Force full cloud sync
  python Leo.py --recommend                Generate recommendations only
  python Leo.py --accuracy                 Print accuracy report
  python Leo.py --search-dict              Rebuild search dictionary
  python Leo.py --review                   Run outcome review only
  python Leo.py --backtest                 Run single-pass backtest
  python Leo.py --offline-repredict        Offline reprediction mode
  python Leo.py --streamer                 Run live score streamer
  python Leo.py --rule-engine              Show default rule engine + accuracy
  python Leo.py --rule-engine --list       List all saved rule engines
  python Leo.py --rule-engine --backtest   Progressive backtest default engine
  python Leo.py --rule-engine --backtest --id ENGINE_ID   Backtest a specific engine
  python Leo.py --rule-engine --backtest --from-date 2025-08-01   Set start date
  python Leo.py --rule-engine --set-default "James' Law"   Set engine as default
        """
    )
    # --- Granular Chapter / Page Selection ---
    parser.add_argument('--prologue', action='store_true',
                       help='Run all Prologue pages (P1+P2+P3)')
    parser.add_argument('--chapter', type=int, choices=[1, 2, 3], metavar='N',
                       help='Run a specific chapter (1, 2, or 3)')
    parser.add_argument('--page', type=int, choices=[1, 2, 3], metavar='N',
                       help='Run a specific page within --prologue or --chapter')

    # --- Utility Commands ---
    parser.add_argument('--sync', action='store_true',
                       help='Force a full cloud sync (bi-directional)')
    parser.add_argument('--recommend', action='store_true',
                       help='Generate and display recommendations only')
    parser.add_argument('--accuracy', action='store_true',
                       help='Print accuracy report only')
    parser.add_argument('--search-dict', action='store_true',
                       help='Rebuild the search dictionary from CSVs')
    parser.add_argument('--review', action='store_true',
                       help='Run outcome review process only')
    parser.add_argument('--backtest', action='store_true',
                       help='Run a single-pass backtest check')
    parser.add_argument('--offline-repredict', action='store_true',
                       help='Run offline reprediction using stored data')
    parser.add_argument('--streamer', action='store_true',
                       help='Run the live score streamer independently')
    parser.add_argument('--schedule', action='store_true',
                       help='Run the daily schedule scraper independently')
    parser.add_argument('--refresh', action='store_true',
                       help='Run multi-day schedule scraping (requires --schedule)')

    # --- Rule Engine Management ---
    parser.add_argument('--rule-engine', action='store_true',
                       help='Show default rule engine info (combine with --list, --set-default, --backtest)')
    parser.add_argument('--list', action='store_true',
                       help='List all saved rule engines (use with --rule-engine)')
    parser.add_argument('--set-default', type=str, metavar='NAME',
                       help='Set a rule engine as default by name or ID (use with --rule-engine)')
    parser.add_argument('--id', type=str, metavar='ENGINE_ID',
                       help='Target a specific engine by ID (use with --rule-engine --backtest)')
    parser.add_argument('--from-date', type=str, metavar='DATE',
                       help='Start date for backtest YYYY-MM-DD (use with --rule-engine --backtest)')

    # --- Validation ---
    args = parser.parse_args()
    if args.page and not args.prologue and args.chapter is None:
        parser.error("--page requires --prologue or --chapter")
    if args.list and not args.rule_engine:
        parser.error("--list requires --rule-engine")
    if args.set_default and not args.rule_engine:
        parser.error("--set-default requires --rule-engine")
    return args

