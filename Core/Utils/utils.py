# utils.py: utils.py: General-purpose utility functions and system helpers.
# Part of LeoBook Core — Utilities
#
# Classes: Tee, BatchProcessor
# Functions: log_error_state(), capture_debug_snapshot()

"""
Utilities Module
General-purpose utility functions and classes for the LeoBook system.
Responsible for error logging, batch processing, and system utilities.
"""

import asyncio
import sys
import traceback
from datetime import datetime as dt
from pathlib import Path
from typing import Callable, List, TypeVar

from playwright.async_api import Page

T = TypeVar('T')
LOG_DIR = Path("Logs")
ERROR_LOG_DIR = LOG_DIR / "Error" # Corrected to match handbook
AUTH_DIR = Path("Data/Auth")

class Tee(object):
    """A utility to redirect stdout to both console and a log file."""
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

async def log_error_state(page: Page, context_label: str, error: Exception):
    """Captures the state of the page upon an error."""
    ERROR_LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        print(f"  [CRITICAL ERROR] Logging state for '{context_label}'. See 'Logs/Error' folder.")
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{context_label}_{timestamp}"
        
        with open(ERROR_LOG_DIR / f"{base_filename}.txt", "w", encoding="utf-8") as f:
            f.write(f"Error Context: {context_label}\nTimestamp: {dt.now().isoformat()}\n\n")
            traceback.print_exc(file=f)
            f.write(f"\n--- Error Message ---\n{error}")

        if page and not page.is_closed():
            await page.screenshot(path=ERROR_LOG_DIR / f"{base_filename}.png", full_page=True)
            with open(ERROR_LOG_DIR / f"{base_filename}.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
    except Exception as log_e:
        print(f"    [Logger Failure] Could not write error state: {log_e}")


async def capture_debug_snapshot(page: Page, label: str, info_text: str = ""):
    """Captures a debug snapshot (PNG + HTML + TXT) for analysis."""
    DEBUG_DIR = LOG_DIR / "Debug"
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        safe_label = label.replace(" ", "_").replace("/", "-").replace(":", "")[:50]
        base_filename = f"{safe_label}_{timestamp}"
        
        # Write info text
        with open(DEBUG_DIR / f"{base_filename}.txt", "w", encoding="utf-8") as f:
            f.write(f"Context: {label}\nTimestamp: {dt.now().isoformat()}\n\nInfo:\n{info_text}")

        if page and not page.is_closed():
            try:
                # Capture viewport screenshot (faster/safer than full page for dynamic apps)
                await page.screenshot(path=DEBUG_DIR / f"{base_filename}.png")
                # Save HTML
                with open(DEBUG_DIR / f"{base_filename}.html", "w", encoding="utf-8") as f:
                    f.write(await page.content())
                print(f"    [Debug Saved] {base_filename}")
            except Exception as e:
                print(f"    [Debug Capture Fail] Screen/HTML: {e}")
                
    except Exception as e:
        print(f"    [Debug Failure] Could not write debug snapshot: {e}") 

class BatchProcessor:
    def __init__(self, max_concurrent: int = 4):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def _worker(self, func: Callable, item: T, *args, **kwargs): # type: ignore
        async with self.semaphore:
            return await func(item, *args, **kwargs)

    async def run_batch(self, items: List[T], func: Callable, *args, **kwargs):
        tasks = [self._worker(func, item, *args, **kwargs) for item in items]
        return await asyncio.gather(*tasks)
