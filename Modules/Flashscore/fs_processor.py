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
from Core.Utils.utils import log_error_state
import re
import os

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
from Core.Intelligence.rule_engine import RuleEngine
from .fs_utils import retry_extraction

# Cache of league IDs already enriched in this cycle (avoid duplicate page visits)
_enriched_leagues = set()

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
    fixture_id = match_data.get('fixture_id') or match_data.get('id') or 'unknown'
    match_label = f"{match_data.get('home_team', 'unknown')}_vs_{match_data.get('away_team', 'unknown')}_{fixture_id}"

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
                h2h_data = await retry_extraction(extract_h2h_data, page, match_data['home_team'], match_data['away_team'], "fs_h2h_tab", page=page, context_key="fs_h2h_tab", element_key="h2h_match_rows")

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
                standings_result = await retry_extraction(extract_standings_data, page, page=page, context_key="fs_standings_tab", element_key="standings_row")
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

        # --- Meta Data Extraction (Leagues & Teams) — Shared Utility ---
        from .enrich_match_metadata import extract_match_page_metadata
        meta_result = await extract_match_page_metadata(page, match_data)

        # --- Per-Match League Enrichment (v3.6) ---
        # Visit the league page to extract full metadata, match URLs, team data
        league_url = meta_result.get('league_url') or match_data.get('league_url', '')
        league_id = match_data.get('league_id', '')
        league_name = meta_result.get('league_name', '')
        region_name = meta_result.get('region_name', '')

        league_inline_result = {}
        if league_url and league_id and league_id not in _enriched_leagues:
            try:
                from Scripts.enrich_leagues import enrich_league_inline
                league_inline_result = await enrich_league_inline(page, league_url, league_id, league_name, region_name) or {}
                _enriched_leagues.add(league_id)
            except Exception as e:
                print(f"      [Enrich] League enrichment error (non-fatal): {e}")
        elif league_id in _enriched_leagues:
            print(f"      [Enrich] League '{league_name}' already enriched this cycle — skipping.")

        # --- Per-Match Search Dict (v3.7) ---
        # Collect ALL discovered teams from league page + standings + match
        # and batch-enrich them via LLM (batches of 10)
        try:
            from Scripts.build_search_dict import enrich_match_search_dict, enrich_batch_teams_search_dict

            # 1. Enrich the league + 2 match teams (lightweight, max 3 items)
            await enrich_match_search_dict(
                league_name=match_data.get('region_league', league_name),
                league_id=league_id,
                home_team=match_data.get('home_team', ''),
                home_id=match_data.get('home_team_id', ''),
                away_team=match_data.get('away_team', ''),
                away_id=match_data.get('away_team_id', '')
            )

            # NOTE: Heavy batch enrichment runs ONCE in manager.py before match loop.
            # Only per-match lightweight check (2 teams + 1 league) runs here.

        except Exception as e:
            print(f"      [SearchDict] Search dict error (non-fatal): {e}")

        # --- MANDATORY RULE: Enrichment Complete ---
        print(f"      [Rule] SearchDict enrichment complete for {match_label} — proceeding to prediction.")
        match_link = match_data.get('match_link', '')
        if match_link:
            try:
                await page.goto(match_link, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(1.5)
            except Exception:
                pass

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
        try:
            await context.close()
        except Exception:
            pass  # Context may already be destroyed
