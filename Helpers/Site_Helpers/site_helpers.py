# Helpers/site_helpers.py

import asyncio # Keep asyncio for async operations
from typing import Optional # Keep Optional for type hinting
from playwright.async_api import Page, TimeoutError, Frame # Import Frame
from Neo.intelligence import get_selector

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
        onetrust_btn = page.locator("#onetrust-accept-btn-handler")
        if await onetrust_btn.is_visible(timeout=2000):
            await onetrust_btn.click()
            print("    [Cookies] Accepted via OneTrust")
            await asyncio.sleep(0.5)
            return
    except Exception:
        pass

    try:
        cookie_sel = get_selector('home_page', 'cookie_accept_button')
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
    next_sel = get_selector('home_page', 'next_day_button')
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
    """Universal pop-up dismissal for Football.com."""
    
    async def _single_dismiss_attempt():
        # This is a simplified version of your complex popup handler.
        # It prioritizes the most common buttons.
        guide_texts = ["GOT IT!", "Ok", "Done", "Got it", "Skip", "I Accept", "I Agree", "I understand"]
        for text in guide_texts:
            try:
                btn_locator = page.get_by_role("button", name=text, exact=False).first
                if await btn_locator.is_visible(timeout=1000):
                    await btn_locator.click(timeout=2000)
                    print(f"    [Popup Handler] Clicked guide button: '{text}'")
                    return True # Handled one popup
            except Exception:
                continue
        
        # Fallback for 'X' close icons
        fallback_selectors = [ 'svg.close-circle-icon', 'button[class*="close"]', '[data-testid*="close"]' ]
        for sel in fallback_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click(timeout=2000)
                    print(f"    [Popup Handler] Closed popup via fallback selector: {sel}")
                    return True
            except Exception:
                continue
        return False

    if monitor_forever:
        print(f"    [Popup Handler] Continuous monitoring enabled...")
        async def monitor_loop():
            while not page.is_closed():
                await _single_dismiss_attempt()
                await asyncio.sleep(30) # Check every 30s
        asyncio.create_task(monitor_loop())
    else:
        for i in range(3): # Try up to 3 times for multi-step popups
            if not await _single_dismiss_attempt():
                print(f"    [Popup Handler] No dismissible popups found on attempt {i+1}.")
                break
            await asyncio.sleep(1)
            


async def get_main_frame(page: Page) -> Optional[Page | Frame]:
    """
    Checks for the presence of the main 'app' iframe and returns the content frame if it exists.
    Otherwise, it returns the original page object.
    """
    try:
        iframe_locator = page.locator("#app")
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