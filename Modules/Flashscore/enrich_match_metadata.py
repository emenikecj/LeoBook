# enrich_match_metadata.py: Shared match-page metadata extraction utility.
# Part of LeoBook Modules â€” Flashscore
#
# Functions: extract_match_page_metadata(), strip_league_stage()
# Called by: fs_processor.py (Ch1 P1), manager.py (--schedule --all)

"""
JIT Metadata Enrichment
Extracts team crests, URLs, league info, region flags, and league IDs
from a Flashscore match page that is ALREADY loaded in the browser.

League ID extraction requires visiting the league page (JS injects the
season hash into the URL). While on the league page, we also harvest
match URLs from the results/fixtures tabs.
"""

import re
import asyncio
from playwright.async_api import Page
from Core.Intelligence.selector_manager import SelectorManager
from Data.Access.db_helpers import save_region_league_entry, save_team_entry, save_schedule_entry


def strip_league_stage(league_name: str):
    """Strips ' - Round X' etc. and returns (clean_league, stage)."""
    if not league_name:
        return "", ""
    match = re.search(
        r" - (Round \d+|Group [A-Z]|Play Offs|Qualification|Relegation Group|Championship Group|Finals?)$",
        league_name, re.IGNORECASE
    )
    if match:
        stage = match.group(1)
        base_league = league_name[:match.start()].strip()
        return base_league, stage
    return league_name, ""


def _standardize_url(url: str) -> str:
    """Ensure flashscore URLs are absolute."""
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.flashscore.com" + url
    return url


async def extract_match_page_metadata(page: Page, match_data: dict) -> dict:
    """
    Extracts and persists team/league metadata from an already-loaded match page.

    This function:
      1. Extracts team crests, URLs, region flags from the match page header.
      2. Visits the league page to extract the real League ID (season hash).
      3. While on the league page, extracts league metadata (crest, flag)
         and harvests match URLs from the results tab.
      4. Saves to region_league.csv and teams.csv.

    Enriches match_data in-place with:
      - region_league, league_stage, league_id
      - team crests, URLs, region flags

    Returns: dict of extracted metadata (for callers that need it).
    """
    extracted = {}
    match_label = f"{match_data.get('home_team', '?')} vs {match_data.get('away_team', '?')}"

    try:
        # --- Selectors ---
        sel_region_name = await SelectorManager.get_selector_auto(page, "fs_match_page", "region_name")
        sel_region_flag = await SelectorManager.get_selector_auto(page, "fs_match_page", "region_flag_img")
        sel_league_url = await SelectorManager.get_selector_auto(page, "fs_match_page", "league_url")
        sel_region_url = await SelectorManager.get_selector_auto(page, "fs_match_page", "region_url")

        sel_home_crest = await SelectorManager.get_selector_auto(page, "fs_match_page", "home_crest")
        sel_home_url = await SelectorManager.get_selector_auto(page, "fs_match_page", "home_url")
        sel_away_crest = await SelectorManager.get_selector_auto(page, "fs_match_page", "away_crest")
        sel_away_url = await SelectorManager.get_selector_auto(page, "fs_match_page", "away_url")

        # --- Region & League (from match page header) ---
        region_name = await page.locator(sel_region_name).inner_text() if sel_region_name else "Unknown"
        region_flag = await page.locator(sel_region_flag).get_attribute("src") if sel_region_flag else ""
        region_url = await page.locator(sel_region_url).get_attribute("href") if sel_region_url else ""
        league_url_href = await page.locator(sel_league_url).get_attribute("href") if sel_league_url else ""
        league_name = await page.locator(sel_league_url).inner_text() if sel_league_url else "Unknown"

        league_url = _standardize_url(league_url_href)

        # --- League Stage Parsing ---
        clean_league, stage = strip_league_stage(league_name)
        computed_region_league = f"{region_name.upper()} - {clean_league}"

        # --- League ID: Visit league page for real season hash ---
        league_id = ""
        league_crest = ""

        if league_url:
            try:
                # Navigate to the league page â€” JS injects the season hash into the URL
                await page.goto(league_url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(5)  # Allow JS to update URL with season hash

                final_url = page.url
                if '#/' in final_url:
                    try:
                        hash_part = final_url.split('#/')[1].split('/')[0]
                        if hash_part and len(hash_part) > 5:  # typical Flashscore ID length
                            league_id = hash_part
                            print(f"      [league_id] Extracted after visit: {league_id}")
                    except (IndexError, AttributeError):
                        pass

                if not league_id:
                    # Fallback to href-based ID
                    parts = league_url.rstrip('/').split('/')
                    league_id = parts[-1] if parts else ""
                    print(f"      [league_id] Fallback to href: {league_id}")

                # --- Extract league metadata (crest, flag) from league page ---
                try:
                    from Core.Browser.Extractors.league_page_extractor import extract_league_metadata
                    league_meta = await extract_league_metadata(page)
                    if league_meta:
                        league_crest = league_meta.get('league_crest', '')
                        if league_meta.get('region_flag'):
                            region_flag = league_meta['region_flag']
                        extracted.update(league_meta)
                except Exception as meta_e:
                    print(f"      [Warning] League metadata extraction failed: {meta_e}")

                # --- Harvest match URLs from results AND fixtures tabs ---
                try:
                    from Core.Browser.Extractors.league_page_extractor import extract_league_match_urls
                    for mode in ["results", "fixtures"]:
                        harvest_urls = await extract_league_match_urls(page, league_url, mode=mode)
                        if harvest_urls:
                            added = 0
                            for m_url in harvest_urls:
                                full_url = _standardize_url(m_url)
                                fid = m_url.split('/')[2] if '/match/' in m_url else ''
                                if fid:
                                    save_schedule_entry({
                                        'fixture_id': fid,
                                        'date': '',
                                        'match_time': '',
                                        'region_league': computed_region_league,
                                        'match_status': 'finished' if mode == "results" else "scheduled",
                                        'match_link': full_url
                                    })
                                    added += 1
                            if added:
                                print(f"      [League Harvest] {added} {mode} URLs saved for {clean_league}")
                except Exception as harvest_e:
                    print(f"      [Warning] League harvest failed: {harvest_e}")

                # --- Navigate back to match page for caller ---
                match_link = match_data.get('match_link', '')
                if match_link:
                    await page.goto(match_link, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(1.5)

            except Exception as visit_e:
                print(f"      [Warning] League page visit failed: {visit_e}")
                # Fallback: try extracting from URL fragment on match page
                if league_url_href and "#/" in league_url_href:
                    league_id = league_url_href.split("#/")[-1]
                if not league_id:
                    league_id = f"{region_name}_{league_name}".replace(' ', '_').replace('-', '_').upper()
        else:
            league_id = f"{region_name}_{league_name}".replace(' ', '_').replace('-', '_').upper()

        # --- Enrich match_data in place ---
        match_data['region_league'] = computed_region_league
        match_data['league_stage'] = stage
        match_data['league_id'] = league_id

        extracted.update({
            'region_name': region_name,
            'region_flag': region_flag,
            'region_url': region_url,
            'league_name': league_name,
            'league_url': league_url,
            'league_id': league_id,
            'league_crest': league_crest,
            'region_league': computed_region_league,
            'league_stage': stage,
        })

        # --- Save Region/League ---
        save_region_league_entry({
            'league_id': league_id,
            'region': region_name,
            'region_flag': region_flag,
            'region_url': region_url,
            'league': league_name,
            'league_url': league_url,
            'league_crest': league_crest
        })

        # --- Team Crests & URLs ---
        # Re-fetch if we navigated back, or use already-loaded page
        home_crest = await page.locator(sel_home_crest).get_attribute("src") if sel_home_crest else ""
        home_url = await page.locator(sel_home_url).get_attribute("href") if sel_home_url else ""
        away_crest = await page.locator(sel_away_crest).get_attribute("src") if sel_away_url else ""
        away_url = await page.locator(sel_away_url).get_attribute("href") if sel_away_url else ""

        extracted.update({
            'home_crest': home_crest,
            'home_url': home_url,
            'away_crest': away_crest,
            'away_url': away_url,
        })

        # --- Save Teams ---
        save_team_entry({
            'team_id': match_data.get('home_team_id'),
            'team_name': match_data.get('home_team'),
            'league_ids': league_id,
            'team_crest': home_crest,
            'team_url': home_url
        })
        save_team_entry({
            'team_id': match_data.get('away_team_id'),
            'team_name': match_data.get('away_team'),
            'league_ids': league_id,
            'team_crest': away_crest,
            'team_url': away_url
        })

    except Exception as e:
        print(f"      [Warning] Failed to extract metadata for {match_label}: {e}")

    return extracted

