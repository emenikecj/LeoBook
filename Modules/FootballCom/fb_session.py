# fb_session.py: fb_session.py: Browser context and anti-detect management.
# Part of LeoBook Modules — Football.com
#
# Functions: cleanup_chrome_processes(), launch_browser_with_retry()

import asyncio
import os
import subprocess
from pathlib import Path
from playwright.async_api import Playwright, BrowserContext

async def cleanup_chrome_processes():
    """Automatically terminate conflicting Chrome processes before launch."""
    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
            print("  [Cleanup] Cleaned up Chrome processes.")
        else:
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
            print("  [Cleanup] Cleaned up Chrome processes.")
    except Exception as e:
        print(f"  [Cleanup] Warning: Could not cleanup Chrome processes: {e}")

async def launch_browser_with_retry(playwright: Playwright, user_data_dir: Path, max_retries: int = 3) -> BrowserContext:
    """Launch browser with retry logic and exponential backoff."""
    base_timeout = 60000
    backoff_multiplier = 1.2

    # Auto-detect headless: use headed on Windows/macOS with display, headless on Linux without X server
    use_headless = os.name != 'nt' and not os.environ.get('DISPLAY')
    if use_headless:
        print("  [Launch] No DISPLAY detected — using headless mode.")

    for attempt in range(max_retries):
        timeout = int(base_timeout * (backoff_multiplier ** attempt))
        print(f"  [Launch] Attempt {attempt + 1}/{max_retries} with {timeout}ms timeout...")

        try:
            chrome_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-infobars",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-service-autorun",
                "--password-store=basic"
            ]

            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=use_headless,
                args=chrome_args,
                ignore_default_args=["--enable-automation"],
                viewport={'width': 375, 'height': 612},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
                timeout=timeout
            )

            print(f"  [Launch] Browser launched successfully on attempt {attempt + 1}!")
            return context

        except Exception as e:
            print(f"  [Launch] Attempt {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                lock_file = user_data_dir / "SingletonLock"
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                        print(f"  [Launch] Removed SingletonLock before retry.")
                    except Exception as lock_e:
                        print(f"  [Launch] Could not remove lock file: {lock_e}")

                wait_time = 2 ** attempt
                print(f"  [Launch] Waiting {wait_time}s before next attempt...")
                await asyncio.sleep(wait_time)
            else:
                print(f"  [Launch] All {max_retries} attempts failed.")
                raise e
