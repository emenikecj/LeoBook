# Leo.py: The central orchestrator for the LeoBook system (v2.8).
# This script is a PURE ORCHESTRATOR containing ZERO business logic or function definitions.
# All logic lives in the modules it calls.

import asyncio
import nest_asyncio
import os
import sys
from datetime import datetime as dt
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Apply nest_asyncio for nested loops
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# --- Modular Imports (all logic is external) ---
from Core.System.lifecycle import (
    log_state, log_audit_state, setup_terminal_logging, parse_args, state
)
from Core.System.withdrawal_checker import (
    check_triggers, propose_withdrawal, calculate_proposed_amount, get_latest_win,
    check_withdrawal_approval, execute_withdrawal
)
from Data.Access.db_helpers import init_csvs, log_audit_event
from Data.Access.sync_manager import SyncManager, run_full_sync
from Data.Access.review_outcomes import run_review_process, run_accuracy_generation
from Data.Access.prediction_accuracy import print_accuracy_report
from Scripts.enrich_all_schedules import enrich_all_schedules
from Modules.Flashscore.manager import run_flashscore_analysis, run_flashscore_offline_repredict
from Modules.Flashscore.fs_live_streamer import live_score_streamer
from Modules.FootballCom.fb_manager import run_odds_harvesting, run_automated_booking
from Core.System.monitoring import run_chapter_3_oversight
from Scripts.recommend_bets import get_recommendations

# Configuration
CYCLE_WAIT_HOURS = int(os.getenv('LEO_CYCLE_WAIT_HOURS', 6))
LOCK_FILE = "leo.lock"

async def main():
    """Main execution loop: Prologue (Pages 1-3) → Chapter 1 (Pages 1-3). No definitions here."""
    # Singleton Check
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
                import psutil
                if psutil.pid_exists(old_pid):
                    print(f"   [System Error] Leo is already running (PID: {old_pid}).")
                    sys.exit(1)
        except: pass

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        init_csvs()

        async with async_playwright() as p:
            # Spawn live score streamer in parallel (own browser, 60s loop)
            streamer_task = asyncio.create_task(live_score_streamer(p))

            while True:
                try:
                    state["cycle_count"] += 1
                    state["cycle_start_time"] = dt.now()
                    cycle_num = state["cycle_count"]
                    log_state(chapter="Cycle Start", action=f"Starting Cycle #{cycle_num}")
                    log_audit_event("CYCLE_START", f"Cycle #{cycle_num} initiated.")

                    # ============================================================
                    # 🟢 PROLOGUE: THE ENRICHMENT & CLOUD-SYNC PHASE
                    # ============================================================

                    # --- PROLOGUE PAGE 1: Data & Prediction Review ---
                    log_state(chapter="Prologue P1", action="Cloud Handshake & Prediction Review")
                    try:
                        print("\n" + "=" * 60)
                        print("  PROLOGUE PAGE 1: Cloud Handshake & Prediction Review")
                        print("=" * 60)

                        # 1a. Cloud Handshake (Bi-Directional Sync)
                        sync_mgr = SyncManager()
                        await sync_mgr.sync_on_startup()

                        from Data.Access.outcome_reviewer import run_review_process
                        await run_review_process(p)

                        # 1c. Accuracy Report
                        print_accuracy_report()

                        log_audit_event("PROLOGUE_P1", "Cloud handshake and prediction review completed.", status="success")
                    except Exception as e:
                        print(f"  [Error] Prologue Page 1 failed: {e}")
                        log_audit_event("PROLOGUE_P1", f"Failed: {e}", status="failed")

                    # --- PROLOGUE PAGE 2: Schedules & Metadata Enrichment ---
                    log_state(chapter="Prologue P2", action="Metadata Enrichment")
                    try:
                        print("\n" + "=" * 60)
                        print("  PROLOGUE PAGE 2: Schedules & Metadata Enrichment")
                        print("=" * 60)

                        await enrich_all_schedules(extract_standings=True)

                        log_audit_event("PROLOGUE_P2", "Metadata enrichment completed.", status="success")
                    except Exception as e:
                        print(f"  [Error] Prologue Page 2 failed: {e}")
                        log_audit_event("PROLOGUE_P2", f"Failed: {e}", status="failed")

                    # --- PROLOGUE PAGE 3: Accuracy Report & Final Sync ---
                    log_state(chapter="Prologue P3", action="Accuracy Generation & Final Prologue Sync")
                    try:
                        print("\n" + "=" * 60)
                        print("  PROLOGUE PAGE 3: Accuracy & Final Prologue Sync")
                        print("=" * 60)

                        await run_accuracy_generation()
                        await run_full_sync(session_name="Prologue Final")

                        log_audit_event("PROLOGUE_P3", "Accuracy generated and Prologue sync completed.", status="success")
                    except Exception as e:
                        print(f"  [Error] Prologue Page 3 failed: {e}")
                        log_audit_event("PROLOGUE_P3", f"Failed: {e}", status="failed")

                    # ============================================================
                    # 🔴 CHAPTER 1: THE DISCOVERY & PREDICTION PHASE
                    # ============================================================

                    # --- CHAPTER 1 PAGE 1: Extraction & Prediction ---
                    log_state(chapter="Ch1 P1", action="Flashscore Extraction & Analysis")
                    try:
                        print("\n" + "=" * 60)
                        print("  CHAPTER 1 PAGE 1: Extraction & Prediction")
                        print("=" * 60)

                        await run_flashscore_analysis(p)

                        log_audit_event("CH1_P1", "Flashscore extraction and analysis completed.", status="success")
                    except Exception as e:
                        print(f"  [Error] Chapter 1 Page 1 failed: {e}")
                        log_audit_event("CH1_P1", f"Failed: {e}", status="failed")

                    # --- CHAPTER 1 PAGE 2: Odds Harvesting & URL Resolution ---
                    log_state(chapter="Ch1 P2", action="Odds Harvesting & URL Resolution")
                    fb_session_healthy = False  # Fix #6: Session health flag
                    try:
                        print("\n" + "=" * 60)
                        print("  CHAPTER 1 PAGE 2: Odds Harvesting & URL Resolution")
                        print("=" * 60)

                        # Resolve URLs and harvest odds/booking codes (no placement)
                        await run_odds_harvesting(p)
                        fb_session_healthy = True  # Only set True if harvesting succeeded

                        log_audit_event("CH1_P2", "Odds harvesting and URL resolution completed.", status="success")
                    except Exception as e:
                        print(f"  [Error] Chapter 1 Page 2 failed: {e}")
                        print(f"  [Session] Football.com session marked unhealthy — Chapter 2 will be skipped.")
                        log_audit_event("CH1_P2", f"Failed: {e}", status="failed")

                    # --- CHAPTER 1 PAGE 3: Final Sync & Recommendations ---
                    log_state(chapter="Ch1 P3", action="Final Chapter Sync & Recommendations")
                    try:
                        print("\n" + "=" * 60)
                        print("  CHAPTER 1 PAGE 3: Final Sync & Recommendations")
                        print("=" * 60)

                        sync_ok = await run_full_sync(session_name="Chapter 1 Final")
                        if not sync_ok:
                            print("  [AIGO] Sync parity issues detected. Logged for review.")
                            log_audit_event("CH1_P3_SYNC", "Sync parity issues detected.", status="partial_failure")

                        get_recommendations(save_to_file=True)

                        log_audit_event("CH1_P3", "Final sync and recommendations completed.", status="success")
                    except Exception as e:
                        print(f"  [Error] Chapter 1 Page 3 failed: {e}")
                        log_audit_event("CH1_P3", f"Failed: {e}", status="failed")

                    # ============================================================
                    # 🟡 CHAPTER 2: AUTOMATED BOOKING & FUNDS MANAGEMENT
                    # ============================================================

                    # Fix #6: Skip entire Chapter 2 if Football.com session is dead
                    if not fb_session_healthy:
                        print("\n" + "=" * 60)
                        print("  CHAPTER 2: SKIPPED — Football.com session unhealthy")
                        print("=" * 60)
                        log_audit_event("CH2_SKIPPED", "Skipped: Football.com session failed in Ch1 P2.", status="skipped")
                    else:
                        # --- CHAPTER 2 PAGE 1: Automated Booking ---
                        log_state(chapter="Ch2 P1", action="Automated Booking (Football.com)")
                        try:
                            print("\n" + "=" * 60)
                            print("  CHAPTER 2 PAGE 1: Automated Booking")
                            print("=" * 60)

                            # Place multi-bets from harvested codes (decoupled from harvesting)
                            await run_automated_booking(p)

                            log_audit_event("CH2_P1", "Automated booking phase completed.", status="success")
                        except Exception as e:
                            print(f"  [Error] Chapter 2 Page 1 failed: {e}")
                            log_audit_event("CH2_P1", f"Failed: {e}", status="failed")

                        # --- CHAPTER 2 PAGE 2: Funds & Withdrawal Check ---
                        log_state(chapter="Ch2 P2", action="Funds & Withdrawal Check")
                        try:
                            print("\n" + "=" * 60)
                            print("  CHAPTER 2 PAGE 2: Funds & Withdrawal Check")
                            print("=" * 60)

                            async with await p.chromium.launch(headless=True) as check_browser:
                                from Modules.FootballCom.navigator import extract_balance
                                check_page = await check_browser.new_page()
                                state["current_balance"] = await extract_balance(check_page)

                            if await check_triggers():
                                proposed_amount = calculate_proposed_amount(state["current_balance"], get_latest_win())
                                await propose_withdrawal(proposed_amount)

                            # Check if a previously proposed withdrawal was approved via Web/App
                            if await check_withdrawal_approval():
                                from Core.System.withdrawal_checker import pending_withdrawal
                                await execute_withdrawal(pending_withdrawal["amount"])

                            log_audit_event("CH2_P2", f"Withdrawal check completed. Balance: {state.get('current_balance', 'N/A')}", status="success")
                        except Exception as e:
                            print(f"  [Warning] Chapter 2 Page 2 failed: {e}")
                            log_audit_event("CH2_P2", f"Failed: {e}", status="failed")

                    # ============================================================
                    # 🔵 CHAPTER 3: CHIEF ENGINEER MONITORING & OVERSIGHT
                    # ============================================================
                    log_state(chapter="Chapter 3", action="Chief Engineer Oversight")
                    try:
                        print("\n" + "=" * 60)
                        print("  CHAPTER 3: Chief Engineer Monitoring & Oversight")
                        print("=" * 60)

                        await run_chapter_3_oversight()

                        log_audit_event("CH3", "Chief Engineer oversight completed.", status="success")
                    except Exception as e:
                        print(f"  [Error] Chapter 3 failed: {e}")
                        log_audit_event("CH3", f"Failed: {e}", status="failed")

                    # ============================================================
                    # CYCLE COMPLETE
                    # ============================================================
                    log_audit_event("CYCLE_COMPLETE", f"Cycle #{cycle_num} finished.")
                    print(f"\n   [System] Cycle #{cycle_num} finished at {dt.now().strftime('%H:%M:%S')}. Sleeping {CYCLE_WAIT_HOURS}h...")
                    await asyncio.sleep(CYCLE_WAIT_HOURS * 3600)

                except Exception as e:
                    state["error_log"].append(f"{dt.now()}: {e}")
                    print(f"[ERROR] Main loop: {e}")
                    log_audit_event("CYCLE_ERROR", f"Unhandled: {e}", status="failed")
                    await asyncio.sleep(60)
    finally:
        if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)

async def main_offline_repredict():
    """Run offline reprediction."""
    print("    --- LEO: Offline Reprediction Mode ---      ")
    init_csvs()
    async with async_playwright() as p:
        try:
            await run_review_process(p)
            print_accuracy_report()
            await run_flashscore_offline_repredict(p)
        except Exception as e:
            print(f"[ERROR] Offline repredict: {e}")

if __name__ == "__main__":
    args = parse_args()
    log_file, original_stdout, original_stderr = setup_terminal_logging(args)
    try:
        if args.offline_repredict: asyncio.run(main_offline_repredict())
        else: asyncio.run(main())
    except KeyboardInterrupt:
        print("\n   --- LEO: Shutting down. ---")
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr
        log_file.close()
