# slip_aigo.py: slip_aigo.py: AIGO-powered betslip management
# Part of LeoBook Modules — Football.com Booking
#
# Functions: force_clear_slip_v5(), force_clear_slip(), get_bet_slip_count_v5()

import asyncio
from playwright.async_api import Page
from Core.Intelligence.interaction_engine import execute_smart_action


async def force_clear_slip_v5(page: Page, retry_count: int = 2) -> bool:
    """
    AIGO V5 implementation of betslip clearing.
    Replaces manual 3-retry loop with intelligent self-healing actions.
    
    Returns: True if successfully cleared, raises exception otherwise.
    """
    print("    [Slip V5] Starting AIGO-powered clearing...")
    
    try:
        # Step 1: Open betslip using AIGO
        await execute_smart_action(
            page=page,
            context_key="fb_match_page",
            element_key="slip_trigger_button",
            action_fn=lambda sel: page.locator(sel).first.click(),
            objective="Open betslip modal for clearing",
            max_retries=2
        )
        await asyncio.sleep(1.5)
        
        # Step 2: Click "Remove All" using AIGO
        await execute_smart_action(
            page=page,
            context_key="fb_match_page",
            element_key="betslip_remove_all",
            action_fn=lambda sel: page.locator(sel).first.click(),
            objective="Click Remove All button in betslip",
            max_retries=2
        )
        await asyncio.sleep(1)
        
        # Step 3: Confirm removal if dialog appears (Optional Path B)
        try:
            await execute_smart_action(
                page=page,
                context_key="fb_match_page",
                element_key="confirm_bet_button",
                action_fn=lambda sel: page.locator(sel).first.click(),
                objective="Confirm removal in dialog",
                max_retries=1
            )
        except Exception:
            # Confirmation may not always appear
            pass
        
        # Step 4: Close betslip
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except:
            pass
        
        print("    [Slip V5 SUCCESS] Betslip cleared via AIGO.")
        return True
        
    except Exception as e:
        print(f"    [Slip V5 ERROR] AIGO clearing failed: {e}")
        raise


# Backward compatibility wrapper
async def force_clear_slip(page: Page, retry_count: int = 3):
    """Legacy wrapper for AIGO V5 implementation."""
    try:
        return await force_clear_slip_v5(page, retry_count=2)
    except Exception as e:
        # Fatal escalation (same as original)
        print(f"!!! [CRITICAL] Slip Force-Clear Failed. Escalating. !!!")
        from Modules.FootballCom.booker.slip import FatalSessionError
        raise FatalSessionError(f"AIGO V5 slip clear failed: {e}")


async def get_bet_slip_count_v5(page: Page) -> int:
    """AIGO-powered bet slip count extraction using Path C."""
    try:
        count = await execute_smart_action(
            page=page,
            context_key="fb_match_page",
            element_key="betslip_bet_count",
            action_fn=lambda sel: page.locator(sel).first.inner_text(timeout=2000),
            objective="Extract bet slip count",
            expected_format="Text containing number",
            max_retries=1
        )
        
        # Extract numeric value
        import re
        numeric = int(re.sub(r'\D', '', count) or 0)
        return numeric
    except Exception:
        return 0
