# fs_utils.py: fs_utils.py: Shared utilities for Flashscore automation.
# Part of LeoBook Modules — Flashscore
#
# Functions: retry_extraction()

import asyncio


MAX_EXTRACTION_RETRIES = 3
EXTRACTION_RETRY_DELAYS = [5, 10, 15]

async def retry_extraction(extraction_func, *args, **kwargs):
    """
    Retry wrapper for extraction functions with progressive delays.
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
                raise
