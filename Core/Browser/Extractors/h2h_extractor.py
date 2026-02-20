# h2h_extractor.py: h2h_extractor.py: Extraction logic for Head-to-Head (H2H) match history.
# Part of LeoBook Core — Browser Extractors
#
# Functions: activate_h2h_tab(), extract_h2h_data(), save_extracted_h2h_to_schedules()

"""
H2H Extractor Module
Head-to-head match data extraction from web pages.
Responsible for extracting historical match data, scores, and league information.
"""

import re
from playwright.async_api import Page, TimeoutError, ElementHandle
import re
from typing import Dict, Any, List
from Core.Intelligence.intelligence import get_selector_auto, get_selector
from Data.Access.db_helpers import save_schedule_entry
from Core.Browser.site_helpers import fs_universal_popup_dismissal
import asyncio

async def activate_h2h_tab(page: Page) -> bool:
    """
    Activates the H2H tab on the match page.
    """
    print("      [Extractor] Activiting H2H tab...")
    # Use the CORRECT key 'tab_h2h' from 'fs_match_page' as defined in knowledge.json
    tab_selector = get_selector("fs_match_page", "tab_h2h")
    
    if not tab_selector:
        print("      [Extractor] Error: 'tab_h2h' selector not found in 'fs_match_page' context.")
        return False

    try:
        if await page.locator(tab_selector).is_visible(timeout=5000):
            await page.click(tab_selector)
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(5.0)
            await fs_universal_popup_dismissal(page, "fs_h2h_tab") # Use specific context popup dismissal if needed, or generic
            return True
        else:
             print(f"      [Extractor] H2H tab selector '{tab_selector}' not visible.")
             return False
    except Exception as e:
        print(f"      [Extractor] Failed to activate H2H tab: {e}")
        return False


async def extract_h2h_data(page: Page, home_team_main: str, away_team_main: str, context: str = "fs_h2h_tab") -> Dict[str, Any]:
    """
    Extracts H2H data from the page using AI-generated selectors from knowledge base.
    Eliminates hardcoded CSS classes for robust scraping.
    """
    print("      [Extractor] Extracting H2H tab...")

    # Get ALL selectors from knowledge base matching exact keys from fs_h2h_tab.txt
    selectors = {
        "h2h_section_home_last_5": get_selector(context, "h2h_section_home_last_5") or ".h2h__section:nth-of-type(1)",
        "h2h_section_away_last_5": get_selector(context, "h2h_section_away_last_5") or ".h2h__section:nth-of-type(2)",
        "h2h_section_mutual": get_selector(context, "h2h_section_mutual") or ".h2h__section:nth-of-type(3)",
        "h2h_section_title": get_selector(context, "h2h_section_title") or ".h2h__sectionHeader",
        "h2h_row_general": get_selector(context, "h2h_row_general") or ".h2h__row",
        "h2h_row_link": get_selector(context, "h2h_row_link"),
        "h2h_row_date": get_selector(context, "h2h_row_date") or ".h2h__date",
        "h2h_row_league_icon": get_selector(context, "h2h_row_league_icon") or ".h2h__eventIcon",
        "h2h_row_participant_home": get_selector(context, "h2h_row_participant_home") or ".h2h__homeParticipant",
        "h2h_row_participant_away": get_selector(context, "h2h_row_participant_away") or ".h2h__awayParticipant",
        "h2h_row_score_home": get_selector(context, "h2h_row_score_home") or ".h2h__result span:nth-child(1)",
        "h2h_row_score_away": get_selector(context, "h2h_row_score_away") or ".h2h__result span:nth-child(2)",
        "h2h_row_win_marker": get_selector(context, "h2h_row_win_marker") or ".fontBold",
        "h2h_badge_win": get_selector(context, "h2h_badge_win") or ".h2h__icon--win",
        "h2h_badge_draw": get_selector(context, "h2h_badge_draw") or ".h2h__icon--draw",
        "h2h_badge_loss": get_selector(context, "h2h_badge_loss") or ".h2h__icon--lost",
        "meta_breadcrumb_country": get_selector(context, "meta_breadcrumb_country") or ".tournamentHeader__country",
        "meta_breadcrumb_league": get_selector(context, "meta_breadcrumb_league") or ".tournamentHeader__league a",
    }

    from Core.Utils.constants import WAIT_FOR_LOAD_STATE_TIMEOUT
    await page.wait_for_selector(selectors['h2h_row_general'], timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)

    js_code = r"""(data) => {
        const { selectors, home_team_main, away_team_main } = data;
        const getText = (el, sel) => el ? el.querySelector(sel)?.innerText.trim() || '' : '';
        const getAttribute = (el, sel, attr) => el?.querySelector(sel)?.[attr] || null;

        const results = {
            home_last_10_matches: [],
            away_last_10_matches: [],
            head_to_head: [],
            parsing_errors: []
        };
        let region_league = 'Unknown';

        // Process each specific section defined in fs_h2h_tab.txt
        const sections_map = [
            { selector: 'h2h_section_home_last_5', target: 'home_last_10_matches' },
            { selector: 'h2h_section_away_last_5', target: 'away_last_10_matches' },
            { selector: 'h2h_section_mutual', target: 'head_to_head' }
        ];

        sections_map.forEach(sectionMap => {
            const sectionSelector = selectors[sectionMap.selector];
            if (!sectionSelector) return; // Skip if selector not available

            const section = document.querySelector(sectionSelector);
            if (!section) return; // Skip if section not found

            const rows = section.querySelectorAll(selectors.h2h_row_general);
            rows.forEach(row => {

                let linkEl = selectors.h2h_row_link ? row.querySelector(selectors.h2h_row_link) : null;
                try {

                    // Check if row itself is clickable
                    if (!linkEl && row.tagName === 'A') {
                        linkEl = row;
                    }

                    // Check for parent link elements
                    if (!linkEl) {
                        let parent = row.parentElement;
                        while (parent && !linkEl && parent !== document.body) {
                            if (parent.tagName === 'A') {
                                linkEl = parent;
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    }

                    // Check for data attributes that might indicate clickability
                    if (!linkEl) {
                        const dataHref = row.getAttribute('data-href') || row.getAttribute('data-url') || row.getAttribute('data-link');
                        if (dataHref) {
                            // Create a pseudo link element for consistency
                            linkEl = { getAttribute: () => dataHref };
                        }
                    }

                    // If still no link found, check if row has click handlers or is within a clickable container
                    if (!linkEl && (row.getAttribute('onclick') || row.getAttribute('data-match-id'))) {
                        // Try to construct URL from available data
                        const matchId = row.getAttribute('data-match-id') || row.getAttribute('data-id');
                        if (matchId) {
                            linkEl = { getAttribute: () => `/match/${matchId}` };
                        }
                    }

                    const scoreHomeStr = getText(row, selectors.h2h_row_score_home);
                    const scoreAwayStr = getText(row, selectors.h2h_row_score_away);
                    const scoreHome = parseInt(scoreHomeStr, 10);
                    const scoreAway = parseInt(scoreAwayStr, 10);

                    if (isNaN(scoreHome) || isNaN(scoreAway)) { return; }

                    let winner = 'Draw';
                    if (scoreHome > scoreAway) winner = 'Home';
                    else if (scoreAway > scoreHome) winner = 'Away';

                    // Check for win/loss badges with specific selectors
                    let perspectiveResult = 'N/A';
                    if (row.querySelector(selectors.h2h_badge_win)) perspectiveResult = 'W';
                    else if (row.querySelector(selectors.h2h_badge_draw)) perspectiveResult = 'D';
                    else if (row.querySelector(selectors.h2h_badge_loss)) perspectiveResult = 'L';

                    const matchLink = linkEl ? linkEl.getAttribute('href') : null;

                    let homeTeamId = null;
                    let awayTeamId = null;
                    let homeTeamUrl = null;
                    let awayTeamUrl = null;
                    let cleanId = null;

                    if (matchLink) {
                        // 1. Clean the link to handle both relative and absolute URLs
                        // This regex removes everything up to and including "/match/football/"
                        const cleanPath = matchLink.replace(/^(.*\/match\/football\/)/, '');

                        // 2. Now split only the remaining parts (Teams and IDs)
                        // cleanPath is now "gardnersville-ENOwpmY9/heaven-eleven-rZt0bocF/?mid=dzjg0ibm"
                        const parts = cleanPath.split('/').filter(p => p);

                        if (parts.length >= 2) {
                            const homeSegment = parts[0]; // Now this is correctly "gardnersville-ENOwpmY9"
                            const awaySegment = parts[1]; // Now this is correctly "heaven-eleven-rZt0bocF"

                            // Your extraction logic remains the same and is correct:
                            const homeSlug = homeSegment.substring(0, homeSegment.lastIndexOf('-'));
                            homeTeamId = homeSegment.substring(homeSegment.lastIndexOf('-') + 1);

                            const awaySlug = awaySegment.substring(0, awaySegment.lastIndexOf('-'));
                            awayTeamId = awaySegment.substring(awaySegment.lastIndexOf('-') + 1);

                            homeTeamUrl = `https://www.flashscore.com/team/${homeSlug}/${homeTeamId}/`;
                            awayTeamUrl = `https://www.flashscore.com/team/${awaySlug}/${awayTeamId}/`;

                            // Extract fixture ID from query params
                            const urlParts = matchLink.split('?');
                            if (urlParts.length > 1) {
                                const queryParams = urlParts[1].split('&');
                                for (const param of queryParams) {
                                    if (param.startsWith('mid=')) {
                                        cleanId = param.substring(4);
                                        break;
                                    }
                                }
                            }
                        }
                    }

                    const home = getText(row, selectors.h2h_row_participant_home);
                    const away = getText(row, selectors.h2h_row_participant_away);

                    const matchData = {
                        date: getText(row, selectors.h2h_row_date),
                        home: home,
                        away: away,
                        score: `${scoreHome}-${scoreAway}`,
                        winner: winner,
                        perspective_result: perspectiveResult,
                        match_link: matchLink,
                        match_url: matchLink,
                        home_team_url: homeTeamUrl,
                        away_team_url: awayTeamUrl,
                        fixture_id: cleanId,
                        league_name: getText(row, selectors.h2h_row_league_icon),
                        home_team_id: homeTeamId,
                        away_team_id: awayTeamId
                    };

                    results[sectionMap.target].push(matchData);
                } catch (e) {
                    results.parsing_errors.push({
                        error: `Row parsing failed: ${e.message}`,
                        html: row.outerHTML.substring(0, 200) + '...'
                    });
                }
            });
        });

        const countryEl = document.querySelector(selectors.meta_breadcrumb_country);
        const leagueEl = document.querySelector(selectors.meta_breadcrumb_league);
        const region = countryEl ? countryEl.innerText.trim().toUpperCase() : '';
        const league = leagueEl ? leagueEl.innerText.trim() : '';
        region_league = (region && league) ? `${region} - ${league}` : 'Unknown';

        results.home_team = home_team_main;
        results.away_team = away_team_main;
        results.region_league = region_league;

        return results;
    }"""

    # Pass all parameters as a single object to respect Playwright's API
    data_object = {
        "selectors": selectors,
        "home_team_main": home_team_main,
        "away_team_main": away_team_main
    }
    evaluation_result = await page.evaluate(js_code, data_object)

    if (evaluation_result.get("parsing_errors")):
        print(f"      [Extractor Warning] Encountered {len(evaluation_result['parsing_errors'])} parsing errors.")

    print(f"      [Extractor] Found {len(evaluation_result.get('home_last_10_matches',[]))} home, {len(evaluation_result.get('away_last_10_matches',[]))} away, {len(evaluation_result.get('head_to_head',[]))} H2H matches.")
    return evaluation_result


async def save_extracted_h2h_to_schedules(h2h_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Saves historical matches found during extraction to the schedules.csv file.
    Returns a list of the newly saved match dictionaries for further processing.
    """
    from Data.Access.db_helpers import save_team_entry

    all_past_matches = (
        h2h_data.get("home_last_10_matches", []) +
        h2h_data.get("away_last_10_matches", []) +
        h2h_data.get("head_to_head", [])
    )

    saved_matches = []
    for match in all_past_matches:
        if not match or not match.get('date') or not match.get('score'):
            continue

        home_team = match.get('home')
        away_team = match.get('away')
        score_parts = match.get('score', 'N/A').split('-')

        match_link = match.get('match_url') or match.get('match_link')
        home_team_id = match.get('home_team_id')
        away_team_id = match.get('away_team_id')
        fixture_id = match.get('fixture_id')

        entry_to_save = {
            'fixture_id': fixture_id,
            'date': match.get('date'),
            'match_time': 'N/A',  # Will be updated by enrichment
            'region_league': h2h_data.get("region_league", "Unknown"),
            'home_team': home_team,
            'away_team': away_team,
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_score': score_parts[0].strip() if len(score_parts) > 1 else 'N/A',
            'away_score': score_parts[1].strip() if len(score_parts) > 1 else 'N/A',
            'match_status': 'finished',
            'match_link': match_link
        }

        save_schedule_entry(entry_to_save)

        # Save team entries
        if home_team_id:
            home_team_url = f"https://www.flashscore.com/team/{home_team.lower().replace(' ', '-')}/{home_team_id}/"
            save_team_entry({'team_id': home_team_id, 'team_name': home_team, 'region_league': h2h_data.get("region_league", "Unknown"), 'team_url': home_team_url})
        if away_team_id:
            away_team_url = f"https://www.flashscore.com/team/{away_team.lower().replace(' ', '-')}/{away_team_id}/"
            save_team_entry({'team_id': away_team_id, 'team_name': away_team, 'region_league': h2h_data.get("region_league", "Unknown"), 'team_url': away_team_url})

        saved_matches.append(entry_to_save)

    return saved_matches
