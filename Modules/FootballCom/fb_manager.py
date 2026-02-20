# fb_manager.py: fb_manager.py: Orchestration layer for Football.com booking process.
# Part of LeoBook Modules — Football.com
#
# Functions: _create_session(), run_odds_harvesting(), run_automated_booking(), run_football_com_booking()

"""
Football.com Orchestrator — Decoupled v2.8
Two exported functions with shared session setup.
"""

import asyncio
from pathlib import Path
from playwright.async_api import Playwright

# Modular Imports
from .fb_setup import get_pending_predictions_by_date
from .fb_session import launch_browser_with_retry
from .fb_url_resolver import resolve_urls
from .navigator import load_or_create_session, extract_balance
from Core.Utils.utils import log_error_state
from Core.Utils.monitor import PageMonitor
from Core.System.lifecycle import log_state


async def _create_session(playwright: Playwright):
    """Shared session setup: launch browser, login, extract balance. Returns (context, page, balance)."""
    user_data_dir = Path("Data/Auth/ChromeData_v3").absolute()
    user_data_dir.mkdir(parents=True, exist_ok=True)

    context = await launch_browser_with_retry(playwright, user_data_dir)
    _, page = await load_or_create_session(context)
    PageMonitor.attach_listeners(page)

    current_balance = await extract_balance(page)
    print(f"  [Balance] Current: ₦{current_balance:.2f}")

    return context, page, current_balance


async def run_odds_harvesting(playwright: Playwright):
    """
    Chapter 1 Page 2: Odds Discovery & URL Resolution.
    Resolves Flashscore → Football.com URLs. Harvests booking codes per match.
    Does NOT place bets.
    """
    print("\n--- Running Football.com Odds Harvesting (Chapter 1C) ---")

    predictions_by_date = await get_pending_predictions_by_date()
    if not predictions_by_date:
        return

    max_restarts = 3
    restarts = 0

    while restarts <= max_restarts:
        context = None
        try:
            print(f"  [System] Launching Harvest Session (Restart {restarts}/{max_restarts})...")
            context, page, _ = await _create_session(playwright)
            log_state(chapter="Chapter 1C", action="Harvesting odds")

            for target_date, day_preds in sorted(predictions_by_date.items()):
                print(f"\n--- Date: {target_date} ({len(day_preds)} matches) ---")

                # 1. URL Resolution (Fuzzy match FS → FB)
                matched_urls = await resolve_urls(page, target_date, day_preds)
                if not matched_urls:
                    continue

                # 2. Odds Selection & Code Extraction
                print(f"  [Chapter 1C] Starting odds discovery for {target_date}...")
                from Modules.FootballCom.booker.booking_code import harvest_booking_codes
                await harvest_booking_codes(page, matched_urls, day_preds, target_date)

            break  # Success exit

        except Exception as e:
            is_fatal = "FatalSessionError" in str(type(e)) or "dirty" in str(e).lower()
            if is_fatal and restarts < max_restarts:
                print(f"\n[!!!] FATAL SESSION ERROR: {e}")
                restarts += 1
                if context:
                    await context.close()
                await asyncio.sleep(5)
                continue
            else:
                await log_error_state(None, "harvest_fatal", e)
                print(f"  [CRITICAL] Harvest failed: {e}")
                break
        finally:
            if context:
                try: await context.close()
                except: pass


async def run_automated_booking(playwright: Playwright):
    """
    Chapter 2 Page 1: Automated Booking.
    Reads harvested codes and places multi-bets. Does NOT harvest.
    """
    print("\n--- Running Automated Booking (Chapter 2A) ---")

    predictions_by_date = await get_pending_predictions_by_date()
    if not predictions_by_date:
        return

    # 1. Pre-fetch booking queue (Decoupling: Fetch THEN Act)
    booking_queue = {}
    print("  [System] Building booking queue from registry...")
    from Modules.FootballCom.fb_url_resolver import get_harvested_matches_for_date
    
    for target_date in sorted(predictions_by_date.keys()):
        harvested = await get_harvested_matches_for_date(target_date)
        if harvested:
            booking_queue[target_date] = harvested
            
    if not booking_queue:
        print("  [System] No harvested matches found for any pending dates. Exiting.")
        return

    max_restarts = 3
    restarts = 0

    while restarts <= max_restarts:
        context = None
        try:
            print(f"  [System] Launching Booking Session (Restart {restarts}/{max_restarts})...")
            context, page, current_balance = await _create_session(playwright)
            log_state(chapter="Chapter 2A", action="Placing bets")

            from Modules.FootballCom.booker.placement import place_multi_bet_from_codes

            for target_date, harvested in booking_queue.items():
                print(f"\n--- Booking Date: {target_date} ---")
                await place_multi_bet_from_codes(page, harvested, current_balance)
                log_state(chapter="Chapter 2A", action="Booking Complete", next_step=f"Processed {target_date}")

            break  # Success exit

        except Exception as e:
            is_fatal = "FatalSessionError" in str(type(e)) or "dirty" in str(e).lower()
            if is_fatal and restarts < max_restarts:
                print(f"\n[!!!] FATAL SESSION ERROR: {e}")
                restarts += 1
                if context:
                    await context.close()
                await asyncio.sleep(5)
                continue
            else:
                await log_error_state(None, "booking_fatal", e)
                print(f"  [CRITICAL] Booking failed: {e}")
                break
        finally:
            if context:
                try: await context.close()
                except: pass


# Backward compat — keep old name pointing to harvesting for any legacy callers
async def run_football_com_booking(playwright: Playwright):
    """Legacy wrapper: runs both harvesting and booking sequentially."""
    await run_odds_harvesting(playwright)
    await run_automated_booking(playwright)