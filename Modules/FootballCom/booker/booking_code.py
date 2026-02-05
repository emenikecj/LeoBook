"""
Bet Placement Orchestration
Handles adding selections to the slip and finalizing accumulators.
"""

import asyncio
from typing import List, Dict
from pathlib import Path
from datetime import datetime as dt
from playwright.async_api import Page
from Core.Browser.site_helpers import get_main_frame
from Data.Access.db_helpers import (
    update_prediction_status, 
    update_site_match_status, 
    get_site_match_id
)
from Core.Utils.utils import log_error_state, capture_debug_snapshot
# Corrected Imports for Core.Intelligence
from Core.Intelligence.selector_manager import SelectorManager
from Core.Intelligence.intelligence import get_selector, get_selector_auto, fb_universal_popup_dismissal as neo_popup_dismissal

from .ui import handle_page_overlays, dismiss_overlays
from .mapping import find_market_and_outcome
from .slip import get_bet_slip_count
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

async def ensure_bet_insights_collapsed(page: Page):
    """Ensure the bet insights widget is collapsed to prevent obstruction."""
    try:
        header = page.locator('div.srct-widget-header_custom').first
        if await header.count() > 0:
            arrow = header.locator('div.srct-widget-header_custom-arrow')
            if await arrow.count() > 0:
                is_expanded = await arrow.evaluate('el => el.classList.contains("rotate-arrow")')
                if is_expanded:
                    print("    [UI] Collapsing Bet Insights widget...")
                    await header.scroll_into_view_if_needed()
                    await header.click()
                    # Wait for collapse animation or arrow status change
                    try:
                       await arrow.wait_for(state='visible', timeout=2000)
                    except:
                       pass
    except Exception as e:
        print(f"    [UI] Bet Insights collapse check failed (non-critical): {e}")


async def check_match_start_time(page: Page) -> bool:
    """Check if the match is within 10 minutes of starting time."""
    try:
        # Get match time using dynamic selector
        time_sel = await get_selector_auto(page, "fb_match_page", "match_detail_time_elapsed")
        if not time_sel:
            time_sel = await get_selector_auto(page, "fb_match_page", "match_detail_status")

        if time_sel:
            if await page.locator(time_sel).count() > 0:
                time_text = await page.locator(time_sel).first.inner_text(timeout=3000)
                if time_text:
                    time_text = time_text.strip().lower()
                    print(f"    [Time Check] Match status: '{time_text}'")

                    # Check for ongoing or finished matches
                    if any(keyword in time_text for keyword in ['live', 'in play', 'ft', 'finished', 'ended', 'postponed']):
                        print("    [Time Check] Match is already live or finished. Skipping.")
                        return False

                    # Check for countdown time
                    if ':' in time_text and any(char.isdigit() for char in time_text):
                        # Try to parse time format like "45:00" or "15:30"
                        try:
                            # Extract time part (assume format like "15:30" or just "15:30")
                            time_part = time_text.replace(' ', '')
                            if time_part.count(':') == 1:
                                minutes_str, seconds_str = time_part.split(':')
                                if minutes_str.isdigit() and seconds_str.isdigit():
                                    minutes = int(minutes_str)
                                    seconds = int(seconds_str)
                                    total_seconds = minutes * 60 + seconds

                                    # Check if match is within 10 minutes (600 seconds) of starting
                                    if total_seconds <= 600:  # 10 minutes = 600 seconds
                                        print(f"    [Time Check] Match starts in {minutes}:{seconds:02d} ({total_seconds}s) - within 10 minutes. Proceeding.")
                                        return True
                                    else:
                                        print(f"    [Time Check] Match starts in {minutes}:{seconds:02d} ({total_seconds}s) - too far ahead. Skipping.")
                                        return False
                        except ValueError:
                            pass

                    # If we can't parse the time but it's not clearly live/finished, assume it's okay to check
                    print("    [Time Check] Could not parse exact time, but match doesn't appear live. Proceeding.")
                    return True

        # Fallback: check for live indicators
        live_indicators = [
            "div.live-in-play-icon",
            "[data-testid='wcl-icon-live']",
            ".live-tag",
            "span.live-in-play-icon"
        ]

        for indicator in live_indicators:
            if await page.locator(indicator).count() > 0:
                print("    [Time Check] Found live indicator. Match is already in progress. Skipping.")
                return False

        print("    [Time Check] No clear time or live indicators found. Assuming match is upcoming.")
        return True

    except Exception as e:
        print(f"    [Time Check] Error checking match time: {e}. Assuming safe to proceed.")
        return True

async def harvest_booking_codes(page: Page, matched_urls: Dict[str, str], day_predictions: List[Dict], target_date: str):
    """
    Phase 2a: Harvest individual booking codes for each matched fixture.
    Follows flowchart: Navigate -> Select -> Book -> Save Code -> Clear Slip.
    """
    from .slip import force_clear_slip
    processed_urls = set()

    # Pre-emptive clear ensuring a fresh start
    await force_clear_slip(page)

    for match_id, match_url in matched_urls.items():
        if not match_url or match_url in processed_urls: continue
        
        pred = next((p for p in day_predictions if str(p.get('fixture_id', '')) == str(match_id)), None)
        if not pred or pred.get('prediction') == 'SKIP': continue

        print(f"\n   [Harvest] Processing: {pred['home_team']} vs {pred['away_team']}")
        processed_urls.add(match_url)

        try:
            # 1. Navigation
            await page.goto(match_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)
            await neo_popup_dismissal(page, "fb_match_page")
            await ensure_bet_insights_collapsed(page)

            # 2. Market/Outcome Logic
            m_name, o_name = await find_market_and_outcome(pred)
            if not m_name:
                print(f"    [Info] No market found for prediction: {pred.get('prediction', 'N/A')}")
                continue

            # 3. Search & Click Outcome
            # (Re-using search/click logic with improvements)
            bet_added = await find_and_click_outcome(page, m_name, o_name)
            
            if bet_added:
                # 4. Extract Code (The "Book Single" step)
                book_btn_sel = await get_selector_auto(page, "fb_match_page", "book_bet_button")
                if book_btn_sel and await page.locator(book_btn_sel).count() > 0:
                    print(f"    [Booking] Clicking Book-a-Bet button...")
                    await page.locator(book_btn_sel).first.scroll_into_view_if_needed()
                    await page.locator(book_btn_sel).first.click(force=True)
                    await asyncio.sleep(2)

                    booking_code = await extract_booking_details(page)
                    if booking_code and booking_code != "N/A":
                        # Save to registries
                        update_prediction_status(match_id, target_date, 'harvested', booking_code=booking_code)
                        site_id = get_site_match_id(target_date, pred['home_team'], pred['away_team'])
                        update_site_match_status(site_id, 'harvested', booking_code=booking_code)
                        await save_booking_code(target_date, booking_code, page)
                
                # Close Modal if open
                close_sel = await get_selector_auto(page, "fb_match_page", "modal_close_button")
                if close_sel and await page.locator(close_sel).count() > 0:
                    await page.locator(close_sel).first.click()
                    await asyncio.sleep(1)

                # 5. Force Clear Slip (Crucial step in flowchart)
                await force_clear_slip(page)
            else:
                print(f"    [Error] Could not add outcome '{o_name}' for matching fixture.")
                update_prediction_status(match_id, target_date, 'failed_harvest')

        except Exception as e:
            print(f"    [Error] Harvest failed for match {match_id}: {e}")
            await capture_debug_snapshot(page, f"harvest_fail_{match_id}")

async def find_and_click_outcome(page: Page, m_name: str, o_name: str) -> bool:
    """Helper to search for and click the outcome button."""
    frame = await get_main_frame(page)
    if not frame: return False

    # (Same robust search logic as before, distilled for clarity)
    search_sel = await get_selector_auto(page, "fb_match_page", "search_icon")
    input_sel = await get_selector_auto(page, "fb_match_page", "search_input")
    
    if not search_sel or not input_sel: return False

    try:
        await page.locator(search_sel).first.scroll_into_view_if_needed()
        await page.locator(search_sel).first.click(force=True)
        await asyncio.sleep(0.5)
        await page.locator(input_sel).first.fill(m_name)
        await page.keyboard.press("Enter")
        await asyncio.sleep(2)

        # Outcome discovery
        outcome_sel = f"button:has-text('{o_name}'), div[role='button']:has-text('{o_name}'), .m-outcome-item:has-text('{o_name}')"
        if await frame.locator(outcome_sel).count() > 0:
             count_before = await get_bet_slip_count(page)
             await frame.locator(outcome_sel).first.scroll_into_view_if_needed()
             await frame.locator(outcome_sel).first.click(force=True)
             await asyncio.sleep(1)
             return await get_bet_slip_count(page) > count_before
    except:
        pass
    return False

async def finalize_accumulator(page: Page, target_date: str) -> bool:
    """Navigate to slip, enter stake, and confirm placement."""
    print(f"[Betting] Finalizing accumulator for {target_date}...")
    try:
        await dismiss_overlays(page)
        await handle_page_overlays(page)
        # Refresh state after dismissals
        await asyncio.sleep(1)
        await page.keyboard.press("End")
        
        # Check if slip is open
        drawer_sel = await get_selector_auto(page, "fb_match_page", "slip_drawer_container")
        is_open = False
        if drawer_sel:
             is_open = await page.locator(drawer_sel).first.is_visible(timeout=500)

        if not is_open:
            trigger_sel = await get_selector_auto(page, "fb_match_page", "slip_trigger_button")
            if trigger_sel:
                await page.locator(trigger_sel).first.scroll_into_view_if_needed()
                if await page.locator(trigger_sel).first.click(force=True):
                    await asyncio.sleep(3)
            else:
                print("    [Betting] Slip trigger selector missing")

        # Ensure 'Multiple' tab is selected for accumulators
        multi_sel = await get_selector_auto(page, "fb_match_page", "slip_tab_multiple")
        
        if multi_sel and await page.locator(multi_sel).count() > 0:
            if await page.locator(multi_sel).is_visible(timeout=2000):
                await page.locator(multi_sel).scroll_into_view_if_needed()
                await page.locator(multi_sel).click(force=True)
                await asyncio.sleep(1)

        # Enter Stake
        stake_sel = await get_selector_auto(page, "fb_match_page", "stake_input")
        stake_entered = False
        
        if stake_sel:
            try:
                if await page.locator(stake_sel).count() > 0:
                    input_field = page.locator(stake_sel).first
                    await input_field.scroll_into_view_if_needed()
                    await input_field.click(force=True)
                    await input_field.fill("1")
                    await page.keyboard.press("Enter")
                    print(f"    [Betting] Entered stake with selector: {stake_sel}")
                    stake_entered = True
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"    [Betting] Stake selector failed: {stake_sel} - {e}")

        if not stake_entered:
            print("    [Warning] Could not enter stake. Attempting to place anyway.")

        # Place bet
        place_sel = await get_selector_auto(page, "fb_match_page", "place_bet_button")
        bet_placed = False
        
        if place_sel:
            try:
                await page.locator(place_sel).first.scroll_into_view_if_needed()
                if await page.locator(place_sel).first.click(force=True):
                    print(f"    [Betting] Clicked place bet with selector: {place_sel}")
                    bet_placed = True
                    await asyncio.sleep(2)
            except Exception as e:
                print(f"    [Betting] Place bet selector failed: {place_sel} - {e}")

        if not bet_placed:
            print("    [Betting] Could not place bet")
            return False

        # Confirm bet
        confirm_sel = await get_selector_auto(page, "fb_match_page", "confirm_bet_button")
        
        if confirm_sel:
            try:
                if await page.locator(confirm_sel).count() > 0:
                    await page.locator(confirm_sel).first.scroll_into_view_if_needed()
                    await page.locator(confirm_sel).first.click(force=True)
                    print(f"    [Betting] Confirmed bet with selector: {confirm_sel}")
                    await asyncio.sleep(3)
                    
                    # Extract and save booking code
                    booking_code = await extract_booking_details(page)
                    if booking_code and booking_code != "N/A":
                        await save_booking_code(target_date, booking_code, page)
                    
                    print(f"    [Success] Placed for {target_date}")
                    return True
            except Exception as e:
                 print(f"    [Betting] Confirm selector failed: {confirm_sel} - {e}")

        print("    [Betting] Could not confirm bet")
        return False
    except Exception as e:
        await log_error_state(page, "finalize_fatal", e)
    return False

async def extract_booking_details(page: Page) -> str:
    """Extract booking code using dynamic selector."""
    code_sel = await get_selector_auto(page, "fb_match_page", "booking_code_text")
    
    if code_sel:
        try:
            if await page.locator(code_sel).count() > 0:
                code = await page.locator(code_sel).first.inner_text()
                if code and code.strip():
                    print(f"    [Booking] Code: {code.strip()}")
                    return code.strip()
        except Exception as e:
            print(f"    [Booking] Code selector failed: {code_sel} - {e}")
            
    print("    [Booking] Could not extract booking code")
    return "N/A"


async def save_booking_code(target_date: str, booking_code: str, page: Page):
    """
    Save booking code to file and capture betslip screenshot.
    Stores in DB/bookings.txt with timestamp and date association.
    """
    from pathlib import Path
    
    try:
        # Save to bookings file
        db_dir = Path("DB")
        db_dir.mkdir(exist_ok=True)
        bookings_file = db_dir / "bookings.txt"
        
        timestamp = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        booking_entry = f"{timestamp} | Date: {target_date} | Code: {booking_code}\n"
        
        with open(bookings_file, "a", encoding="utf-8") as f:
            f.write(booking_entry)
        
        print(f"    [Booking] Saved code {booking_code} to bookings.txt")
        
        # Capture betslip screenshot for records
        try:
            screenshot_path = db_dir / f"betslip_{booking_code}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"    [Booking] Saved screenshot to {screenshot_path.name}")
        except Exception as screenshot_error:
            print(f"    [Booking] Screenshot failed: {screenshot_error}")
            
    except Exception as e:
        print(f"    [Booking] Failed to save booking code: {e}")

