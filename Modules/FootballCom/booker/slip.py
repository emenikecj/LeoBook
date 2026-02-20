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

async def force_clear_slip(page: Page, retry_count: int = 3):
    """
    AGGRESSIVELY ensures the bet slip is empty. 
    Crucial for Phase 2 "Harvest" strategy.
    
    Logic:
    1. Check count.
    2. If > 0, open slip -> Remove All -> Confirm -> Close.
    3. Verify count == 0.
    4. If failed, RETRY.
    5. If all retries fail, DELETE STORAGE & RAISE FATAL ERROR.
    """
    import os
    from Data.Access.db_helpers import log_audit_event
    for attempt in range(retry_count):
        count = await get_bet_slip_count(page)
        if count == 0:
            # print(f"    [Slip] Slip clean (Attempt {attempt+1}).")
            return

        print(f"    [Slip] {count} bets detected (Attempt {attempt+1}/{retry_count}). Clearing...")

        try:
            # 1. Open Slip (Try multiple triggers)
            trigger_keys = ["slip_trigger_button", "betslip_trigger_by_attribute", "bet_slip_fab_icon_button"]
            slip_opened = False
            
            for key in trigger_keys:
                sel = SelectorManager.get_selector_strict("fb_match_page", key) or SelectorManager.get_selector_strict("fb_global", key)
                # Check visibility aggressively
                if sel and await page.locator(sel).count() > 0 and await page.locator(sel).first.is_visible():
                        await page.locator(sel).first.click()
                        slip_opened = True
                        await asyncio.sleep(1.5)
                        break
            
            if not slip_opened:
                print("    [Slip] Warning: Could not open bet slip to clear.")
                # Don't return, try finding 'Remove All' anyway in case it's already open
            
            # 2. Click Remove All
            # Try finding it in different contexts if needed
            clear_sel = SelectorManager.get_selector("fb_match_page", "betslip_remove_all")
            if clear_sel and await page.locator(clear_sel).count() > 0 and await page.locator(clear_sel).first.is_visible():
                await page.locator(clear_sel).first.click()
                await asyncio.sleep(1)
                
                # 3. Confirm Removal (if dialog appears)
                confirm_sel = SelectorManager.get_selector("fb_match_page", "confirm_bet_button")
                if confirm_sel and await page.locator(confirm_sel).count() > 0 and await page.locator(confirm_sel).first.is_visible():
                    await page.locator(confirm_sel).first.click()
                    await asyncio.sleep(1)
                
                print("    [Slip] Cliicked remove all.")
            else:
                 print("    [Slip] 'Remove All' button not found (Slip might be closed or empty?)")

            # 4. Close Slip (Important to reset UI state)
            try:
                await page.keyboard.press("Escape")
                
                close_icon = SelectorManager.get_selector("fb_match_page", "betslip_close_button")
                if close_icon and await page.locator(close_icon).count() > 0:
                        if await page.locator(close_icon).first.is_visible():
                            await page.locator(close_icon).first.click()
            except:
                pass
            
            await asyncio.sleep(1)

        except Exception as e:
            print(f"    [Slip Error] Attempt {attempt+1} failed: {e}")
            await asyncio.sleep(2)

    # --- FINAL VERIFICATION ---
    final_count = await get_bet_slip_count(page)
    if final_count > 0:
        print(f"!!! [CRITICAL] Slip Force-Clear Failed. {final_count} bets remain after {retry_count} retries. !!!")
        
        # log_audit_event("FATAL_ERROR", f"Slip stuck dirty with {final_count} items. Escalating.")
        print("!!! [CRITICAL] Deleting storage state and triggering restart. !!!")
        
        # Delete storage state to force fresh login next time
        try:
             import os
             if os.path.exists("storage_state.json"):
                 os.remove("storage_state.json")
                 print("    [System] storage_state.json deleted.")
             
             # Also try to close context if possible
             if page and not page.is_closed():
                 context = page.context
                 if context:
                     await context.close()
        except Exception as e:
            print(f"    [System] Failed to close context/delete storage: {e}")

        raise FatalSessionError("Slip stuck dirty after 3 retries. Session invalidated.")
    else:
        print("    [Slip] Cleaned successfully.")

