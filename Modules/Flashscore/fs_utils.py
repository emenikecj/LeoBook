# fs_utils.py: Shared utilities for Flashscore automation.
# Part of LeoBook Modules — Flashscore
#
# Functions: retry_extraction()

import asyncio


MAX_EXTRACTION_RETRIES = 3
EXTRACTION_RETRY_DELAYS = [5, 10, 15]

async def retry_extraction(extraction_func, *args, page=None, context_key=None, element_key=None, **kwargs):
    """
    Retry wrapper for extraction functions with progressive delays.
    After all standard retries fail, triggers AIGO self-healing as a final escape hatch.

    Args:
        extraction_func: The async extraction function to call.
        *args: Positional args passed to extraction_func.
        page: Playwright Page (needed for AIGO healing).
        context_key: SelectorManager context key (e.g. 'fs_standings_tab').
        element_key: Selector element key to heal (e.g. 'standings_row').
        **kwargs: Keyword args passed to extraction_func.
    """
    for attempt in range(MAX_EXTRACTION_RETRIES):
        try:
            return await extraction_func(*args, **kwargs)
        except Exception as e:
            if attempt < MAX_EXTRACTION_RETRIES - 1:
                delay = EXTRACTION_RETRY_DELAYS[attempt]
                print(f"      [Retry] Extraction failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                print(f"      [Retry] Extraction failed after {MAX_EXTRACTION_RETRIES} attempts: {e}")

                # AIGO Healing — final escape hatch (RULEBOOK §2.6)
                if page and context_key and element_key:
                    try:
                        from Core.Intelligence.selector_manager import SelectorManager
                        print(f"      [AIGO HEAL] Triggering AI healing for '{element_key}' in '{context_key}'...")
                        healed = await SelectorManager.heal_selector_on_failure(
                            page, context_key, element_key, failure_reason=str(e)
                        )
                        if healed:
                            print(f"      [AIGO SUCCESS] Healed selector found. Attempting final recovery run...")
                            try:
                                return await extraction_func(*args, **kwargs)
                            except Exception as final_e:
                                print(f"      [AIGO FATAL] Recovery attempt failed after healing: {final_e}")
                                raise final_e
                    except Exception as aigo_err:
                        print(f"      [AIGO ERROR] Healing itself failed: {aigo_err}")

                raise
