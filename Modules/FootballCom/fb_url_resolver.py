# fb_url_resolver.py: Match discovery and URL mapping for Football.com.
# Refactored for Clean Architecture (v2.7)
# This script executes search/navigation to find specific match pages.

from playwright.async_api import Page
from Data.Access.db_helpers import (
    load_site_matches, save_site_matches, update_site_match_status
)
from .navigator import navigate_to_schedule, select_target_date
from .extractor import extract_league_matches
from .matcher import match_predictions_with_site

async def resolve_urls(page: Page, target_date: str, day_preds: list) -> dict:
    """
    Resolves URLs for predictions by checking cache, then scraping ONLY if cache is empty for the date.
    Returns: mapped_urls {fixture_id: url}
    """
    cached_site_matches = load_site_matches(target_date)
    matched_urls = {}
    
    # 1. Direct ID check (Already matched in previous runs)
    unmatched_predictions = []
    for pred in day_preds:
        fid = str(pred.get('fixture_id'))
        cached_match = next((m for m in cached_site_matches if m.get('fixture_id') == fid), None)
        if cached_match and cached_match.get('url'):
            if cached_match.get('booking_status') != 'booked':
                matched_urls[fid] = cached_match.get('url')
        else:
            unmatched_predictions.append(pred)

    if not unmatched_predictions:
        return matched_urls

    # 2. If we have unmatched predictions but the cache is NOT empty, try AI matching first
    if cached_site_matches:
        print(f"  [Registry] Found {len(cached_site_matches)} cached matches for {target_date}. Attempting AI match...")
        new_mappings = await match_predictions_with_site(unmatched_predictions, cached_site_matches)
        
        still_unmatched = []
        for pred in unmatched_predictions:
            fid = str(pred.get('fixture_id'))
            if fid in new_mappings:
                url = new_mappings[fid]
                matched_urls[fid] = url
                site_match = next((m for m in cached_site_matches if m.get('url') == url), None)
                if site_match:
                    fs_fixture_name = f"{pred.get('home_team')} vs {pred.get('away_team')}"
                    update_site_match_status(site_match['site_match_id'], 'pending', fixture_id=fid, matched=fs_fixture_name)
            else:
                still_unmatched.append(pred)
        unmatched_predictions = still_unmatched

    # 3. Only Crawl if we still have unmatched AND the cache was completely empty for this date
    if unmatched_predictions and not cached_site_matches:
        print(f"  [Registry] Cache empty for {target_date}. Starting full crawl...")
        await navigate_to_schedule(page)
        if await select_target_date(page, target_date):
            site_matches = await extract_league_matches(page, target_date)
            if site_matches:
                save_site_matches(site_matches)
                # Refresh cache from disk
                new_cached_matches = load_site_matches(target_date)
                new_mappings = await match_predictions_with_site(unmatched_predictions, new_cached_matches)
                for fid, url in new_mappings.items():
                    matched_urls[fid] = url
                    site_match = next((m for m in new_cached_matches if m.get('url') == url), None)
                    if site_match:
                        # Find the prediction for this fixture_id to get its FS name
                        pred = next((p for p in unmatched_predictions if str(p.get('fixture_id')) == fid), {})
                        fs_fixture_name = f"{pred.get('home_team')} vs {pred.get('away_team')}"
                        update_site_match_status(site_match['site_match_id'], 'pending', fixture_id=fid, matched=fs_fixture_name)

    return matched_urls

async def get_harvested_matches_for_date(target_date: str) -> list:
    """
    Retrieves matches for the date that have valid booking codes (harvested in Phase 2a).
    Used for Phase 2b multi-bet placement.
    """
    site_matches = load_site_matches(target_date)
    harvested = [m for m in site_matches if m.get('booking_code') and m.get('booking_code') != 'N/A']
    print(f"  [Registry] Found {len(harvested)} harvested codes for {target_date}.")
    return harvested
