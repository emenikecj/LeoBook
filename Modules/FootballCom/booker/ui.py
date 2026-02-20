# ui.py: ui.py: Resilient UI interaction helpers for Football.com.
# Part of LeoBook Modules — Football.com Booking
#
# Functions: handle_page_overlays(), wait_for_condition(), dismiss_overlays(), wait_for_element()

"""
Booker UI Utilities
Handles overlays, tutorials, and resilient click interactions.
"""

import asyncio
from playwright.async_api import Page, Locator
from Core.Utils.utils import log_error_state
from Core.Intelligence.selector_manager import SelectorManager

async def handle_page_overlays(page: Page):
    """Forcefully hide or remove sticky elements that intercept clicks."""
    try:
        await page.keyboard.press("Escape")
    except: pass

    selectors = [
        "footer.CommentFooter", "section#event-detail-header-nav",
        "div.dialog-wrapper", ".m-dialog-mask", ".m-popup-mask",
        "div.srct-widget-indicator_custom", "div.m-main-right",
        "div.m-tutorial-mask", "div.m-tutorial"
    ]
    
    for selector in selectors:
        try:
            await page.evaluate(f"document.querySelectorAll('{selector}').forEach(el => el.style.display = 'none')")
        except: pass


async def wait_for_condition(condition_func, timeout: int = 10000, interval: float = 0.5) -> bool:
    """
    Polls a condition_func (async) until it returns True or timeout expires.
    """
    import time
    start = time.time()
    while time.time() - start < (timeout / 1000.0):
        try:
            if await condition_func():
                return True
        except:
            pass
        await asyncio.sleep(interval)
    return False

async def dismiss_overlays(page: Page):
    """Actively click 'Skip' or 'Close' on common UI overlays."""
    overlays = ["text='Next'", "text='Got it'", "text='Skip'", ".m-tutorial-close", ".m-close-btn"]
    for sel in overlays:
        try:
            if await page.locator(sel).first.is_visible(timeout=500):
                await page.locator(sel).first.click(timeout=1000)
        except: pass

async def wait_for_element(page: Page, selector: str, timeout: int = 10000) -> bool:
    """Helper to wait for visibility with boolean return."""
    try:
        await page.locator(selector).first.wait_for(state="visible", timeout=timeout)
        return True
    except: return False
