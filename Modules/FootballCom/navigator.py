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
from Core.Intelligence.aigo_suite import AIGOSuite

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


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_match_page", element_key="navbar_balance")
async def extract_balance(page: Page) -> float:
    """Extract account balance with AIGO self-healing safety net."""
    print("  [Money] Retrieving account balance...")
    
    # Refresh selector from manager in case of updates
    balance_sel = SelectorManager.get_selector_strict("fb_match_page", "navbar_balance")
    
    if balance_sel:
        # Wait for balance to be visible
        await page.wait_for_selector(balance_sel, state="visible", timeout=5000)
        
        if await page.locator(balance_sel).count() > 0:
            balance_text = await page.locator(balance_sel).first.inner_text(timeout=3000)
            # Remove currency symbols and formatting
            import re
            cleaned_text = re.sub(r'[^\d.]', '', balance_text)
            if cleaned_text:
                val = float(cleaned_text)
                return val
    
    raise ValueError("Balance element not found or empty.")


@AIGOSuite.aigo_retry(max_retries=2, delay=3.0, context_key="fb_global", element_key="login_button")
async def perform_login(page: Page):
    """Perform login with AIGO protection for the entire flow."""
    print("  [Auth] Initiating Football.com login flow...")
    
    # 1. Navigate to main page
    await page.goto("https://www.football.com/ng", wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
    await asyncio.sleep(2)

    # 2. Click Login Button to open modal/page
    login_sel = SelectorManager.get_selector_strict("fb_global", "login_button")
    if await page.locator(login_sel).count() > 0:
        await page.locator(login_sel).first.click(force=True)
        await asyncio.sleep(2)
    
    # 3. Get Credentials Selectors
    mobile_selector = SelectorManager.get_selector_strict("fb_login_page", "login_input_username")
    password_selector = SelectorManager.get_selector_strict("fb_login_page", "login_input_password")
    login_btn_selector = SelectorManager.get_selector_strict("fb_login_page", "login_button_submit")

    # 4. Input Mobile Number
    print(f"  [Login] Filling mobile number...")
    await page.wait_for_selector(mobile_selector, state="visible", timeout=10000)
    await page.fill(mobile_selector, PHONE)

    # 5. Input Password
    print(f"  [Login] Filling password...")
    await page.wait_for_selector(password_selector, state="visible", timeout=5000)
    await page.fill(password_selector, PASSWORD)

    # 6. Click Submit
    print(f"  [Login] Clicking login submit...")
    await page.locator(login_btn_selector).first.click(force=True)
    
    # 7. Final Validation
    await page.wait_for_load_state('networkidle', timeout=30000)
    await asyncio.sleep(5)
    print("[Login] Football.com Login process completed.")


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


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_global", element_key="full_schedule_button")
async def navigate_to_schedule(page: Page):
    """Simplified navigation to schedule with AIGO safety net."""
    await fb_universal_popup_dismissal(page)
    
    if "/sport/football/" in page.url:
         return await hide_overlays(page)

    sel = SelectorManager.get_selector_strict("fb_global", "full_schedule_button")
    
    # Standard Playwright: Check visibility and click
    if sel and await page.locator(sel).count() > 0:
        await page.locator(sel).first.click(force=True)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    else:
        # Direct URL as fallback
        await page.goto("https://www.football.com/ng/m/sport/football/", wait_until="domcontentloaded")
        
    await hide_overlays(page)
    

@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_schedule_page", element_key="filter_dropdown_today")
async def select_target_date(page: Page, target_date: str) -> bool:
    """Select target date with AIGO self-healing."""
    await capture_debug_snapshot(page, "pre_date_select", f"Attempting to select {target_date}")

    dropdown_sel = SelectorManager.get_selector_strict("fb_schedule_page", "filter_dropdown_today")
    if not dropdown_sel or await page.locator(dropdown_sel).count() == 0:
        raise ValueError(f"Date dropdown '{dropdown_sel}' not found.")

    await page.locator(dropdown_sel).first.click(force=True)
    await asyncio.sleep(1)

    # ... remaining date selection logic ...
    target_dt = dt.strptime(target_date, "%d.%m.%Y")
    day_str = "Today" if target_dt.date() == dt.now().date() else target_dt.strftime("%A")
    
    day_item_tmpl = SelectorManager.get_selector_strict("fb_schedule_page", "day_list_item_template")
    day_item_sel = day_item_tmpl.replace("{day}", day_str)

    if await page.locator(day_item_sel).count() == 0:
        # Try short day format
        day_item_sel = day_item_tmpl.replace("{day}", target_dt.strftime("%a"))
    
    if await page.locator(day_item_sel).count() > 0:
        await page.locator(day_item_sel).first.click(force=True)
    else:
        raise ValueError(f"Target day '{day_str}' not found in dropdown.")

    await page.wait_for_load_state('networkidle', timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)

    # Mandatory Sort by League
    sort_sel = SelectorManager.get_selector_strict("fb_schedule_page", "sort_dropdown")
    if sort_sel and await page.locator(sort_sel).count() > 0:
        await page.locator(sort_sel).first.click(force=True)
        await asyncio.sleep(1)
        item_tmpl = SelectorManager.get_selector_strict("fb_schedule_page", "sort_dropdown_list_item_template")
        item_sel = item_tmpl.replace("{sort}", "League")
        await page.locator(item_sel).first.click(force=True)
    
    return True


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
