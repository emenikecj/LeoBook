# page_logger.py: page_logger.py: Diagnostic tool for capturing HTML and screenshot snapshots.
# Part of LeoBook Core — Browser Automation
#
# Functions: log_fb_login_page(), log_page_html()

import asyncio
from datetime import datetime as dt
from pathlib import Path

from playwright.async_api import Page

LOG_DIR = Path("Logs")
PAGE_LOG_DIR = LOG_DIR / "Page"

async def log_fb_login_page(page: Page):
    """ Captures the state of the Facebook login page for debugging. """
    await log_page_html(page, "fb_login_page")

async def log_page_html(page: Page, context_label: str):
    """Saves screenshot and HTML content of the page."""
    PAGE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    png_file = PAGE_LOG_DIR / f"{context_label}.png"
    html_file = PAGE_LOG_DIR / f"{context_label}.html"

    try:
        # Take screenshot without full_page to avoid hanging on large pages
        await page.screenshot(path=png_file, timeout=5000)  # 5 second timeout
        print(f"    [Logger] Screenshot saved: {png_file.name}")
    except Exception as e:
        print(f"    [Logger] Screenshot failed: {e}")

    try:
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(await page.content())
        print(f"    [Logger] HTML saved: {html_file.name}")
    except Exception as e:
        print(f"    [Logger] HTML save failed: {e}")
