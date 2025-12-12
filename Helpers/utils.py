# Helpers/utils.py

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
AUTH_DIR = Path("auth")

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
        print(f"  [CRITICAL ERROR] Logging state for '{context_label}'. See 'Logs/Errors' folder.")
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

class BatchProcessor:
    def __init__(self, max_concurrent: int = 4):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def _worker(self, func: Callable, item: T, *args, **kwargs): # type: ignore
        async with self.semaphore:
            return await func(item, *args, **kwargs)

    async def run_batch(self, items: List[T], func: Callable, *args, **kwargs):
        tasks = [self._worker(func, item, *args, **kwargs) for item in items]
        return await asyncio.gather(*tasks)