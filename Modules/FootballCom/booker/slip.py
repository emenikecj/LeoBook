# slip.py: slip.py: Interaction logic for the Football.com betslip.
# Part of LeoBook Modules — Football.com Booking
#
# Classes: FatalSessionError
# Functions: get_bet_slip_count(), force_clear_slip()

"""
Betslip Management
Handles counting and clearing of the betslip with robust, self-healing logic.
"""

import re
import asyncio
from playwright.async_api import Page

from Core.Intelligence.selector_manager import SelectorManager
from Core.Intelligence.aigo_suite import AIGOSuite

async def get_bet_slip_count(page: Page) -> int:
    """Extract current number of bets in the slip using dynamic selector."""
    # Use fb_match_page as it contains the betslip keys
    count_sel = SelectorManager.get_selector_strict("fb_match_page", "betslip_bet_count")
    
    if count_sel:
        try:
            if await page.locator(count_sel).count() > 0:
                text = await page.locator(count_sel).first.inner_text(timeout=2000)
                count = int(re.sub(r'\D', '', text) or 0)
                if count > 0:
                    return count
        except Exception as e:
            # print(f"    [Slip] Count selector failed: {count_sel} - {e}")
            pass

    return 0


class FatalSessionError(Exception):
    """Raised when the session is irretrievably broken (e.g. cannot clear slip)."""
    pass

@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_match_page", element_key="slip_trigger_button")
async def force_clear_slip(page: Page):
    """
    AGGRESSIVELY ensures the bet slip is empty using AIGO safety net.
    """
    count = await get_bet_slip_count(page)
    if count == 0:
        return

    print(f"    [Slip] {count} bets detected. Clearing...")

    # 1. Open Slip
    trigger_keys = ["slip_trigger_button", "betslip_trigger_by_attribute", "bet_slip_fab_icon_button"]
    slip_opened = False
    for key in trigger_keys:
        sel = SelectorManager.get_selector_strict("fb_match_page", key) or SelectorManager.get_selector_strict("fb_global", key)
        if sel and await page.locator(sel).count() > 0:
            await page.locator(sel).first.click()
            slip_opened = True
            await asyncio.sleep(1.5)
            break
    
    # 2. Click Remove All
    clear_sel = SelectorManager.get_selector("fb_match_page", "betslip_remove_all")
    if clear_sel and await page.locator(clear_sel).count() > 0:
        await page.locator(clear_sel).first.click()
        await asyncio.sleep(1)
        
        # 3. Confirm Removal
        confirm_sel = SelectorManager.get_selector("fb_match_page", "confirm_bet_button")
        if confirm_sel and await page.locator(confirm_sel).count() > 0:
            await page.locator(confirm_sel).first.click()
            await asyncio.sleep(1)
        
    # Validation
    new_count = await get_bet_slip_count(page)
    if new_count > 0:
        raise ValueError(f"Failed to clear slip. {new_count} bets remaining.")
    
    # Close Slip
    await page.keyboard.press("Escape")
    print("    [Slip] Slip cleared successfully.")

