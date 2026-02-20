# fb_harvester.py: fb_harvester.py: Batch processing of match booking codes.
# Part of LeoBook Modules — Football.com
#
# Functions: run_harvest_loop()

from datetime import datetime as dt
from playwright.async_api import Page
from Data.Access.db_helpers import (
    get_site_match_id, load_site_matches, log_audit_event
)
from Core.System.lifecycle import log_state
from .booker.booking_code import harvest_single_match_code

async def run_harvest_loop(page: Page, matched_urls: dict, day_preds: list, target_date: str, current_balance: float) -> int:
    """
    Executes Phase 2a: Harvest for all matched URLs.
    Returns count of successfully harvested codes.
    """
    print(f"  [Phase 2a] Entering Harvest for {len(matched_urls)} matches...")
    harvested_count = 0
    
    for match_id, match_url in matched_urls.items():
        pred = next((p for p in day_preds if str(p['fixture_id']) == str(match_id)), None)
        if not pred: 
            continue

        fixture_id = pred['fixture_id']
        match_dict = {
            'url': match_url, 
            'site_match_id': get_site_match_id(target_date, pred['home_team'], pred['away_team']),
            'home_team': pred['home_team'], 
            'away_team': pred['away_team']
        }

        # Skip if already harvested
        matches_now = load_site_matches(target_date)
        existing_m = next((m for m in matches_now if m['site_match_id'] == match_dict['site_match_id']), None)
        if existing_m and existing_m.get('booking_status') == 'harvested':
            continue

        print(f"   [Harvest] Starting for: {pred['home_team']} vs {pred['away_team']} (ID: {fixture_id})")

        try:
            success = await harvest_single_match_code(page, match_dict, pred)
            if success:
                harvested_count += 1
                log_state("Harvest", "Success", f"Fixture {fixture_id}")
            else:
                log_state("Harvest", "Skipped", f"Fixture {fixture_id}")
        except Exception as harvest_error:
            print(f"    [Harvest Error] {fixture_id}: {str(harvest_error)}")
            debug_path = f"Logs/Debug/harvest_error_{fixture_id}_{dt.now().strftime('%H%M%S')}.png"
            await page.screenshot(path=debug_path)
            print(f"    [Debug] Screenshot saved: {debug_path}")
            log_audit_event("HARVEST_ERROR", f"Fixture {fixture_id}: {str(harvest_error)}", current_balance, current_balance, 0, "FAILED")
            log_state("Harvest", "Error Continued", f"Fixture {fixture_id}")

    print(f"  [Harvest Complete] {harvested_count} codes harvested successfully.")
    return harvested_count
