# standings_extractor.py: standings_extractor.py: Extraction logic for league standings and goal differences.
# Part of LeoBook Core — Browser Extractors
#
# Functions: activate_standings_tab(), _post_activation_prep(), extract_standings_data()

import re
from playwright.async_api import Page, TimeoutError, ElementHandle
import re
from typing import Dict, Any, List
from Core.Intelligence.selector_manager import SelectorManager
from Core.Browser.site_helpers import fs_universal_popup_dismissal
import asyncio

async def activate_standings_tab(page: Page) -> bool:
    """
    Activates the Standings tab on the match page.
    """
    print("      [Extractor] Activating Standings tab...")
    # Use the CORRECT key 'tab_standings' from 'fs_match_page' as defined in knowledge.json
    tab_selector = SelectorManager.get_selector("fs_match_page", "tab_standings")
    
    if not tab_selector:
        print("      [Extractor] Error: 'tab_standings' selector not found in 'fs_match_page' context.")
        return False

    try:
        # 1. Try primary selector from knowledge.json
        if tab_selector and await page.locator(tab_selector).count() > 0:
            locator = page.locator(tab_selector)
            if await locator.is_visible(timeout=3000):
                await locator.click()
                await _post_activation_prep(page)
                return True

        # 2. Try URL-based detection (most robust across sports: /standings, /draw, /table)
        print("      [Extractor] Selector not visible. Trying URL-based detection (#/standings, #/draw, #/table)...")
        url_selectors = ['a[href*="#/standings"]', 'a[href*="#/draw"]', 'a[href*="#/table"]']
        for sel in url_selectors:
            if await page.locator(sel).count() > 0:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await _post_activation_prep(page)
                    return True

        # 3. Try text-based fallback with broader labels
        print("      [Extractor] URL detection failed. Trying expanded text fallback (STANDINGS, DRAW, TABLE)...")
        fallbacks = ["STANDINGS", "DRAW", "TABLE", "Standings", "Draw", "Table"]
        for label in fallbacks:
             # Look for anchor tags containing the text inside the detail__tabs container
             text_locator = page.locator(f".detail__tabs a:has-text('{label}')")
             if await text_locator.count() > 0:
                btn = text_locator.first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await _post_activation_prep(page)
                    return True

        print(f"      [Extractor] Standings tab could not be activated (Selector: {tab_selector or 'N/A'})")
        return False
    except Exception as e:
        print(f"      [Extractor] Failed to activate Standings tab: {e}")
        return False

async def _post_activation_prep(page: Page):
    """Wait for content and dismiss popups after tab activation."""
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(2.0)
    await fs_universal_popup_dismissal(page, "fs_standings_tab")
    await asyncio.sleep(3.0)

async def extract_standings_data(page: Page, context: str = "fs_standings_tab") -> Dict[str, Any]:
    """
    Extracts essential standings data: position, team, stats, and league info.
    """
    print("      [Extractor] Extracting Standings tab...")

    selectors = {
        "standings_row": SelectorManager.get_selector(context, "standings_row") or ".ui-table__row",
        "standings_col_rank": SelectorManager.get_selector(context, "standings_col_rank") or ".tableCellRank",
        "standings_col_team_name": SelectorManager.get_selector(context, "standings_col_team_name") or ".tableCellParticipant__name",
        "standings_col_team_link": SelectorManager.get_selector(context, "standings_col_team_link") or ".tableCellParticipant__name a",
        "standings_col_matches_played": SelectorManager.get_selector(context, "standings_col_matches_played") or "td:nth-child(3)",
        "standings_col_wins": SelectorManager.get_selector(context, "standings_col_wins") or "td:nth-child(4)",
        "standings_col_draws": SelectorManager.get_selector(context, "standings_col_draws") or "td:nth-child(5)",
        "standings_col_losses": SelectorManager.get_selector(context, "standings_col_losses") or "td:nth-child(6)",
        "standings_col_goals": SelectorManager.get_selector(context, "standings_col_goals") or "td:nth-child(7)",
        "standings_col_points": SelectorManager.get_selector(context, "standings_col_points") or ".tableCellPoints",
        "standings_col_form": SelectorManager.get_selector(context, "standings_col_form") or ".tableCellForm",
        "meta_breadcrumb_country": SelectorManager.get_selector(context, "meta_breadcrumb_country") or ".tournamentHeader__country",
        "meta_breadcrumb_league": SelectorManager.get_selector(context, "meta_breadcrumb_league") or ".tournamentHeader__league a",
    }

    from Core.Utils.constants import WAIT_FOR_LOAD_STATE_TIMEOUT
    await page.wait_for_selector(selectors['standings_row'], timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)

    js_code = r"""(selectors) => {
        const getText = (el, sel) => {
            const elem = el?.querySelector(sel);
            return elem ? elem.innerText?.trim() : null;
        };
        const getInt = (text) => {
            if (text === null) return null;
            const parsed = parseInt(text.replace(/[()]/g, ''), 10);
            return isNaN(parsed) ? null : parsed;
        };
        const getHref = (el, sel) => {
            const elem = el?.querySelector(sel);
            return elem ? elem.href : null;
        };

        const table = [];

        const rows = document.querySelectorAll(selectors.standings_row);
        if (rows.length === 0) {
            return { standings: [], region_league: 'Unknown', parsing_errors: ['No table rows found'] };
        }

        rows.forEach((row, index) => {
            const teamLink = getHref(row, selectors.standings_col_team_link);
            let teamId = null;
            if (teamLink) {
                const parts = teamLink.split('/').filter(p => p);
                const teamIndex = parts.indexOf('team');
                if (teamIndex !== -1 && parts.length > teamIndex + 2) {
                    teamId = parts[teamIndex + 2];
                }
            }

            let gf = null, ga = null;
            const goals = getText(row, selectors.standings_col_goals);
            if (goals && goals.includes(':')) {
                [gf, ga] = goals.split(':').map(p => {
                    const parsed = parseInt(p.trim());
                    return isNaN(parsed) ? null : parsed;
                });
            }

            const positionText = getText(row, selectors.standings_col_rank);
            const position = getInt(positionText) || (index + 1);

            const teamName = getText(row, selectors.standings_col_team_name);
            const team = teamName || `Team ${index + 1}`;

            table.push({
                position: position,
                team_name: team,
                team_id: teamId,
                played: getInt(getText(row, selectors.standings_col_matches_played)),
                wins: getInt(getText(row, selectors.standings_col_wins)),
                draws: getInt(getText(row, selectors.standings_col_draws)),
                losses: getInt(getText(row, selectors.standings_col_losses)),
                goals_for: gf,
                goals_against: ga,
                goal_difference: (gf !== null && ga !== null) ? (gf - ga) : null,
                points: getInt(getText(row, selectors.standings_col_points)),
                form: getText(row, selectors.standings_col_form),
            });
        });

        const country = document.querySelector(selectors.meta_breadcrumb_country)?.innerText?.trim()?.toUpperCase();
        const leagueEl = document.querySelector(selectors.meta_breadcrumb_league);
        const league = leagueEl?.innerText?.trim();
        const league_url = leagueEl?.href || null;
        const region_league = (country && league) ? `${country} - ${league}` : 'Unknown';

        return {
            standings: table,
            region_league: region_league,
            league_url: league_url,
            parsing_errors: []
        };
    }"""

    evaluation_result = await page.evaluate(js_code, selectors)

    team_count = len(evaluation_result.get('standings', []))
    league_name = evaluation_result.get('region_league', 'Unknown League')
    print(f"      [Extractor] Found {team_count} teams in standings for '{league_name}'.")

    return evaluation_result
