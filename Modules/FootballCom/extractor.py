# extractor.py: Schedule scraper for Football.com.
# Refactored for Clean Architecture (v2.7)
# This script extracts match cards and metadata from league-specific pages.

"""
Extractor Module
Handles extraction of leagues and matches from Football.com schedule pages.
"""

import asyncio
from typing import List, Dict

from playwright.async_api import Page

from Core.Intelligence.selector_manager import SelectorManager
from Core.Intelligence.intelligence import get_selector
from Core.Utils.constants import WAIT_FOR_LOAD_STATE_TIMEOUT
from .navigator import hide_overlays


async def extract_league_matches(page: Page, target_date: str) -> List[Dict]:
    """Iterates through all league headers, expands them, and extracts matches for a specific date."""
    print("  [Harvest] Starting 'Expand & Harvest' sequence...")
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

    try:
        league_headers = await page.locator(league_section_sel).all()
        print(f"  [Harvest] Found {len(league_headers)} league sections.")

        for i, header_locator in enumerate(league_headers):
            try:
                # 1. Extract League Name
                league_element = header_locator.locator(league_title_sel).first
                if await league_element.count() > 0:
                    league_text = (await league_element.inner_text(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)).strip().replace('\n', ' - ')
                elif await header_locator.locator("h4").count() > 0:
                    league_text = (await header_locator.locator("h4").first.inner_text()).strip().replace('\n', ' - ')
                else:
                    league_text = f"Unknown League {i+1}"
                
                print(f"  -> Processing League {i+1}: {league_text}")

                if league_text.startswith("Simulated Reality League"):
                     continue

                # 2. Expansion Logic
                is_collapsed = await header_locator.locator(collapsed_icon_sel).count() > 0
                if is_collapsed:
                    print(f"    -> {league_text}: Expanding...")
                    await header_locator.scroll_into_view_if_needed()
                    await header_locator.click(force=True, timeout=5000)
                    try:
                        await page.wait_for_selector(match_card_sel, state="visible", timeout=5000)
                    except: pass
                    await asyncio.sleep(1.5)
                else:
                    print(f"    -> {league_text}: Already expanded.")

                # 3. Extraction
                matches_container = await header_locator.evaluate_handle('(el) => el.nextElementSibling')
                if matches_container:
                    matches_in_section = await matches_container.evaluate("""(container, args) => {
                        const { selectors, leagueText } = args;
                        const results = [];
                        const cards = container.querySelectorAll(selectors.match_card_sel);
                        cards.forEach(card => {
                            const homeEl = card.querySelector(selectors.home_team_sel);
                            const awayEl = card.querySelector(selectors.away_team_sel);
                            const timeEl = card.querySelector(selectors.time_sel);
                            const linkEl = card.querySelector(selectors.match_url_sel) || card.closest('a');
                            const home = homeEl ? homeEl.innerText.trim() : "";
                            const away = awayEl ? awayEl.innerText.trim() : "";
                            if (home && away) {
                                results.push({ 
                                    home: home, away: away, 
                                    time: timeEl ? timeEl.innerText.trim() : "N/A", 
                                    league: leagueText, 
                                    url: linkEl ? linkEl.href : "", 
                                    date: args.targetDate 
                                });
                            }
                        });
                        return results;
                    }""", {
                        "selectors": {
                            "match_card_sel": match_card_sel, "match_url_sel": match_url_sel,
                            "home_team_sel": home_team_sel, "away_team_sel": away_team_sel,
                            "time_sel": time_sel
                        }, 
                        "leagueText": league_text, "targetDate": target_date
                    })

                    if matches_in_section:
                        all_matches.extend(matches_in_section)
                        print(f"    -> {league_text}: Extracted {len(matches_in_section)} matches.")
                    else:
                        print(f"    -> {league_text}: No matches found. Retrying expansion via Title Click...")
                        # Retry: Click the league title text specifically
                        try:
                            title_el = header_locator.locator(league_title_sel).first
                            if await title_el.is_visible():
                                await title_el.click(timeout=3000, force=True)
                            else:
                                # User requested specific fallback:
                                print(f"    -> {league_text}: Title selector failed, trying text match...")
                                await header_locator.get_by_text(league_text, exact=True).first.click(timeout=3000, force=True)

                            await asyncio.sleep(2) # Wait for expansion
                            
                            # Re-evaluate matches
                            matches_in_section_retry = await matches_container.evaluate("""(container, args) => {
                                const { selectors, leagueText } = args;
                                const results = [];
                                const cards = container.querySelectorAll(selectors.match_card_sel);
                                cards.forEach(card => {
                                    const homeEl = card.querySelector(selectors.home_team_sel);
                                    const awayEl = card.querySelector(selectors.away_team_sel);
                                    const timeEl = card.querySelector(selectors.time_sel);
                                    const linkEl = card.querySelector(selectors.match_url_sel) || card.closest('a');
                                    const home = homeEl ? homeEl.innerText.trim() : "";
                                    const away = awayEl ? awayEl.innerText.trim() : "";
                                    if (home && away) {
                                        results.push({ 
                                            home: home, away: away, 
                                            time: timeEl ? timeEl.innerText.trim() : "N/A", 
                                            league: leagueText, 
                                            url: linkEl ? linkEl.href : "", 
                                            date: args.targetDate 
                                        });
                                    }
                                });
                                return results;
                            }""", {
                                "selectors": {
                                    "match_card_sel": match_card_sel, "match_url_sel": match_url_sel,
                                    "home_team_sel": home_team_sel, "away_team_sel": away_team_sel,
                                    "time_sel": time_sel
                                }, 
                                "leagueText": league_text, "targetDate": target_date
                            })
                            
                            if matches_in_section_retry:
                                all_matches.extend(matches_in_section_retry)
                                print(f"    -> {league_text}: Extracted {len(matches_in_section_retry)} matches (Retry Success).")
                            else:
                                print(f"    -> {league_text}: Still no matches found after retry.")
                        except Exception as retry_e:
                            print(f"    -> {league_text}: Retry failed: {retry_e}")

                # We DON'T close the section to preserve stability

            except Exception as e:
                print(f"    [Harvest Error] Failed league '{league_text}': {e}")
    except Exception as e:
        print(f"  [Harvest] Fatal harvesting error: {e}")

    print(f"  [Harvest] Total: {len(all_matches)}")
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
