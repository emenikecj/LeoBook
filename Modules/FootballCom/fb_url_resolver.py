# fb_url_resolver.py: fb_url_resolver.py: Module for Modules — Football.com.
# Part of LeoBook Modules — Football.com
#
# Functions: match_flash_to_fb(), resolve_urls(), get_harvested_matches_for_date()

from playwright.async_api import Page
from fuzzywuzzy import fuzz
import asyncio
from typing import List, Dict

from Data.Access.db_helpers import (
    load_site_matches, save_site_matches, update_site_match_status, 
    get_all_schedules, MATCH_REGISTRY_CSV
)
from Data.Access.sync_manager import run_full_sync
from .navigator import navigate_to_schedule, select_target_date
from .extractor import extract_league_matches
from .match_resolver import GrokMatcher
from Core.System.search_dict import fuzzy_search

# Initialize Matcher (Singleton-ish)
matcher = GrokMatcher()

def match_flash_to_fb(flash_name: str):
    """best canonical name for Football.com lookup using the dictionary."""
    matches = fuzzy_search(flash_name, top_k=3, max_dist=3)
    if matches:
        return matches[0]["name"]  # best canonical name for Football.com lookup
    return None

async def resolve_urls(page: Page, target_date: str) -> dict:
    """
    Resolves URLs for predictions by matching Flashscore fixtures with Football.com matches.
    Uses fuzzy matching and progressive synchronization (every 10 mappings).
    """
    print(f"\n    [URL Resolver] Resolving Football.com mappings for {target_date}...")
    
    # 1. Load Flashscore schedules for the target date
    all_fs_schedules = get_all_schedules()
    day_fs_matches = [m for m in all_fs_schedules if m.get('date') == target_date]
    
    if not day_fs_matches:
        print(f"    [URL Resolver] No Flashscore schedules found for {target_date}. Skipping.")
        return {}

    # 2. Extract or Load Football.com matches
    cached_site_matches = load_site_matches(target_date)
    if not cached_site_matches:
        print(f"    [URL Resolver] Cache empty. Navigating to Football.com schedule...")
        await navigate_to_schedule(page)
        if await select_target_date(page, target_date):
            cached_site_matches = await extract_league_matches(page, target_date)
            if cached_site_matches:
                save_site_matches(cached_site_matches)
    
    if not cached_site_matches:
        print(f"    [URL Resolver] Failed to retrieve Football.com matches for {target_date}.")
        return {}

    # 3. Fuzzy Matching & Progressive Sync
    resolved_count = 0
    mappings = {}
    
    for fs_match in day_fs_matches:
        fs_home = fs_match.get('home_team', '').lower()
        fs_away = fs_match.get('away_team', '').lower()
        fixture_id = fs_match.get('fixture_id')
        
        # Skip if already matched in cache
        already_matched = next((m for m in cached_site_matches if m.get('fixture_id') == fixture_id), None)
        if already_matched:
            mappings[fixture_id] = already_matched.get('url')
            continue

        # Use GrokMatcher (LLM > Fuzzy > None)
        best_match, highest_score = await matcher.resolve(f"{fs_home} vs {fs_away}", cached_site_matches)
        
        if best_match:
            print(f"    [Matched] {fs_home} vs {fs_away}  ==>  {best_match['home_team']} vs {best_match['away_team']} ({highest_score:.1f}%)")
            mappings[fixture_id] = best_match['url']
            
            # Update registry with the fixture_id
            update_site_match_status(
                best_match['site_match_id'], 
                status='pending', 
                fixture_id=fixture_id, 
                matched=f"{fs_match['home_team']} vs {fs_match['away_team']}"
            )
            
            resolved_count += 1
            if resolved_count % 10 == 0:
                print(f"\n    [Progressive Sync] Reached {resolved_count} mappings. Triggering cloud sync...")
                await run_full_sync()
    
    # Final sync if any mappings occurred
    if resolved_count > 0 and resolved_count % 10 != 0:
        await run_full_sync()

    print(f"    [URL Resolver] Completed. Resolved {resolved_count} new mappings.")
    return mappings

async def get_harvested_matches_for_date(target_date: str) -> list:
    """Retrieves matches for the date that have valid booking codes and haven't been booked yet."""
    site_matches = load_site_matches(target_date)
    harvested = [
        m for m in site_matches
        if m.get('booking_code') and m.get('booking_code') != 'N/A'
        and m.get('status') not in ('booked', 'placed')
    ]
    already_booked = sum(1 for m in site_matches if m.get('status') in ('booked', 'placed'))
    if already_booked:
        print(f"  [Registry] ⏭ {already_booked} already booked for {target_date} (skipped)")
    print(f"  [Registry] Found {len(harvested)} unbooked harvested codes for {target_date}.")
    return harvested
