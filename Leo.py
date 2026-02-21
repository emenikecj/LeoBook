# Leo.py: Leo.py: The central orchestrator for the LeoBook system (v3.0).
# Part of LeoBook Unknown
#
# Functions: run_prologue_p1(), run_prologue_p2(), run_prologue_p3(), run_chapter_1_p1(), run_chapter_1_p2(), run_chapter_1_p3(), run_chapter_2_p1(), run_chapter_2_p2() (+5 more)

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


# ============================================================
# PAGE FUNCTIONS — Each is a self-contained async operation
# ============================================================

async def run_prologue_p1(p):
    """Prologue Page 1: Cloud Handshake & Prediction Review."""
    log_state(chapter="Prologue P1", action="Cloud Handshake & Prediction Review")
    try:
        print("\n" + "=" * 60)
        print("  PROLOGUE PAGE 1: Cloud Handshake & Prediction Review")
        print("=" * 60)

        sync_mgr = SyncManager()
        await sync_mgr.sync_on_startup()

        from Data.Access.outcome_reviewer import run_review_process
        await run_review_process(p)

        print_accuracy_report()

        log_audit_event("PROLOGUE_P1", "Cloud handshake and prediction review completed.", status="success")
    except Exception as e:
        print(f"  [Error] Prologue Page 1 failed: {e}")
        log_audit_event("PROLOGUE_P1", f"Failed: {e}", status="failed")


async def run_prologue_p2():
    """Prologue Page 2: Metadata Enrichment (schedules, teams, leagues, standings)."""
    log_state(chapter="Prologue P2", action="Metadata Enrichment")
    try:
        print("\n" + "=" * 60)
        print("  PROLOGUE PAGE 2: Schedules & Metadata Enrichment")
        print("=" * 60)
        await enrich_all_schedules(extract_standings=True, league_page=True)
        await run_full_sync(session_name="Prologue P2")
        log_audit_event("PROLOGUE_P2", "Metadata enrichment completed.", status="success")
    except Exception as e:
        print(f"  [Error] Prologue Page 2 failed: {e}")
        log_audit_event("PROLOGUE_P2", f"Failed: {e}", status="failed")


async def run_prologue_p3():
    """Prologue Page 3: Accuracy Generation & Final Prologue Sync."""
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


async def run_chapter_1_p1(p):
    """Chapter 1 Page 1: Flashscore Extraction & AI Analysis."""
    log_state(chapter="Ch1 P1", action="Flashscore Extraction & Analysis")
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 1 PAGE 1: Extraction & Prediction")
        print("=" * 60)
        await run_flashscore_analysis(p)
        await run_full_sync(session_name="Ch1 P1")
        log_audit_event("CH1_P1", "Flashscore extraction and analysis completed.", status="success")
    except Exception as e:
        print(f"  [Error] Chapter 1 Page 1 failed: {e}")
        log_audit_event("CH1_P1", f"Failed: {e}", status="failed")


async def run_chapter_1_p2(p):
    """Chapter 1 Page 2: Odds Harvesting & URL Resolution. Returns session health."""
    log_state(chapter="Ch1 P2", action="Odds Harvesting & URL Resolution")
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 1 PAGE 2: Odds Harvesting & URL Resolution")
        print("=" * 60)
        await run_odds_harvesting(p)
        await run_full_sync(session_name="Ch1 P2")
        log_audit_event("CH1_P2", "Odds harvesting and URL resolution completed.", status="success")
        return True  # Session healthy
    except Exception as e:
        print(f"  [Error] Chapter 1 Page 2 failed: {e}")
        print(f"  [Session] Football.com session marked unhealthy — Chapter 2 will be skipped.")
        log_audit_event("CH1_P2", f"Failed: {e}", status="failed")
        return False  # Session unhealthy


async def run_chapter_1_p3():
    """Chapter 1 Page 3: Final Sync & Recommendation Generation."""
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


async def run_chapter_2_p1(p):
    """Chapter 2 Page 1: Automated Booking on Football.com."""
    log_state(chapter="Ch2 P1", action="Automated Booking (Football.com)")
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 2 PAGE 1: Automated Booking")
        print("=" * 60)
        await run_automated_booking(p)
        await run_full_sync(session_name="Ch2 P1 Booking")
        log_audit_event("CH2_P1", "Automated booking phase completed.", status="success")
    except Exception as e:
        print(f"  [Error] Chapter 2 Page 1 failed: {e}")
        log_audit_event("CH2_P1", f"Failed: {e}", status="failed")


async def run_chapter_2_p2(p):
    """Chapter 2 Page 2: Funds Balance & Withdrawal Check."""
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

        if await check_withdrawal_approval():
            from Core.System.withdrawal_checker import pending_withdrawal
            await execute_withdrawal(pending_withdrawal["amount"])

        log_audit_event("CH2_P2", f"Withdrawal check completed. Balance: {state.get('current_balance', 'N/A')}", status="success")
        await run_full_sync(session_name="Ch2 P2 Withdrawal")
    except Exception as e:
        print(f"  [Warning] Chapter 2 Page 2 failed: {e}")
        log_audit_event("CH2_P2", f"Failed: {e}", status="failed")


async def run_chapter_3():
    """Chapter 3: Chief Engineer Monitoring & Oversight + Backtest Check."""
    log_state(chapter="Chapter 3", action="Chief Engineer Oversight")
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 3: Chief Engineer Monitoring & Oversight")
        print("=" * 60)

        await run_chapter_3_oversight()

        # --- Backtest Check (single-pass, integrated from backtest_monitor.py) ---
        try:
            from Scripts.backtest_monitor import TRIGGER_FILE, CONFIG_FILE
            from Core.Intelligence.rule_config import RuleConfig
            import json
            if os.path.exists(TRIGGER_FILE):
                print("  [Backtest] Trigger detected — running single-pass backtest...")
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, 'r') as f:
                        config_data = json.load(f)
                    valid_keys = RuleConfig.__annotations__.keys()
                    filtered = {k: v for k, v in config_data.items() if k in valid_keys}
                    config = RuleConfig(**filtered)
                    await run_flashscore_offline_repredict(playwright=None, custom_config=config)
                    print("  [Backtest] Complete.")
                os.remove(TRIGGER_FILE)
        except Exception as e:
            print(f"  [Backtest] Check failed: {e}")

        log_audit_event("CH3", "Chief Engineer oversight completed.", status="success")
        await run_full_sync(session_name="Ch3 Oversight")
    except Exception as e:
        print(f"  [Error] Chapter 3 failed: {e}")
        log_audit_event("CH3", f"Failed: {e}", status="failed")


# ============================================================
# UTILITY COMMANDS — Single-shot operations, no cycle loop
# ============================================================

async def run_utility(args):
    """Handle utility commands that don't require the full pipeline."""
    init_csvs()

    if args.sync:
        print("\n  --- LEO: Force Full Cloud Sync ---")
        await run_full_sync(session_name="Manual Sync")
        print("  [SUCCESS] Sync complete.")

    elif args.recommend:
        print("\n  --- LEO: Generate Recommendations ---")
        get_recommendations(save_to_file=True)

    elif args.accuracy:
        print("\n  --- LEO: Accuracy Report ---")
        print_accuracy_report()

    elif args.search_dict:
        print("\n  --- LEO: Rebuild Search Dictionary ---")
        from Scripts.build_search_dict import main as build_search
        build_search()

    elif args.review:
        print("\n  --- LEO: Outcome Review ---")
        async with async_playwright() as p:
            from Data.Access.outcome_reviewer import run_review_process
            await run_review_process(p)
            print_accuracy_report()

    elif args.backtest and not args.rule_engine:
        print("\n  --- LEO: Single-Pass Backtest ---")
        from Scripts.backtest_monitor import TRIGGER_FILE, CONFIG_FILE
        from Core.Intelligence.rule_config import RuleConfig
        import json
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            valid_keys = RuleConfig.__annotations__.keys()
            filtered = {k: v for k, v in config_data.items() if k in valid_keys}
            config = RuleConfig(**filtered)
            await run_flashscore_offline_repredict(playwright=None, custom_config=config)
        else:
            print(f"  [ERROR] Config file not found: {CONFIG_FILE}")

    elif args.streamer:
        print("\n  --- LEO: Live Score Streamer ---")
        async with async_playwright() as p:
            await live_score_streamer(p)

    elif args.schedule:
        print("\n  --- LEO: Daily Schedule Scraper ---")
        async with async_playwright() as p:
            from Modules.Flashscore.fs_schedule import extract_matches_from_page
            from Core.Browser.site_helpers import click_next_day, fs_universal_popup_dismissal
            from Core.Intelligence.selector_manager import SelectorManager
            from Data.Access.db_helpers import save_schedule_entry, save_team_entry
            from datetime import datetime as dt, timedelta
            from zoneinfo import ZoneInfo
            import asyncio
            NIGERIA_TZ = ZoneInfo("Africa/Lagos")
            
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                timezone_id="Africa/Lagos"
            )
            page = await context.new_page()
            
            try:
                # Go to flashscore home
                await page.goto("https://www.flashscore.com/football/", timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_selector('.sportName.soccer, #live-table', timeout=15000)
                await fs_universal_popup_dismissal(page, "fs_home_page")

                days_to_scan = 7 if args.refresh else 1
                print(f"  [Schedule] Scanning {days_to_scan} day(s)...")

                for day_offset in range(days_to_scan):
                    target_date = dt.now(NIGERIA_TZ) + timedelta(days=day_offset)
                    target_full = target_date.strftime("%d.%m.%Y")
                    
                    if day_offset > 0:
                        match_row_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "match_rows")
                        if not match_row_sel or not await click_next_day(page, match_row_sel):
                            print(f"  [Schedule] Failed to navigate to day {day_offset}, stopping.")
                            break
                        await asyncio.sleep(2)
                    
                    print(f"\n--- SCRAPING DATE: {target_full} ---")
                    await fs_universal_popup_dismissal(page, "fs_home_page")
                    
                    try:
                        scheduled_tab_sel = await SelectorManager.get_selector_auto(page, "fs_home_page", "tab_scheduled")
                        if scheduled_tab_sel and await page.locator(scheduled_tab_sel).is_visible(timeout=5000):
                            await page.click(scheduled_tab_sel)
                            await asyncio.sleep(2.0)
                    except Exception:
                        pass
                    
                    matches_data = await extract_matches_from_page(page)
                    print(f"  [Schedule] Extracted {len(matches_data)} matches for {target_full}.")
                    
                    # Update dates and save metadata to local CSVs
                    for m in matches_data:
                        fixture_id = m.get('fixture_id')
                        m['date'] = target_full
                        save_schedule_entry({
                            'fixture_id': fixture_id, 'date': m.get('date'), 'match_time': m.get('match_time'),
                            'region_league': m.get('region_league'), 'home_team': m.get('home_team'),
                            'away_team': m.get('away_team'), 'home_team_id': m.get('home_team_id'),
                            'away_team_id': m.get('away_team_id'), 'match_status': 'scheduled',
                            'match_link': m.get('match_link')
                        })
                
                print("\n  [SUCCESS] Schedule scraping complete. Database populated.")
            except Exception as e:
                print(f"  [ERROR] Schedule Scraper failed: {e}")
            finally:
                if context: await context.close()
                if browser: await browser.close()

    elif args.rule_engine:
        from Core.Intelligence.rule_engine_manager import RuleEngineManager

        if args.list:
            print("\n  --- LEO: Rule Engine Registry ---")
            RuleEngineManager.print_engine_list()

        elif args.set_default:
            target = args.set_default
            # Try by name first, then by ID
            engines = RuleEngineManager.list_engines()
            engine_id = None
            for e in engines:
                if e["name"].lower() == target.lower() or e["id"] == target:
                    engine_id = e["id"]
                    break
            if engine_id and RuleEngineManager.set_default(engine_id):
                engine = RuleEngineManager.get_engine(engine_id)
                print(f"\n  ✅ Default engine set to: {engine['name']}")
                RuleEngineManager.print_engine(engine)
            else:
                print(f"\n  ❌ Engine '{target}' not found.")
                RuleEngineManager.print_engine_list()

        elif args.backtest:
            from Core.Intelligence.progressive_backtester import run_progressive_backtest
            engine_id = args.id or RuleEngineManager.get_default()["id"]
            start_date = args.from_date or "2025-08-01"
            await run_progressive_backtest(engine_id, start_date)

        else:
            # Default: show current default engine
            print("\n  --- LEO: Default Rule Engine ---")
            engine = RuleEngineManager.get_default()
            RuleEngineManager.print_engine(engine)


# ============================================================
# DISPATCH — Routes CLI args to the appropriate functions
# ============================================================

async def dispatch(args):
    """Route CLI arguments to the correct execution path."""
    init_csvs()

    async with async_playwright() as p:
        # --- Prologue ---
        if args.prologue:
            if args.page == 1:
                await run_prologue_p1(p)
            elif args.page == 2:
                await run_prologue_p2()
            elif args.page == 3:
                await run_prologue_p3()
            else:
                # All prologue pages sequentially
                await run_prologue_p1(p)
                await run_prologue_p2()
                await run_prologue_p3()
            return

        # --- Chapter ---
        if args.chapter == 1:
            if args.page == 1:
                await run_chapter_1_p1(p)
            elif args.page == 2:
                await run_chapter_1_p2(p)
            elif args.page == 3:
                await run_chapter_1_p3()
            else:
                await run_chapter_1_p1(p)
                fb_healthy = await run_chapter_1_p2(p)
                await run_chapter_1_p3()
            return

        if args.chapter == 2:
            if args.page == 1:
                await run_chapter_2_p1(p)
            elif args.page == 2:
                await run_chapter_2_p2(p)
            else:
                await run_chapter_2_p1(p)
                await run_chapter_2_p2(p)
            return

        if args.chapter == 3:
            await run_chapter_3()
            return

    # Should not reach here if --prologue or --chapter was set
    print("[ERROR] Unknown dispatch target.")


# ============================================================
# MAIN — Full cycle loop (default mode)
# ============================================================

async def main():
    """Full cycle: Prologue → Ch1 → Ch2 → Ch3, repeating on CYCLE_WAIT_HOURS."""
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
            # Spawn live score streamer in parallel
            streamer_task = asyncio.create_task(live_score_streamer(p))

            while True:
                try:
                    state["cycle_count"] += 1
                    state["cycle_start_time"] = dt.now()
                    cycle_num = state["cycle_count"]
                    log_state(chapter="Cycle Start", action=f"Starting Cycle #{cycle_num}")
                    log_audit_event("CYCLE_START", f"Cycle #{cycle_num} initiated.")

                    # ── PROLOGUE P1: Sequential (dependency for Chapter 1) ──
                    await run_prologue_p1(p)

                    # ── CONCURRENT: Prologue P2+P3 || Chapter 1→2 ──
                    print("\n" + "=" * 60)
                    print("  ⚡ CONCURRENT EXECUTION: Prologue P2+P3 || Chapter 1→2")
                    print("=" * 60)

                    async def _prologue_p2_p3():
                        await run_prologue_p2()
                        await run_prologue_p3()

                    async def _chapter_1_2():
                        await run_chapter_1_p1(p)
                        fb_healthy = await run_chapter_1_p2(p)
                        await run_chapter_1_p3()
                        if fb_healthy:
                            await run_chapter_2_p1(p)
                            await run_chapter_2_p2(p)
                        else:
                            print("\n" + "=" * 60)
                            print("  CHAPTER 2: SKIPPED — Football.com session unhealthy")
                            print("=" * 60)
                            log_audit_event("CH2_SKIPPED", "Skipped: Football.com session failed.", status="skipped")

                    await asyncio.gather(
                        _prologue_p2_p3(),
                        _chapter_1_2(),
                        return_exceptions=True
                    )

                    # ── CHAPTER 3: Monitoring ──
                    await run_chapter_3()

                    # ── CYCLE COMPLETE ──
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


# ============================================================
# ENTRY POINT — CLI Dispatcher
# ============================================================

if __name__ == "__main__":
    args = parse_args()
    log_file, original_stdout, original_stderr = setup_terminal_logging(args)

    # Determine which mode to run
    is_utility = any([args.sync, args.recommend, args.accuracy,
                      args.search_dict, args.review, args.backtest,
                      args.rule_engine, args.streamer, args.schedule])
    is_granular = args.prologue or args.chapter is not None

    try:
        if args.offline_repredict:
            asyncio.run(main_offline_repredict())
        elif is_utility:
            asyncio.run(run_utility(args))
        elif is_granular:
            asyncio.run(dispatch(args))
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        print("\n   --- LEO: Shutting down. ---")
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr
        log_file.close()
