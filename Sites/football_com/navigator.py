"""
Navigator Module
Handles login, session management, balance extraction, and schedule navigation for Football.com.
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime as dt
from typing import Tuple, Optional, cast

from playwright.async_api import Browser, BrowserContext, Page

from Helpers.Site_Helpers.site_helpers import fb_universal_popup_dismissal
from Neo.intelligence import get_selector, get_selector_auto, fb_universal_popup_dismissal as neo_popup_dismissal
from Neo.selector_manager import SelectorManager
from Helpers.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT
from Helpers.utils import capture_debug_snapshot

PHONE = cast(str, os.getenv("FB_PHONE"))
PASSWORD = cast(str, os.getenv("FB_PASSWORD"))
AUTH_DIR = Path("DB/Auth")
AUTH_FILE = AUTH_DIR / "storage_state.json"

if not PHONE or not PASSWORD:
    raise ValueError("FB_PHONE and FB_PASSWORD environment variables must be set for login.")


async def load_or_create_session(browser: Browser) -> Tuple[BrowserContext, Page]:
    """Load saved session or create new one with login."""
    if AUTH_FILE.exists():
        print("  [Auth] Found saved session. Loading state...")
        try:
            context = await browser.new_context(
                storage_state=str(AUTH_FILE), 
                viewport={'width': 375, 'height': 612},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
            )
            page = await context.new_page()
            await page.goto("https://www.football.com/ng/", wait_until='networkidle', timeout=NAVIGATION_TIMEOUT)
 
            await asyncio.sleep(5)
            # Validate session by checking for login elements
            login_sel = await get_selector_auto(page, "fb_login_page", "top_right_login")
            if login_sel and await page.locator(login_sel).count() > 0:
                print("  [Auth] Session expired. Performing new login...")
                await perform_login(page)
        except Exception as e:
            print(f"  [Auth] Failed to load session: {e}. Deleting corrupted file and logging in anew...")
            AUTH_FILE.unlink(missing_ok=True)
            context = await browser.new_context(
                viewport={'width': 375, 'height': 612},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
            )
            page = await context.new_page()
            await perform_login(page)
    else:
        print("  [Auth] No saved session found. Performing new login...")
        context = await browser.new_context(
            viewport={'width': 375, 'height': 612},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        await perform_login(page)

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(AUTH_FILE))
    #await neo_popup_dismissal(page, "fb_generic", monitor_interval=90)  # Advanced popup handling
    return context, page


async def perform_login(page: Page):
    print("  [Navigation] Going to Football.com...")
    # Go directly to sports/football if possible, or main mobile page
    await page.goto("https://www.football.com/ng/m/sport/football/", wait_until='networkidle', timeout=NAVIGATION_TIMEOUT)
    await asyncio.sleep(5)
    
    try:
        # Click Top Login Button (if visible)
        login_selector = await get_selector_auto(page, "fb_login_page", "top_right_login")
        if login_selector and await page.locator(login_selector).count() > 0:
             if await page.locator(login_selector).is_visible():
                 await page.click(login_selector)
                 print("  [Login] Login page clicked")
                 await asyncio.sleep(3)
        
        # Get Selectors via Auto-Heal
        mobile_selector = await get_selector_auto(page, "fb_login_page", "center_input_mobile_number")
        password_selector = await get_selector_auto(page, "fb_login_page", "center_input_password")
        login_btn_selector = await get_selector_auto(page, "fb_login_page", "bottom_button_login")

        # Fallbacks if Auto-Heal returns nothing valid
        if not mobile_selector: mobile_selector = "input[type='tel'], input[placeholder*='Mobile']"
        if not password_selector: password_selector = "input[type='password']"
        if not login_btn_selector: login_btn_selector = "button:has-text('Login')"

        # Input Mobile Number
        print(f"  [Login] Filling mobile number using: {mobile_selector}")
        try:
             await page.wait_for_selector(mobile_selector, state="visible", timeout=30000)
             await page.locator(mobile_selector).scroll_into_view_if_needed()
             await page.fill(mobile_selector, PHONE)
        except Exception as e:
             print(f"  [Login Warning] Primary mobile selector failed: {e}. Trying fallback 'input[type=tel]'...")
             # Fallback to generic attribute selector
             mobile_fallback = "input[type='tel']"
             if await page.locator(mobile_fallback).count() > 0:
                await page.fill(mobile_fallback, PHONE)
             else:
                raise e # Re-raise if fallback also fails

        await asyncio.sleep(1)

        # Input Password
        print(f"  [Login] Filling password using: {password_selector}")
        await page.wait_for_selector(password_selector, state="visible", timeout=10000)
        await page.fill(password_selector, PASSWORD)
        await asyncio.sleep(1)

        # Click Login
        print(f"  [Login] Clicking login button using: {login_btn_selector}")
        await page.click(login_btn_selector)
        
        await page.wait_for_load_state('networkidle', timeout=30000)
        await asyncio.sleep(5)
        print("[Login] Football.com Login Successful.")
        
    except Exception as e:
        print(f"[Login Error] {e}")
        # One last ditch effort: Keyboard interactions if everything else failed
        print("  [Login Rescue] Attempting keyboard interaction...")
        try:
            await page.keyboard.press("Tab")
            await page.keyboard.press("Tab") # Navigate around hoping to hit inputs
        except:
            pass
        raise


async def extract_balance(page: Page) -> float:
    """Extract account balance."""
    print("  [Money] Retrieving account balance...")
    await asyncio.sleep(2)
    try:
        balance_sel = await get_selector_auto(page, "fb_match_page", "navbar_balance")
        await asyncio.sleep(2)
        if balance_sel and await page.locator(balance_sel).count() > 0:
            balance_text = await page.locator(balance_sel).inner_text(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
            import re
            cleaned_text = re.sub(r'[^\d.]', '', balance_text)
            if cleaned_text:
                #print(f"  [Money] Found balance: {balance_text}")
                return float(cleaned_text)
    except Exception as e:
        print(f"  [Money Error] Could not parse balance: {e}")
    return 0.0


async def hide_overlays(page: Page):
    """Inject CSS to hide obstructing overlays like bottom nav and download bars."""
    try:
        # Simplified CSS to avoid hiding core elements accidentally
        await page.add_style_tag(content="""
            .m-bottom-nav, .place-bet, .app-download-bar, .promotion-popup-wrapper, 
            .download-app-bar, .cookie-banner {
                display: none !important;
                visibility: hidden !important;
                pointer-events: none !important;
            }
        """)
        # Force JS hide for persistent elements
        await page.evaluate("""() => {
            document.querySelectorAll('.m-bottom-nav, .place-bet, .app-download-bar').forEach(el => el.style.display = 'none');
        }""")
       # print("  [UI] Overlays hidden via CSS injection.")
    except Exception as e:
        print(f"  [UI] Failed to hide overlays: {e}")


async def navigate_to_schedule(page: Page):
    """Navigate to the full schedule page using dynamic selectors."""
    
    # Try dynamic selector first
    schedule_sel = get_selector("fb_main_page", "full_schedule_button")
    
    if schedule_sel:
        try:
            print(f"  [Navigation] Trying dynamic selector: {schedule_sel}")
            if await page.locator(schedule_sel).count() > 0:
                await page.locator(schedule_sel).first.click(timeout=5000)
                await page.wait_for_load_state('domcontentloaded', timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                print("  [Navigation] Schedule page loaded via dynamic selector.")
                await hide_overlays(page)
                return
            else:
                 print(f"  [Navigation] Dynamic selector not found on page: {schedule_sel}")
        except Exception as e:
            print(f"  [Navigation] Dynamic selector failed: {e}")

    # Fallback: direct URL navigation
    print("  [Navigation] Dynamic selector failed. Using direct URL navigation.")
    await page.goto("https://www.football.com/ng/m/sport/football/", wait_until='domcontentloaded', timeout=30000)
    print("  [Navigation] Schedule page loaded via direct URL.")
    await hide_overlays(page)
    await asyncio.sleep(1)
    

async def select_target_date(page: Page, target_date: str) -> bool:
    """Select the target date in the schedule and validate using dynamic and robust selectors."""

    print(f"  [Navigation] Selecting date: {target_date}")
    await capture_debug_snapshot(page, "pre_date_select", f"Attempting to select {target_date}")

    # Dynamic Selector First
    dropdown_sel = get_selector("fb_schedule_page", "filter_dropdown_today")
    dropdown_found = False
    
    if dropdown_sel:
        try:
            if await page.locator(dropdown_sel).count() > 0:
                await page.locator(dropdown_sel).first.click()
                print(f"  [Filter] Clicked date dropdown with selector: {dropdown_sel}")
                dropdown_found = True
                await asyncio.sleep(1)
        except Exception as e:
            print(f"  [Filter] Dropdown selector failed: {dropdown_sel} - {e}")
            
    if not dropdown_found:
        print("  [Filter] Could not find date dropdown")
        await capture_debug_snapshot(page, "fail_date_dropdown", "Could not find the date dropdown selector.")
        return False

    # Parse target date and select appropriate day
    target_dt = dt.strptime(target_date, "%d.%m.%Y")
    if target_dt.date() == dt.now().date():
        possible_days = ["Today"]
    else:
        full_day = target_dt.strftime("%A")
        short_day = target_dt.strftime("%a")
        possible_days = [full_day, short_day]

    print(f"  [Filter] Target day options: {possible_days}")

    # Try to find and click the target day
    day_found = False
    league_sorted = False
    
    for day in possible_days:
        try:
            # Try specific dynamic item selector if available + text filter
            day_selector = f"text='{day}'"
            if await page.locator(day_selector).count() > 0:
                await page.locator(f'li:has-text("{day}")').click()
                print(f"  [Filter] Successfully selected: {day}")
                day_found = True
            else:
                continue
        except Exception as e:
            print(f"  [Filter] Failed to select {day}: {e}")
            continue

        await page.wait_for_load_state('networkidle', timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
        await asyncio.sleep(1)

        # Sort by League (Mandatory)
        try:
            sort_sel = get_selector("fb_schedule_page", "sort_dropdown")
            print(f"  [Debug] sort_sel: {sort_sel}")
            if sort_sel:
                if await page.locator(sort_sel).count() > 0:
                    await page.locator(sort_sel).first.click()
                    await asyncio.sleep(1)

                    # Try to select "League" from dropdown options (Content filter)
                    target_sort = "League"
                    league_selector = f"text='{target_sort}'"
                    await page.locator(f'{sort_sel} >> div.m-list').wait_for(state="visible")
                    await page.locator(f'{sort_sel} >> li:has-text("{target_sort}")').click()
                    print("  [Filter] Successfully sorted by League")
                    league_sorted = True
                    await asyncio.sleep(1)
                    break
                else:
                        print(f"  [Filter] League option not found using: {league_selector}")
                        
        except Exception as e:
            print(f"  [Filter] League sorting failed: {e}")

        if day_found and not league_sorted:
             print(f"  [Filter] Date selected but mandatory League sorting failed.")
             await capture_debug_snapshot(page, "fail_league_sort", "Date selected, but failed to sort by League.")
             return False

    if not day_found:
        print(f"  [Filter] Day {possible_days} not available in dropdown for {target_date}")
        await capture_debug_snapshot(page, "fail_day_select", f"Could not find day options {possible_days}")
        return False

    if not league_sorted:
        print(f"  [Filter] Mandatory sorting (Date & League) failed for {target_date}")
        return False


    # Date validation - check if target date was selected
    try:
        # Look for any match time elements to validate we're on the right date page
        # User Requirement: Use dynamically retrieved 'match_row_time'
        time_sel = get_selector("fb_schedule_page", "match_row_time")
        
        if time_sel:
            try:
                if await page.locator(time_sel).count() > 0:
                    sample_time = (await page.locator(time_sel).first.inner_text(timeout=3000)).strip()
                    if sample_time:
                        try:
                            # Intelligent Date Validation: Compare "29 Dec" (sample) with "29.12" (target)
                            target_dt = dt.strptime(target_date, "%d.%m.%Y")
                            
                            # Sample format expected: "29 Dec, 17:00"
                            date_part_str = sample_time.split(',')[0].strip()
                            # Append target year to handle leap years correctly during parsing
                            sample_dt = dt.strptime(f"{date_part_str} {target_dt.year}", "%d %b %Y")
                            
                            if sample_dt.day == target_dt.day and sample_dt.month == target_dt.month:
                                print(f"  [Navigation] Page validation successful - found match times {sample_time} matching {target_date}")
                                return True
                            else:
                                print(f"  [Navigation] Validation Mismatch: Page shows {sample_time}, expected {target_date}")
                                return False
                        except ValueError:
                            print(f"  [Navigation] Validation warning: Could not parse date from '{sample_time}'. Assuming invalid.")
                            return False
            except Exception:
                pass
        
        print("  [Navigation] Page validation warning: Time elements not found using configured selector")
        return True
    
    except Exception as e:
        print(f"  [Navigation] Page validation logic failed (non-critical): {e}")
        return False
