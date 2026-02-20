# navigator_aigo.py: navigator_aigo.py: Module for Modules — Football.com.
# Part of LeoBook Modules — Football.com
#
# Functions: perform_login_v5()

async def perform_login_v5(page: Page):
    """Refactored login flow using AIGO V5 for self-healing interactions."""
    from Core.Intelligence.interaction_engine import execute_smart_action
    
    await asyncio.sleep(2)
    
    try:
        # AIGO TIER 1.1: Login button discovery and click
        print("  [Login V5] Using AIGO for login button discovery...")
        await execute_smart_action(
            page=page,
            context_key="fb_global",
            element_key="login_button",
            action_fn=lambda sel: page.locator(sel).first.click(force=True),
            objective="Click login button to access credentials form",
            max_retries=2
        )
        await asyncio.sleep(3)
        
        # AIGO TIER 1.1: Mobile number input
        print("  [Login V5] Using AIGO for mobile number input...")
        await execute_smart_action(
            page=page,
            context_key="fb_login_page",
            element_key="login_input_username",
            action_fn=lambda sel: page.fill(sel, PHONE),
            objective=f"Fill mobile number input with {PHONE[:4]}****",
            max_retries=2
        )
        await asyncio.sleep(1)
        
        # AIGO TIER 1.1: Password input
        print("  [Login V5] Using AIGO for password input...")
        await execute_smart_action(
            page=page,
            context_key="fb_login_page",
            element_key="login_input_password",
            action_fn=lambda sel: page.fill(sel, PASSWORD),
            objective="Fill password input",
            max_retries=2
        )
        await asyncio.sleep(1)
        
        # AIGO TIER 1.1: Login submit
        print("  [Login V5] Using AIGO for login submission...")
        await execute_smart_action(
            page=page,
            context_key="fb_login_page",
            element_key="login_button_submit",
            action_fn=lambda sel: page.locator(sel).first.click(force=True),
            objective="Submit login credentials",
            max_retries=2
        )
        
        await page.wait_for_load_state('networkidle', timeout=30000)
        await asyncio.sleep(5)
        print("[Login V5 SUCCESS] Football.com Login Successful with AIGO.")
        
    except Exception as e:
        print(f"[Login V5 Error] {e}")
        # Fallback: Keyboard navigation
        print("  [Login Rescue] Attempting keyboard interaction...")
        try:
            await page.keyboard.press("Tab")
            await page.keyboard.press("Tab")
        except:
            pass
        raise


# Alias for backward compatibility
perform_login = perform_login_v5
