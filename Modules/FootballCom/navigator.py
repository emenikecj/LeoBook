# navigator.py: navigator.py: High-level site navigation and state discovery for Football.com.
# Part of LeoBook Modules — Football.com
#
# Functions: log_page_title(), extract_balance(), perform_login(), load_or_create_session(), hide_overlays(), navigate_to_schedule(), select_target_date()

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

from Core.Browser.site_helpers import fb_universal_popup_dismissal
from Core.Intelligence.intelligence import fb_universal_popup_dismissal as neo_popup_dismissal
from Core.Intelligence.selector_manager import SelectorManager
from Core.Utils.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT
from Core.Utils.utils import capture_debug_snapshot
from Core.Utils.monitor import PageMonitor

PHONE = cast(str, os.getenv("FB_PHONE"))
PASSWORD = cast(str, os.getenv("FB_PASSWORD"))
AUTH_DIR = Path("Data/Auth")
AUTH_FILE = AUTH_DIR / "storage_state.json"

if not PHONE or not PASSWORD:
    raise ValueError("FB_PHONE and FB_PASSWORD environment variables must be set for login.")

async def log_page_title(page: Page, label: str = ""):
    """Logs the current page title and records it to the Page Registry."""
    try:
        title = await page.title()
        # print(f"  [Monitor] {label}: '{title}'")
        # Vigilant Capture
        await PageMonitor.capture(page, label)
        return title
    except Exception as e:
        print(f"  [Simple Log] Could not get title: {e}")
        return ""


async def extract_balance(page: Page) -> float:
    """Extract account balance with robustness for multiple calls."""
    print("  [Money] Retrieving account balance...")
    
    # Retry loop for balance extraction
    for attempt in range(3):
        try:
            # Refresh selector from manager in case of updates
            balance_sel = SelectorManager.get_selector_strict("fb_match_page", "navbar_balance")
            
            if balance_sel:
                # Wait for balance to be visible
                try:
                    await page.wait_for_selector(balance_sel, state="visible", timeout=5000)
                except:
                    pass
                
                if await page.locator(balance_sel).count() > 0:
                    balance_text = await page.locator(balance_sel).first.inner_text(timeout=3000)
                    # Remove currency symbols and formatting
                    import re
                    cleaned_text = re.sub(r'[^\d.]', '', balance_text)
                    if cleaned_text:
                        val = float(cleaned_text)
                        # print(f"  [Money] Found balance: {val}")
                        return val
            
            await asyncio.sleep(1)
        except Exception as e:
            print(f"  [Money Error] Attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)
            
    print("  [Money] Failed to extract balance after retries.")
    return 0.0


async def perform_login(page: Page):
    #print("  [Navigation] Going to Football.com...")
    # Go directly to main mobile page
    #await page.goto("https://www.football.com/ng", wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
    #await log_page_title(page, "Login Entry")
    await asyncio.sleep(2) # Reduced sleep

    
    try:
        
        # Checking for login inputs directly as per previous logic structure
        pass

        # print(f"  [Login] Trying login button selectors: {login_selectors}")

        # Debug: Print all clickable elements that might be login buttons
        try:
             # Generic clickables
            clickable_sel = SelectorManager.get_selector_strict("fb_global", "clickable_elements_generic")
            all_buttons = await page.query_selector_all(clickable_sel)
            # print(f"  [Debug] Found {len(all_buttons)} potential clickable elements")
            for i, btn in enumerate(all_buttons[:10]):  # Check first 10
                try:
                    text = await btn.inner_text()
                    classes = await btn.get_attribute('class') or ''
                    # if 'login' in text.lower() or 'login' in classes.lower() or 'user' in classes.lower():
                    #     print(f"  [Debug] Potential login element {i}: text='{text}', class='{classes}'")
                except:
                    pass
        except Exception as e:
            # print(f"  [Debug] Could not enumerate buttons: {e}")
            pass

        login_clicked = False
        login_sel = SelectorManager.get_selector_strict("fb_global", "login_button")
        
        if login_sel:
            try:
                if await page.locator(login_sel).count() > 0 and await page.locator(login_sel).is_visible():
                    await page.locator(login_sel).first.scroll_into_view_if_needed()
                    await page.locator(login_sel).first.click(force=True)
                    print(f"  [Login] Login button clicked using selector: {login_sel}")
                    login_clicked = True
                    await asyncio.sleep(3)
            except Exception as e:
                print(f"  [Login] Failed to click login with {login_sel}: {e}")

        # If selector failed, try predefined login element selectors from knowledge.json
        if not login_clicked:
            print("  [Login] Selector failed, trying predefined login element selectors...")
            try:
                # Get predefined login element selectors from knowledge.json
                login_element_selectors = [
                    SelectorManager.get_selector_strict("fb_login_page", "login_input_username"),
                    SelectorManager.get_selector_strict("fb_login_page", "login_input_password"),
                    SelectorManager.get_selector_strict("fb_login_page", "login_button_submit"),
                ]

                # Remove empty selectors
                login_element_selectors = [sel for sel in login_element_selectors if sel]

                for selector in login_element_selectors:
                    try:
                        if await page.locator(selector).count() > 0 and await page.locator(selector).is_visible():
                            await page.locator(selector).first.scroll_into_view_if_needed()
                            await page.locator(selector).first.click(force=True)
                            print(f"  [Login] Found and clicked login element using predefined selector: {selector}")
                            login_clicked = True
                            await asyncio.sleep(3)
                            break
                    except Exception as e:
                        continue

            except Exception as e:
                print(f"  [Login] Predefined selector search failed: {e}")

        if not login_clicked:
            print("  [Login] Warning: Could not find or click login button")
        
        
        # Get Selectors via Strict Lookup
        mobile_selector = SelectorManager.get_selector_strict("fb_login_page", "login_input_username")
        password_selector = SelectorManager.get_selector_strict("fb_login_page", "login_input_password")
        login_btn_selector = SelectorManager.get_selector_strict("fb_login_page", "login_button_submit")

        # Input Mobile Number
        print(f"  [Login] Filling mobile number using: {mobile_selector}")
        try:
             await page.wait_for_selector(mobile_selector, state="visible", timeout=30000)
             await page.locator(mobile_selector).scroll_into_view_if_needed()
             await page.fill(mobile_selector, PHONE)
        except Exception as e:
             print(f"  [Login Warning] Primary mobile selector failed: {e}. Trying fallback...")
             # Fallback to generic attribute selector
             mobile_fallback = SelectorManager.get_selector_strict("fb_login_page", "mobile_input_fallback")
             if mobile_fallback and await page.locator(mobile_fallback).count() > 0:
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
        await page.locator(login_btn_selector).first.scroll_into_view_if_needed()
        await page.locator(login_btn_selector).first.click(force=True)
        
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


async def load_or_create_session(context: BrowserContext) -> Tuple[BrowserContext, Page]:
    """
    Load session from valid persistent context and perform Step 0 validation checks.
    """
    print("  [Auth] Using Persistent Context. Verifying session...")

    await asyncio.sleep(3)
    
    # Ensure we have a page
    if not context.pages:
        page = await context.new_page()
    else:
        page = context.pages[0]

    # Navigate to check state if needed
    current_url = page.url
    if "football.com" not in current_url or current_url == "about:blank":
         # print("  [Auth] Initial navigation...")
         await page.goto("https://www.football.com/ng", wait_until='networkidle', timeout=NAVIGATION_TIMEOUT)
         
    
    # Step 0: Pre-Booking State Validation
    print("  [Auth] Step 0: Validating session state...")

    # A. Check Logged In Status
    not_logged_in_sel = SelectorManager.get_selector_strict("fb_global", "not_logged_in_indicator")
    if not_logged_in_sel:
        try:
             # If "not logged in" indicator is visible, we are logged out.
             if await page.locator(not_logged_in_sel).count() > 0 and await page.locator(not_logged_in_sel).is_visible(timeout=3000):
                 print("  [Auth] User is NOT logged in. Performing login flow...")
                 await perform_login(page)
             else:
                 # Double check if "logged in" indicator is visible
                 logged_in_sel = SelectorManager.get_selector_strict("fb_global", "logged_in_indicator")
                 if logged_in_sel and await page.locator(logged_in_sel).count() > 0:
                      pass # Valid
                 else:
                      # Ambiguous state, perform login to be safe logic could go here, 
                      # but for now assume if 'not_logged_in' is absent, we are good.
                      pass
        except Exception as e:
             # print(f"  [Auth] Login validation error: {e}")
             # Attempt login if validation fails?
             await perform_login(page)

    # B. Check Balance
    balance = await extract_balance(page)
    print(f"  [Auth] Current Account Balance: {balance}")
    if balance <= 10.0: # Minimum threshold warning
         print("  [Warning] Low balance detected!")

    # C. Aggressive Betslip Clear
    try:
        from .booker.slip import force_clear_slip
        await force_clear_slip(page)
    except ImportError:
        print("  [Auth] Warning: Could not import clear_bet_slip for Step 0 check.")
    except Exception as e:
        print(f"  [Auth] Failed to clear betslip checks: {e}")

    return context, page


async def hide_overlays(page: Page):
    """Inject CSS to hide obstructing overlays like bottom nav and download bars."""
    try:
        # Get selectors info
        overlay_sel = SelectorManager.get_selector_strict("fb_global", "overlay_elements")
        
        # Simplified CSS to avoid hiding core elements accidentally
        css_content = f"""
            {overlay_sel} {{
                display: none !important;
                visibility: hidden !important;
                pointer-events: none !important;
            }}
        """
        await page.add_style_tag(content=css_content)
        
        # Force JS hide for persistent elements
        await page.evaluate(f"document.querySelectorAll(\"{overlay_sel}\").forEach(el => el.style.display = 'none');")
        
       # print("  [UI] Overlays hidden via CSS injection.")
    except Exception as e:
        print(f"  [UI] Failed to hide overlays: {e}")


async def navigate_to_schedule(page: Page):
    """Simplified navigation to schedule."""
    await fb_universal_popup_dismissal(page)
    
    if "/sport/football/" in page.url:
         return await hide_overlays(page)

    # Use the selector from knowledge.json as per rule
    sel = SelectorManager.get_selector_strict("fb_global", "full_schedule_button")
    
    try:
        # Standard Playwright: Check visibility and click
        if sel and await page.locator(sel).is_visible(timeout=3000):
            await page.locator(sel).first.click(force=True)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        else:
            print("  [Navigation] Button not found, using direct URL.")
            await page.goto("https://www.football.com/ng/m/sport/football/", wait_until="domcontentloaded")
    except Exception:
        # Most reliable fallback
        await page.goto("https://www.football.com/ng/m/sport/football/", wait_until="domcontentloaded")
        
    await hide_overlays(page)
    

async def select_target_date(page: Page, target_date: str) -> bool:
    """Select the target date in the schedule and validate using dynamic and robust selectors."""

    # print(f"  [Navigation] Selecting date: {target_date}")
    await capture_debug_snapshot(page, "pre_date_select", f"Attempting to select {target_date}")

    # Dynamic Selector First
    dropdown_sel = SelectorManager.get_selector_strict("fb_schedule_page", "filter_dropdown_today")
    dropdown_found = False
    
    if dropdown_sel:
        try:
            if await page.locator(dropdown_sel).count() > 0:
                await page.locator(dropdown_sel).first.scroll_into_view_if_needed()
                await page.locator(dropdown_sel).first.click(force=True)
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
            # day_selector = f"text='{day}'" # Removed hardcoded
            day_item_tmpl = SelectorManager.get_selector_strict("fb_schedule_page", "day_list_item_template")
            day_item_sel = day_item_tmpl.replace("{day}", day)

            if await page.locator(day_item_sel).count() > 0:
                await page.locator(day_item_sel).first.scroll_into_view_if_needed()
                await page.locator(day_item_sel).first.click(force=True)
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
            sort_sel = SelectorManager.get_selector_strict("fb_schedule_page", "sort_dropdown")
            print(f"  [Debug] sort_sel: {sort_sel}")
            if sort_sel:
                if await page.locator(sort_sel).count() > 0:
                    await page.locator(sort_sel).first.scroll_into_view_if_needed()
                    await page.locator(sort_sel).first.click(force=True)
                    await asyncio.sleep(1)

                    # Try to select "League" from dropdown options (Content filter)
                    target_sort = "League"
                    list_sel = SelectorManager.get_selector_strict("fb_schedule_page", "sort_dropdown_list_container")
                    item_tmpl = SelectorManager.get_selector_strict("fb_schedule_page", "sort_dropdown_list_item_template")
                    item_sel = item_tmpl.replace("{sort}", target_sort)

                    await page.locator(f'{sort_sel} >> {list_sel}').wait_for(state="visible")
                    await page.locator(f'{sort_sel} >> {item_sel}').first.scroll_into_view_if_needed()
                    await page.locator(f'{sort_sel} >> {item_sel}').first.click(force=True)
                    print("  [Filter] Successfully sorted by League")
                    league_sorted = True
                    await asyncio.sleep(1)
                    break
                else:
                        print("  [Filter] Sort dropdown not visible on page")
                        
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
        time_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_row_time")
        
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
                                # print(f"  [Navigation] Page validation successful - found match times {sample_time} matching {target_date}")
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
