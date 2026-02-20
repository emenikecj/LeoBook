# league_page_extractor.py: league_page_extractor.py: Extract all match URLs from a league's results/fixtures page.
# Part of LeoBook Core — Browser Extractors
#
# Functions: extract_league_match_urls(), get_active_leagues_from_main(), extract_league_metadata()

import asyncio
from typing import List, Dict, Any
from playwright.async_api import Page, TimeoutError
from Core.Intelligence.intelligence import get_selector
from Core.Browser.site_helpers import fs_universal_popup_dismissal

async def extract_league_match_urls(page: Page, league_url: str, mode: str = "results") -> List[str]:
    """
    Visits a league page (results or fixtures) and harvests all match URLs.
    
    Args:
        page: Playwright page instance.
        league_url: Base league URL (e.g., https://www.flashscore.com/football/england/premier-league/)
        mode: 'results' or 'fixtures'
    """
    target_url = league_url.rstrip('/')
    if mode == "results":
        if not target_url.endswith("/results"):
            target_url += "/results/"
    else:
        if not target_url.endswith("/fixtures"):
            target_url += "/fixtures/"
            
    print(f"      [League Extractor] Visiting: {target_url}")
    
    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)
        await fs_universal_popup_dismissal(page)
        
        # 1. Expand all matches ("Show more matches")
        show_more_sel = ".event__more"
        max_expansions = 10 # Safety limit
        expansions = 0
        
        while expansions < max_expansions:
            try:
                show_more_btn = page.locator(show_more_sel)
                if await show_more_btn.is_visible(timeout=5000):
                    print(f"      [League Extractor] Clicking 'Show more matches' (Attempt {expansions + 1})...")
                    await show_more_btn.click()
                    await asyncio.sleep(2)
                    expansions += 1
                else:
                    break
            except:
                break
                
        # 2. Extract Match IDs/Links
        # Match rows usually have IDs like 'g_1_XXXXXXX'
        js_code = """() => {
            const links = new Set();
            // Look for elements with ID starting with g_1_
            const matchElements = document.querySelectorAll('[id^="g_1_"]');
            matchElements.forEach(el => {
                const id = el.id.replace('g_1_', '');
                if (id) {
                    links.add(`/match/${id}/#/match-summary`);
                }
            });
            return Array.from(links);
        }"""
        
        match_links = await page.evaluate(js_code)
        print(f"      [League Extractor] Found {len(match_links)} match URLs on page.")
        return match_links
        
    except Exception as e:
        print(f"      [League Extractor Error] Failed to process {target_url}: {e}")
        return []

async def get_active_leagues_from_main(page: Page) -> List[Dict[str, str]]:
    """
    Optional: Scrapes the main page to find all 'live' or 'today' league URLs.
    """
    try:
        # Extract from the 'My Leagues' or 'Summary' sections
        js_code = """() => {
            const leagues = [];
            const leagueEls = document.querySelectorAll('.event__header');
            leagueEls.forEach(el => {
                const link = el.querySelector('a.event__title--link');
                const title = el.querySelector('.event__title--name');
                if (link && title) {
                    leagues.append({
                        'name': title.innerText.trim(),
                        'url': link.href
                    });
                }
            });
            return leagues;
        }"""
        return await page.evaluate(js_code)
    except:
        return []

async def extract_league_metadata(page: Page) -> Dict[str, str]:
    """
    Extracts league metadata: crest, country flag, etc.
    """
    try:
        js_code = """() => {
            const getAttribute = (sel, attr) => document.querySelector(sel)?.[attr] || '';
            const getText = (sel) => document.querySelector(sel)?.innerText.trim() || '';
            
            return {
                'league_crest': getAttribute('.tournamentHeader__image', 'src'),
                'region_flag': getAttribute('.tournamentHeader__country img', 'src'),
                'region': getText('.tournamentHeader__country'),
                'league_name': getText('.tournamentHeader__league')
            };
        }"""
        return await page.evaluate(js_code)
    except:
        return {}
