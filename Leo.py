# Leo.py: The central orchestrator for the LeoBook system.
# Refactored for Clean Architecture (v2.7)
# This script is a pure orchestrator containing NO business logic.

import asyncio
import nest_asyncio
nest_asyncio.apply()
import os
import sys
from datetime import datetime as dt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from playwright.async_api import async_playwright

# Modular Imports
# Modular Imports
from Core.System.lifecycle import (
    log_state, log_audit_state, setup_terminal_logging, parse_args, state
)
from Core.System.telegram_bridge import start_telegram_listener
from Core.System.withdrawal_checker import (
    check_triggers, propose_withdrawal, execute_withdrawal, calculate_proposed_amount, get_latest_win
)
from Data.Access.db_helpers import init_csvs, log_audit_event

# Phase Orchestrators
from Modules.Flashscore.manager import run_flashscore_analysis, run_flashscore_offline_repredict
from Modules.FootballCom.fb_manager import run_football_com_booking

# Configuration
CYCLE_WAIT_HOURS = 6

LOCK_FILE = "leo.lock"

async def main():
    """
    The main execution loop for Leo.
    Adheres to the "Observe, Decide, Act" algorithm with strict phases.
    """
    # Singleton Check
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
                # Check if process is actually running
                import psutil
                if psutil.pid_exists(old_pid):
                    print(f"   [System Error] Leo is already running (PID: {old_pid}). Close it first.")
                    sys.exit(1)
        except (ValueError, ImportError, Exception):
            # If psutil missing or file corrupt, just overwrite
            pass

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        # 1. Initialize
        log_state(phase="Init", action="Initializing Databases")
        init_csvs()
        
        # 2. Start Telegram Listener
        asyncio.create_task(start_telegram_listener())

        async with async_playwright() as p:
            while True:
                try:
                    state["cycle_count"] += 1
                    state["cycle_start_time"] = dt.now()
                    log_state(phase="Cycle Start", action=f"Starting Cycle #{state['cycle_count']}", next_step="Phase 0: Review")

                    # --- PHASE 0: REVIEW (Observe past actions) ---
                    log_state(phase="Phase 0", action="Reviewing Outcomes", next_step="Accuracy Report")
                    from Data.Access.review_outcomes import run_review_process
                    try:
                        #await run_review_process(p)
                        print("Phase 0 Review skipped.")
                    except Exception as e:
                        print(f"  [Error] Phase 0 Review failed: {e}")

                    # Print prediction accuracy report
                    log_state(phase="Phase 0", action="Generating Accuracy Report", next_step="Phase 1: Analysis")
                    from Data.Access.prediction_accuracy import print_accuracy_report
                    try:
                        print_accuracy_report()
                        #print("Phase 0 Accuracy report skipped.")
                    except Exception as e:
                        print(f"  [Error] Phase 0 Accuracy report failed: {e}")

                    # --- PHASE 1: ANALYSIS (Observe and Decide) ---
                    log_state(phase="Phase 1", action="Starting Flashscore Analysis", next_step="Phase 2: Booking")
                    await run_flashscore_analysis(p)

                    # --- PHASE 2: BOOKING (Act) ---
                    log_state(phase="Phase 2", action="Starting Booking Process", next_step="Withdrawal Check")
                    # This phase now follows the Unified "Search & Place" flow
                    await run_football_com_booking(p)
                    
                    # Update current balance in state after booking
                    from Modules.FootballCom.navigator import extract_balance
                    try:
                        check_browser = await p.chromium.launch(headless=True)
                        check_page = await check_browser.new_page()
                        state["current_balance"] = await extract_balance(check_page)
                        await check_browser.close()
                        
                        # --- PHASE 3: WITHDRAWAL PROPOSAL ---
                        if await check_triggers():
                            proposed_amount = calculate_proposed_amount(state["current_balance"], get_latest_win())
                            await propose_withdrawal(proposed_amount)
                    except Exception as e:
                        print(f"  [Warning] Preliminary balance check failed: {e}")

                    # --- CYCLE END ---
                    log_state(phase="Phase 3", action="Cycle Complete", next_step=f"Sleeping {CYCLE_WAIT_HOURS}h")
                    log_audit_event("CYCLE_COMPLETE", f"Cycle #{state['cycle_count']} finished successfully.")
                    print(f"   [System] Cycle #{state['cycle_count']} finished at {dt.now().strftime('%H:%M:%S')}. Sleeping for {CYCLE_WAIT_HOURS} hours...")
                    await asyncio.sleep(CYCLE_WAIT_HOURS * 3600)

                except Exception as e:
                    state["error_log"].append(f"{dt.now()}: {e}")
                    print(f"[ERROR] An unexpected error occurred in the main loop: {e}")
                    print("Restarting cycle after a short delay...")
                    await asyncio.sleep(60)
    finally:
        if os.path.exists(LOCK_FILE):
             os.remove(LOCK_FILE)


async def main_offline_repredict():
    """Run offline reprediction using stored data."""
    print("    --- LEO: Offline Reprediction Mode ---      ")
    init_csvs()

    async with async_playwright() as p:
        try:
            print(f"\n      --- LEO: Starting offline reprediction at {dt.now().strftime('%Y-%m-%d %H:%M:%S')} --- ")

            print("\n   [Phase 0] Checking for past matches to review...")
            from Data.Access.review_outcomes import run_review_process
            await run_review_process(p)

            print("   [Phase 0] Analyzing prediction accuracy...")
            from Data.Access.prediction_accuracy import print_accuracy_report
            print_accuracy_report()

            print("\n   [Phase 1] Starting offline reprediction engine...")
            await run_flashscore_offline_repredict(p)

            print("\n   --- LEO: Offline Reprediction Complete. ---")

        except Exception as e:
            print(f"[ERROR] An unexpected error occurred in offline reprediction: {e}")


if __name__ == "__main__":
    args = parse_args()
    log_file, original_stdout, original_stderr = setup_terminal_logging(args)

    try:
        if args.offline_repredict:
            asyncio.run(main_offline_repredict())
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        print("\n   --- LEO: Shutting down gracefully. ---")
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()
