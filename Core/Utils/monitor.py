# monitor.py: monitor.py: Page monitoring and change detection.
# Part of LeoBook Core — Utilities
#
# Classes: PageMonitor

import asyncio
import hashlib
from datetime import datetime as dt
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

# Import existing helpers for consistency
from Data.Access.db_helpers import upsert_entry, _write_csv

# --- CONFIGURATION ---
DB_DIR = Path("Data/Store")
PAGES_CSV = DB_DIR / "pages_registry.csv"

HEADERS = [
    'page_id',         # Hash of URL + Title (Unique Identifier)
    'url',             # Full URL
    'page_title',      # Extracted Page Title
    'domain',          # extracted domain
    'first_seen',      # ISO Timestamp
    'last_seen',       # ISO Timestamp
    'visit_count',     # Valid integers
    'status'           # "active", "error", etc.
]

class PageMonitor:
    """
    Vigilant monitoring system to detect, extract, and document page names and changes.
    """
    
    @staticmethod
    def _generate_id(url: str, title: str) -> str:
        """Generates a stable ID based on URL and Title to track unique states."""
        raw = f"{url.strip()}|{title.strip()}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    @staticmethod
    def _ensure_csv_exists():
        if not PAGES_CSV.exists():
            print(f"    [Monitor] Initializing Page Registry at {PAGES_CSV}")
            _write_csv(str(PAGES_CSV), [], HEADERS)

    @classmethod
    async def capture(cls, page: Page, context_label: str = ""):
        """
        Captures the current state of the page (URL & Title) and UPSERTs it into the DB.
        Should be called on navigation events, loads, or explicitly.
        """
        if not page or page.is_closed():
            return

        try:
            # 1. Extract Info
            url = page.url
            if url == "about:blank": return

            try:
                title = await page.title()
            except Exception:
                title = "Unknown/Unresponsive"

            # Clean title
            title = title.strip()
            
            # Domain extraction
            import urllib.parse
            try:
                domain = urllib.parse.urlparse(url).netloc
            except:
                domain = "unknown"

            # 2. Generate ID
            page_id = cls._generate_id(url, title)
            now = dt.now().isoformat()

            # 3. Prepare Data
            entry = {
                'page_id': page_id,
                'url': url,
                'page_title': title,
                'domain': domain,
                'first_seen': now, # This will only be used if new
                'last_seen': now,
                'visit_count': 1,
                'status': 'active'
            }

            # 4. UPSERT logic (Custom to handle incrementing visit_count)
            # We can't use generic upsert_entry easily if we want to increment visit_count 
            # without reading first. But upsert_entry overwrites.
            # Strategy: We will just read, update/append, write.
            # Given the scale (hundreds of pages), simple read/write is fine.
            
            cls._ensure_csv_exists()
            
            # This logic needs to be fast.
            # We will use the generic upsert but we need to preserve FirstSeen and Increment count.
            # Actually, standard upsert replaces. 
            # Let's implement a specific robust upsert for this monitor here.
            
            import csv
            rows = []
            found = False
            
            existing_data = [] # To hold all rows
            
            # Read all
            if PAGES_CSV.stat().st_size > 0:
                with open(PAGES_CSV, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    existing_data = list(reader)

            # Update in memory
            for row in existing_data:
                if row['page_id'] == page_id:
                    row['last_seen'] = now
                    try:
                        count = int(row['visit_count'])
                    except:
                        count = 0
                    row['visit_count'] = str(count + 1)
                    # Keep first_seen
                    # Title/URL are same by definition of ID
                    found = True
                    # Print only if meaningful change or forced? 
                    # User said "immediately be able to detect page name changes". 
                    # If ID matches, it's the SAME page state.
                    break
            
            if not found:
                # New State Detected! (Either new URL or new Title for existing URL)
                # Check if URL exists with OTHER title to log change
                previous_titles = [r['page_title'] for r in existing_data if r['url'] == url]
                if previous_titles:
                    print(f"    [Monitor] ⚠ PAGE NAME CHANGED for {url}!")
                    print(f"      Old: {previous_titles[-1]}")
                    print(f"      New: {title}")
                else:
                    if context_label:
                        print(f"    [Monitor] New Page Detected: '{title}'")
                
                existing_data.append(entry)

            # Write back
            with open(PAGES_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerows(existing_data)

        except Exception as e:
            print(f"    [Monitor Error] Failed to capture page state: {e}")

    @classmethod
    def attach_listeners(cls, page: Page):
        """
        Attaches event listeners to the page to automatically capture state changes.
        """
        # Capture on 'load' (strict) and 'domcontentloaded' (faster)
        page.on("domcontentloaded", lambda p: asyncio.create_task(cls.capture(p, "Auto-Listener")))
        # page.on("framenavigated", lambda p: asyncio.create_task(cls.capture(p, "Nav"))) # Can be noisy
        # print("    [Monitor] Vigilance active on page.")

