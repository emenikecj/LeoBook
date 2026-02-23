# extractor.py: extractor.py: Schedule scraper for Football.com.
# Part of LeoBook Modules — Football.com
#
# Functions: extract_league_matches(), validate_match_data()

"""
Extractor Module
Handles extraction of leagues and matches from Football.com schedule pages.
"""

import asyncio
from typing import List, Dict

from playwright.async_api import Page

from Core.Intelligence.selector_manager import SelectorManager

from Core.Utils.constants import WAIT_FOR_LOAD_STATE_TIMEOUT
from .navigator import hide_overlays
from Core.Intelligence.aigo_suite import AIGOSuite


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_schedule_page", element_key="league_section")
async def extract_league_matches(page: Page, target_date: str) -> List[Dict]:
    """Iterates leagues and extracts matches with AIGO protection."""
    print("  [Harvest] Starting protected extraction sequence...")
    await hide_overlays(page)
    all_matches = []
    
    # Selectors
    league_section_sel = SelectorManager.get_selector_strict("fb_schedule_page", "league_section")
    match_card_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_rows")
    match_url_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_url")
    league_title_sel = SelectorManager.get_selector_strict("fb_schedule_page", "league_title_link")
    home_team_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_row_home_team_name")
    away_team_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_row_away_team_name")
    time_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_row_time")
    collapsed_icon_sel = SelectorManager.get_selector_strict("fb_schedule_page", "league_expand_icon_collapsed")

    league_headers = await page.locator(league_section_sel).all()
    if not league_headers:
        raise ValueError("No league sections found on page.")

    for i, header_locator in enumerate(league_headers):
        # 1. Extract League Name
        league_element = header_locator.locator(league_title_sel).first
        if await league_element.count() > 0:
            league_text = (await league_element.inner_text()).strip().replace('\n', ' - ')
        else:
            league_text = f"Unknown League {i+1}"
        
        if league_text.startswith("Simulated Reality"): continue

        # 2. Expansion
        if await header_locator.locator(collapsed_icon_sel).count() > 0:
            print(f"    -> {league_text}: Expanding...")
            await header_locator.click(force=True)
            await asyncio.sleep(1.5)

        # 3. Extraction
        matches_container = await header_locator.evaluate_handle('(el) => el.nextElementSibling')
        if matches_container:
            matches_in_section = await matches_container.evaluate("""(container, args) => {
                const { selectors, leagueText, targetDate } = args;
                const results = [];
                const cards = container.querySelectorAll(selectors.match_card_sel);
                cards.forEach(card => {
                    const homeEl = card.querySelector(selectors.home_team_sel);
                    const awayEl = card.querySelector(selectors.away_team_sel);
                    const timeEl = card.querySelector(selectors.time_sel);
                    const linkEl = card.querySelector(selectors.match_url_sel) || card.closest('a');
                    if (homeEl && awayEl) {
                        results.push({ 
                            home: homeEl.innerText.trim(), 
                            away: awayEl.innerText.trim(), 
                            time: timeEl ? timeEl.innerText.trim() : "N/A", 
                            league: leagueText, 
                            url: linkEl ? linkEl.href : "", 
                            date: targetDate 
                        });
                    }
                });
                return results;
            }""", {
                "selectors": {
                    "match_card_sel": match_card_sel, "match_url_sel": match_url_sel,
                    "home_team_sel": home_team_sel, "away_team_sel": away_team_sel, "time_sel": time_sel
                },
                "leagueText": league_text,
                "targetDate": target_date
            })
            if matches_in_section:
                all_matches.extend(matches_in_section)

    print(f"  [Harvest] Total: {len(all_matches)}")
    return all_matches
    return all_matches


async def validate_match_data(matches: List[Dict]) -> List[Dict]:
    """Validate and clean extracted match data."""
    valid_matches = []
    for match in matches:
        if all(k in match for k in ['home', 'away', 'url', 'league']):
            # Basic validation
            if match['home'] and match['away'] and match['url']:
                valid_matches.append(match)
        else:
            print(f"    [Validation] Skipping invalid match: {match}")
    print(f"  [Validation] {len(valid_matches)}/{len(matches)} matches valid.")
    return valid_matches
