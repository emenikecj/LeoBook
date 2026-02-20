# fs_processor.py: fs_processor.py: Match processing and prediction generation flow.
# Part of LeoBook Modules — Flashscore
#
# Functions: strip_league_stage(), process_match_task()

import asyncio
from playwright.async_api import Browser
from Data.Access.db_helpers import save_prediction, save_region_league_entry, save_standings, save_team_entry
from Core.Browser.site_helpers import fs_universal_popup_dismissal
from Core.Browser.Extractors.h2h_extractor import extract_h2h_data, activate_h2h_tab, save_extracted_h2h_to_schedules
from Core.Browser.Extractors.standings_extractor import extract_standings_data, activate_standings_tab
from Core.Utils.monitor import PageMonitor
from Core.Utils.utils import log_error_state
import re

def strip_league_stage(league_name: str):
    """Strips ' - Round X' etc. and returns (clean_league, stage)."""
    if not league_name: return "", ""
    # Common patterns: ' - Round 25', ' - Group A', ' - Play Offs', ' - Qualification'
    match = re.search(r" - (Round \d+|Group [A-Z]|Play Offs|Qualification|Relegation Group|Championship Group|Finals?)$", league_name, re.IGNORECASE)
    if match:
        stage = match.group(1)
        base_league = league_name[:match.start()].strip()
        return base_league, stage
    return league_name, ""
from Core.Utils.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT
from Core.Intelligence.model import RuleEngine
from .fs_utils import retry_extraction

async def process_match_task(match_data: dict, browser: Browser):
    """
    Worker function to process a single match in a new page/context.
    """
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Mobile Safari/537.36"
        ),
        viewport={'width': 450, 'height': 900},
        timezone_id="Africa/Lagos"
    )
    page = await context.new_page()
    PageMonitor.attach_listeners(page)
    match_label = f"{match_data.get('home_team', 'unknown')}_vs_{match_data.get('away_team', 'unknown')}"

    try:
        print(f"    [Batch Start] {match_data['home_team']} vs {match_data['away_team']}")

        full_match_url = f"{match_data['match_link']}"
        await page.goto(full_match_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
        await asyncio.sleep(2.0)

        await fs_universal_popup_dismissal(page, "fs_match_page")
        await page.wait_for_load_state("domcontentloaded", timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
        
        # --- H2H Tab & Expansion (Mobile Optimized) ---
        h2h_data = {}
        if await activate_h2h_tab(page):
            try:
                # Sections: Home Last 5/10, Away Last 5/10, Mutual H2H
                show_more_selector = ".h2h__section .h2h__showMore"
                
                print("    [H2H Expansion] Expanding sections for deep analysis...")
                for _ in range(2): # Click twice for each to get ~15 matches
                    buttons = page.locator(show_more_selector)
                    btn_count = await buttons.count()
                    for j in range(btn_count):
                        try:
                            btn = buttons.nth(j)
                            if await btn.is_visible():
                                await btn.click(timeout=5000)
                                await asyncio.sleep(1.0)
                        except:
                            continue
                
                await asyncio.sleep(1.5)
                h2h_data = await retry_extraction(extract_h2h_data, page, match_data['home_team'], match_data['away_team'], "fs_h2h_tab")

                h2h_count = len(h2h_data.get("home_last_10_matches", [])) + len(h2h_data.get("away_last_10_matches", [])) + len(h2h_data.get("head_to_head", []))
                print(f"      [OK H2H] H2H tab data extracted for {match_label} ({h2h_count} matches found)")

                await save_extracted_h2h_to_schedules(h2h_data)

            except Exception as e:
                print(f"      [Warning] Failed to fully load/expand H2H tab for {match_label}: {e}")
        else:
            print(f"      [Warning] H2H tab inaccessible for {match_label}")

        # --- Data Quality Validation ---
        home_form_count = len(h2h_data.get("home_last_10_matches", []))
        away_form_count = len(h2h_data.get("away_last_10_matches", []))
        
        if home_form_count < 3 or away_form_count < 3:
            print(f"      [Data Quality] Skipped {match_label}: Insufficient form data (Home: {home_form_count}, Away: {away_form_count})")
            return False

        # --- Standings Tab ---
        standings_data = []
        standings_league = "Unknown"
        
        if await activate_standings_tab(page):
            try:
                standings_result = await retry_extraction(extract_standings_data, page)
                standings_data = standings_result.get("standings", [])
                standings_league = standings_result.get("region_league", "Unknown")
                if standings_league == "Unknown":
                    standings_league = h2h_data.get("region_league", "Unknown")
                standings_league_url = standings_result.get("league_url", "")
                if standings_result.get("has_draw_table"):
                    print(f"      [Graceful Skip] Match has Draw table (Cup/Tournament). Proceeding without standings.")
                    # We don't return False here, allowing H2H-only prediction
                if standings_data and standings_league != "Unknown":
                    for row in standings_data:
                        row['url'] = standings_league_url
                    save_standings(standings_data, standings_league)
                    print(f"      [OK Standing] Standings tab data extracted for {standings_league}")
                ## Phase 5: League Stage Parsing Fix
                # - [x] Update `db_helpers.py` headers for `league_stage`
                # - [x] Update `enrich_all_schedules.py`
                ## Phase 8: Draw Tab Skip Logic
                # - [x] Implement graceful standings skip in `fs_processor.py`
            except Exception as e:
                print(f"      [Warning] Failed to load Standings tab for {match_label}: {e}")

        # --- Meta Data Extraction (Leagues & Teams) ---
        try:
            from Core.Intelligence.selector_manager import SelectorManager
            
            sel_region_name = await SelectorManager.get_selector_auto(page, "fs_match_page", "region_name")
            sel_region_flag = await SelectorManager.get_selector_auto(page, "fs_match_page", "region_flag_img")
            sel_league_url = await SelectorManager.get_selector_auto(page, "fs_match_page", "league_url")
            
            sel_home_crest = await SelectorManager.get_selector_auto(page, "fs_match_page", "home_crest")
            sel_home_url = await SelectorManager.get_selector_auto(page, "fs_match_page", "home_url")
            sel_away_crest = await SelectorManager.get_selector_auto(page, "fs_match_page", "away_crest")
            sel_away_url = await SelectorManager.get_selector_auto(page, "fs_match_page", "away_url")

            region_name = await page.locator(sel_region_name).inner_text() if sel_region_name else "Unknown"
            region_flag = await page.locator(sel_region_flag).get_attribute("src") if sel_region_flag else ""
            region_url = await page.locator(sel_region_url).get_attribute("href") if sel_region_url else ""
            league_url = await page.locator(sel_league_url).get_attribute("href") if sel_league_url else ""
            league_name = await page.locator(sel_league_url).inner_text() if sel_league_url else "Unknown"
            
            # Extract rl_id from league URL fragment (e.g. #/ldxRUZwe)
            # Or from page source if URL is generic
            rl_id = ""
            if league_url and "#/" in league_url:
                rl_id = league_url.split("#/")[-1]
            
            if not rl_id:
                # Fallback: look for tournamentId in page source
                content = await page.content()
                import re
                match = re.search(r"tournamentId[:\s]+'([^']+)'", content)
                if match:
                    rl_id = match.group(1)
            
            if not rl_id:
                rl_id = f"{region_name}_{league_name}".replace(' ', '_').replace('-', '_').upper()
            
            # --- LEAGUE STAGE PARSING ---
            clean_league, stage = strip_league_stage(league_name)
            match_data['region_league'] = f"{region_name.upper()} - {clean_league}"
            match_data['league_stage'] = stage
            match_data['league_id'] = rl_id
            
            save_region_league_entry({
                'rl_id': rl_id,
                'region': region_name,
                'region_flag': region_flag,
                'region_url': region_url,
                'league': league_name,
                'league_url': league_url
            })

            # Home Team
            save_team_entry({
                'team_id': match_data.get('home_team_id'),
                'team_name': match_data.get('home_team'),
                'rl_ids': rl_id,
                'team_crest': await page.locator(sel_home_crest).get_attribute("src") if sel_home_crest else "",
                'team_url': await page.locator(sel_home_url).get_attribute("href") if sel_home_url else ""
            })

            # Away Team
            save_team_entry({
                'team_id': match_data.get('away_team_id'),
                'team_name': match_data.get('away_team'),
                'rl_ids': rl_id,
                'team_crest': await page.locator(sel_away_crest).get_attribute("src") if sel_away_crest else "",
                'team_url': await page.locator(sel_away_url).get_attribute("href") if sel_away_url else ""
            })
        except Exception as e:
            print(f"      [Warning] Failed to extract expanded metadata for {match_label}: {e}")

        # --- Process Data & Predict ---
        analysis_input = {"h2h_data": h2h_data, "standings": standings_data}
        prediction = RuleEngine.analyze(analysis_input)

        # Record Reference Data for Offline Review & Debugging
        h2h_ids = []
        if h2h_data:
            for m in h2h_data.get('head_to_head', []):
                if m.get('fixture_id'): h2h_ids.append(m['fixture_id'])
        
        home_form_ids = []
        away_form_ids = []
        if h2h_data:
            for m in h2h_data.get('home_last_10_matches', []):
                if m.get('fixture_id'): home_form_ids.append(m['fixture_id'])
            for m in h2h_data.get('away_last_10_matches', []):
                if m.get('fixture_id'): away_form_ids.append(m['fixture_id'])

        prediction['h2h_fixture_ids'] = h2h_ids
        prediction['form_fixture_ids'] = home_form_ids + away_form_ids
        prediction['standings_snapshot'] = standings_data if standings_data else []

        total_xg = prediction.get("total_xg", 0.0)
        p_type = prediction.get("type", "SKIP")

        # Rule Engine Logic Gate: Prioritize Over markets if Avg Goals > 1.8
        # We also verify if a prediction was skipped despite high xG
        if total_xg > 1.8 and p_type == "SKIP":
            print(f"      [xG Signal] High Avg Goals ({total_xg}) detected. Categorizing as OVER 1.5 fallback.")
            prediction.update({
                "type": "OVER 1.5",
                "market_prediction": "OVER 1.5",
                "confidence": "Medium",
                "reason": [f"High Avg Goals ({total_xg}) logic gate met"]
            })
            p_type = "OVER 1.5"

        if p_type != "SKIP":
            # Verification: If Avg Goals is too low, downgrade confidence
            if total_xg < 1.4 and prediction.get("confidence") == "High":
                prediction["confidence"] = "Medium"
                prediction["reason"].append(f"Confidence adjusted for low Avg Goals ({total_xg})")

            save_prediction(match_data, prediction)
            print(f"            [OK Signal] {match_label} (Type: {p_type}, xG: {total_xg})")
            return True
        else:
            print(f"      [NO Signal] {match_label} (xG: {total_xg})")
            return False

    except Exception as e:
        print(f"      [Error] Match failed {match_label}: {e}")
        await log_error_state(page, f"process_match_task_{match_label}", e)
        return False
    finally:
        await asyncio.sleep(1.0)
        await context.close()
