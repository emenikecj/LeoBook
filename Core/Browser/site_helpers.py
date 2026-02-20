# site_helpers.py: site_helpers.py: General browser automation helpers for Flashscore and Football.com.
# Part of LeoBook Core — Browser Automation
#
# Functions: fs_universal_popup_dismissal(), accept_cookies_robust(), click_next_day(), fb_universal_popup_dismissal(), get_main_frame()

import asyncio # Keep asyncio for async operations
from typing import Optional # Keep Optional for type hinting
from playwright.async_api import Page, TimeoutError, Frame # Import Frame
from Core.Intelligence.intelligence import get_selector

async def fs_universal_popup_dismissal(page: Page, context: str = "fs_generic"):
    """Universal pop-up dismissal for Flashscore."""
    await accept_cookies_robust(page)

    try:
        understand_selectors = [
            get_selector(context, 'tooltip_i_understand_button'),
            "button:has-text('I understand')",
        ]
        for sel in understand_selectors:
            if sel:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible(timeout=10000):
                    await btn.click(timeout=2000, force=True)
                    print(f"    [Popup Handler] Clicked 'I understand' button via: {sel}")
                    await asyncio.sleep(0.5)
                    return # Assume one popup is enough for now
    except Exception:
        pass

async def accept_cookies_robust(page: Page):
    """Handles cookie consent dialogs across different patterns."""
    try:
        onetrust_sel = get_selector('fs_home_page', 'cookie_accept_onetrust')
        if onetrust_sel:
            onetrust_btn = page.locator(onetrust_sel)
            if await onetrust_btn.is_visible(timeout=2000):
                await onetrust_btn.click()
                print("    [Cookies] Accepted via OneTrust")
                await asyncio.sleep(0.5)
                return
    except Exception:
        pass

    try:
        cookie_sel = get_selector('fs_home_page', 'cookie_accept_button')
        if cookie_sel and await page.locator(cookie_sel).is_visible(timeout=1000):
            await page.locator(cookie_sel).click()
            print(f"    [Cookies] Accepted via AI selector")
            await asyncio.sleep(0.5)
            return
    except Exception:
        pass

    try:
        for text in ["Accept All", "I Agree", "Allow All", "Accept Cookies", "I Accept"]:
            btn = page.get_by_role("button", name=text, exact=True).first
            if await btn.is_visible(timeout=500):
                await btn.click()
                print(f"    [Cookies] Accepted via text: {text}")
                return
    except Exception:
        pass

async def click_next_day(page: Page, match_row_selector: str) -> bool:
    """Clicks the next day button in calendar."""
    print("  [Navigation] Clicking next day...")
    await accept_cookies_robust(page)
    next_sel = get_selector('fs_home_page', 'next_day_button')
    if next_sel:
        try:
            btn = page.locator(next_sel).first
            if await btn.is_visible(timeout=5000):
                await btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
                print(f"    [Success] Next day clicked and page updated.")
                return True
        except Exception as e:
            print(f"    [Error] Click next day failed: {e}")
    return False


async def fb_universal_popup_dismissal(page: Page, context: str = "fb_generic", monitor_forever: bool = False):
    """Universal pop-up dismissal for Football.com - NOW USING MODULAR HANDLER."""
    print(f"[DEBUG] fb_universal_popup_dismissal called with context='{context}', monitor_forever={monitor_forever}")

    try:
        # Import the new modular popup handler
        from Core.Intelligence.popup_handler import PopupHandler

        # Create handler instance
        handler = PopupHandler()
        print("[DEBUG] Modular PopupHandler instantiated successfully")

        # Convert monitor_forever to monitor_interval (0 = single run, >0 = continuous)
        monitor_interval = 30 if monitor_forever else 0

        # Call the new modular handler
        result = await handler.fb_universal_popup_dismissal(page, context, None, monitor_interval)
        print(f"[DEBUG] Modular handler returned: success={result.get('success', False)}, method={result.get('method', 'unknown')}")

        # Return boolean for backward compatibility
        return result.get('success', False)

    except Exception as e:
        print(f"[DEBUG] Error in modular handler: {e}")
        import traceback
        traceback.print_exc()
        return False
            


async def get_main_frame(page: Page) -> Optional[Page | Frame]:
    """
    Checks for the presence of the main 'app' iframe and returns the content frame if it exists.
    Otherwise, it returns the original page object.
    """
    try:
        app_sel = get_selector('fb_match_page', 'app_iframe')
        if not app_sel:
            app_sel = '#app'  # Ultimate fallback
        iframe_locator = page.locator(app_sel)
        if await iframe_locator.count() > 0:
            iframe_element = await iframe_locator.element_handle()
            frame = await iframe_element.content_frame()
            if frame:
                await frame.wait_for_load_state('networkidle', timeout=30000)
                print("  [Frame] Switched to main #app iframe.")
                return frame
    except Exception:
        print("  [Frame] No #app iframe found, using main page.")
    return page
