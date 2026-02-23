# aigo_suite.py: Universal AIGO Retry & Healing Logic.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Decorators: aigo_retry

import asyncio
import functools
import time
from typing import Callable, Any, Optional, Dict
from playwright.async_api import Page, TimeoutError

class AIGOSuite:
    """
    Central suite for AIGO (AI-Driven Self-Healing) operations.
    """

    @staticmethod
    def aigo_retry(
        max_retries: int = 2,
        delay: float = 2.0,
        context_key: Optional[str] = None,
        element_key: Optional[str] = None,
        use_aigo: bool = True
    ):
        """
        Universal decorator for retrying operations with AIGO healing as the final escape hatch.
        
        Args:
            max_retries: Standard attempts before triggering AIGO.
            delay: Wait time between standard retries.
            context_key: Context for AIGO healing (e.g., 'fb_match_page').
            element_key: Specific selector key to heal if the operation fails.
            use_aigo: Whether to trigger AIGO healing on the final failure.
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Attempt to extract 'page' from arguments
                page = kwargs.get('page')
                if not page:
                    for arg in args:
                        if isinstance(arg, Page):
                            page = arg
                            break

                last_exception = None
                
                # 1. Standard Retry Loop
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries:
                            print(f"    [AIGO Retry] Attempt {attempt+1}/{max_retries+1} failed: {e}. Retrying in {delay}s...")
                            await asyncio.sleep(delay)
                        else:
                            # 2. Final Escape Hatch: AIGO Healing
                            if use_aigo and page and context_key and element_key:
                                print(f"    [AIGO HEAL] Final attempt failed. Triggering AI healing for '{element_key}' in '{context_key}'...")
                                from .selector_manager import SelectorManager
                                healed_selector = await SelectorManager.heal_selector_on_failure(
                                    page, context_key, element_key, failure_reason=str(e)
                                )
                                
                                if healed_selector:
                                    print(f"    [AIGO SUCCESS] Healed selector found. Attempting final recovery run...")
                                    try:
                                        # One last attempt with the healed state
                                        return await func(*args, **kwargs)
                                    except Exception as final_e:
                                        print(f"    [AIGO FATAL] Recovery attempt failed even after healing: {final_e}")
                                        raise final_e
                            
                            print(f"    [AIGO FATAL] Operation failed after {max_retries + 1} attempts.")
                            raise last_exception
                
                return None
            return wrapper
        return decorator
