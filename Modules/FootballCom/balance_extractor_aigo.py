# balance_extractor_aigo.py: balance_extractor_aigo.py: AIGO-powered balance extraction
# Part of LeoBook Modules — Football.com
#
# Functions: extract_balance_v5()

from playwright.async_api import Page
from Core.Intelligence.interaction_engine import execute_smart_action


async def extract_balance_v5(page: Page) -> float:
    """
    AIGO V5 balance extraction using Path C fallback.
    Replaces manual 3-retry loop with intelligent extraction.
    """
    print("  [Balance V5] Using AIGO for balance extraction...")
    
    try:
        balance_text = await execute_smart_action(
            page=page,
            context_key="fb_match_page",
            element_key="navbar_balance",
            action_fn=lambda sel: page.locator(sel).first.inner_text(timeout=3000),
            objective="Extract account balance text",
            expected_format="Currency value (e.g., '1,250.50')",
            max_retries=2
        )
        
        # Clean and parse
        import re
        cleaned_text = re.sub(r'[^\d.]', '', balance_text)
        if cleaned_text:
            val = float(cleaned_text)
            print(f"  [Balance V5 SUCCESS] Extracted: {val}")
            return val
        
        print("  [Balance V5] Could not parse balance text.")
        return 0.0
        
    except Exception as e:
        print(f"  [Balance V5 ERROR] Extraction failed: {e}")
        return 0.0
