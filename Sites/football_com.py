# Sites/football_com.py

import asyncio
import os
import csv
import json
import re
from pathlib import Path
from datetime import datetime as dt
from typing import Dict, List, Optional

from playwright.async_api import Browser, Page
from google.generativeai.types import GenerationConfig

from Helpers.DB_Helpers.db_helpers import PREDICTIONS_CSV, update_prediction_status
from Helpers.Site_Helpers.site_helpers import fb_universal_popup_dismissal, get_main_frame
from Helpers.utils import AUTH_DIR, log_error_state
from Neo.intelligence import get_selector_auto
from Helpers.Site_Helpers.site_helpers import get_main_frame
from Helpers.Neo_Helpers.Managers.api_key_manager import gemini_api_call_with_rotation

PHONE = os.getenv("FB_PHONE")
PASSWORD = os.getenv("FB_PASSWORD")
AUTH_FILE = AUTH_DIR / "storage_state.json"


async def map_matches_with_gemini(predictions: List[Dict], site_matches: List[Dict], batch_size: int = 10) -> Dict[str, str]:
    """
    Uses Gemini to perform intelligent batch matching between CSV predictions and Site matches.
    """
    print("  [Gemini Intelligence] Mapping predictions to betting site matches in batches...")
    if not predictions or not site_matches:
        return {}

    all_mapped_matches = {}
    site_mini = [{"url": m.get("url"), "teams": f"{m.get('home')} vs {m.get('away')}", "league": m.get("league", ""), "datetime": m.get("datetime", m.get("time", ""))} for m in site_matches]

    for i in range(0, len(predictions), batch_size):
        current_batch_predictions = predictions[i:i + batch_size]
        preds_mini_batch = [{"id": p.get("fixture_id", "unknown"), "teams": f"{p.get('home_team')} vs {p.get('away_team')}", "league": p.get("region_league", ""), "datetime": f"{p.get('date')} {p.get('match_time')}"} for p in current_batch_predictions]

        prompt = f"""
        You are an expert football fixture matcher. Your only job: match each entry in PREDICTIONS to the correct entry in SITE_MATCHES.
        Rules:
        - Primary match: matching league first, then closest datetime and highly similar team names.
        - Only include matches you are highly confident about.
        - Output ONLY valid JSON: {{"prediction_id": "site_url", ...}}
        - If no confident match, omit that prediction.

        PREDICTIONS:
        {json.dumps(preds_mini_batch, indent=0)}

        SITE_MATCHES:
        {json.dumps(site_mini, indent=0)}
        """
        try:
            print(f"  [Gemini Intelligence] Processing batch {int(i/batch_size) + 1}/{(len(predictions) + batch_size - 1) // batch_size}...")
            response = await gemini_api_call_with_rotation(prompt, GenerationConfig(temperature=0.1, max_output_tokens=4096))
            if response.candidates:
                batch_mapping = json.loads(response.text)
                all_mapped_matches.update(batch_mapping)
        except Exception as e:
            print(f"  [Gemini Intelligence Error] Mapping failed for batch {int(i/batch_size) + 1}: {e}")

    print(f"  [Gemini Intelligence] Successfully mapped {len(all_mapped_matches)}/{len(predictions)} matches.")
    return all_mapped_matches


async def choose_best_bet_with_gemini(markets: List[Dict], prediction: Dict, page: Page) -> Optional[str]:
    """
    Uses Gemini to analyze available markets against a prediction to find the best betting opportunity.
    """
    print("    [Gemini Strategy] Analyzing markets to find the best edge...")
    prediction_details = {k: v for k, v in prediction.items() if k not in ['date', 'status']}
    prompt = f"""
    You are a professional sports betting analyst. Your ONLY goal is to find the SINGLE highest-edge bet from the available markets, prioritizing safety and value.
    CRITICAL INSTRUCTION: UNDERS ARE FORBIDDEN. Do NOT select ANY Under market (e.g., Under 2.5, BTTS-No).

    Allowed high-probability markets (in priority order):
    1. Strong/favorite team Over 0.5 Goals (safest playable bet, xG ≥ 1.2-1.4+)
    2. Strong/favorite team Over 1.5 Goals (when "scores 2+" or xG ≥ 1.8+)
    3. Over 1.5 Total Goals (safest over, total xG ≥ 2.0)
    4. Over 2.5 Total Goals (if explicitly tagged OVER_2.5)
    5. BTTS Yes (if btts=YES and trends are strong)
    6. Double Chance (favorite or draw) (fallback if others are unavailable)

    Rules:
    - Minimum odds: 1.15.
    - Greed is forbidden. A high-probability bet at 1.45 is better than a low-probability one at 3.20.
    - Never pick corners, cards, or player props.

    Response MUST be strict JSON only: {{"selector": "[data-gemini-selector-id='exact-id-here']", "reasoning": "Brief justification."}}

    PREDICTION_DATA:
    {json.dumps(prediction_details, indent=2)}

    AVAILABLE_MARKETS:
    {json.dumps(markets, indent=2)}
    """
    try:
        response = await gemini_api_call_with_rotation(prompt, generation_config=GenerationConfig(response_mime_type="application/json"))
        result = json.loads(response.text)
        selector = result.get("selector")
        reasoning = result.get("reasoning", "No reasoning provided.")
        if selector and isinstance(selector, str) and selector.startswith("[data-gemini-selector-id"):
            print(f"    [Gemini Strategy] Selected: {selector}")
            print(f"    [Gemini Reasoning] {reasoning}")
            if await page.locator(selector).count() > 0:
                return selector
            else:
                print("    [Gemini Verification Error] Selector chosen by Gemini not found on page!")
    except Exception as e:
        print(f"    [Gemini Strategy Error] Failed to get betting decision: {e}")
    return None


async def get_bet_slip_count(page: Page) -> int:
    """Extracts the current number of bets in the slip."""
    try:
        counter_sel = "section[data-op='betslip-icon'] span.odds"
        if await page.locator(counter_sel).count() > 0:
            text = await page.locator(counter_sel).inner_text(timeout=2000)
            return int(re.sub(r'\D', '', text) or 0)
    except:
        pass
    return 0


async def extract_all_markets(page: Page) -> List[Dict]:
    """Expands all market containers and extracts all available betting outcomes."""
    print("    [Harvest] Expanding and harvesting markets...")
    market_container_sel = await get_main_frame(page, "fb_match_page", "match_market_details_container") or ".market-details-container"
    market_header_sel = ".market-title, .group-header"
    market_name_sel = ".market-name, .market-title-text, .group-header__title"
    odds_button_sel = "[data-op*='odds'], .odds-button, .m-odds, .odds"
    all_markets_data = []

    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    await asyncio.sleep(2)
    market_containers = await page.locator(market_container_sel).all()
    print(f"    [Harvest] Found {len(market_containers)} potential market containers.")

    for i, container in enumerate(market_containers):
        try:
            header = container.locator(market_header_sel).first
            if await header.count() > 0:
                is_collapsed_icon = header.locator("svg[class*='down'], i[class*='down']")
                if await is_collapsed_icon.count() > 0 and await is_collapsed_icon.is_visible():
                    await header.click(timeout=3000)
                    await asyncio.sleep(0.75)

            market_data = await container.evaluate("""(container, selectors) => {
                const marketNameEl = container.querySelector(selectors.market_name_sel);
                const marketName = marketNameEl ? marketNameEl.innerText.trim().replace(/\\n/g, ' ') : `Unknown Market ${Math.random()}`;
                const outcomes = [];
                const buttons = Array.from(container.querySelectorAll(selectors.odds_button_sel));
                buttons.forEach((btn, index) => {
                    if (btn.offsetParent === null) return;
                    let outcomeName = "Unknown";
                    const parentRow = btn.closest('.market-line, .seln-container, div[class*="outcome"]');
                    if (parentRow) {
                        const nameEl = parentRow.querySelector('.seln-name, .outcome-name, .label, span:not([class*="odds"])');
                        if (nameEl) outcomeName = nameEl.innerText.trim();
                    }
                    if (outcomeName === "Unknown") outcomeName = `Outcome ${index + 1}`;
                    const oddsEl = btn.querySelector('.odds, .price') || btn;
                    const oddsText = oddsEl ? oddsEl.innerText.trim().split('\\n').pop() : "0.0";
                    if (parseFloat(oddsText) > 1.0) {
                        const cleanMarket = marketName.replace(/[^a-zA-Z0-9]/g, '');
                        const cleanOutcome = outcomeName.replace(/[^a-zA-Z0-9]/g, '');
                        const unique_id = `gemini-btn-${cleanMarket}-${index}`;
                        btn.setAttribute('data-gemini-selector-id', unique_id);
                        outcomes.push({ name: outcomeName, odds: oddsText, selector: `[data-gemini-selector-id='${unique_id}']` });
                    }
                });
                return outcomes.length > 0 ? { market_name: marketName, outcomes: outcomes } : null;
            }""", {"market_name_sel": market_name_sel, "odds_button_sel": odds_button_sel})

            if market_data:
                all_markets_data.append(market_data)
        except Exception as e:
            print(f"      [Harvest Debug] Error processing a market container: {e}")

    print(f"  [Harvest] Successfully harvested {len(all_markets_data)} markets.")
    return all_markets_data


async def get_balance(page: Page) -> float:
    """Retrieves and parses the account balance."""
    print("  [Money] Retrieving account balance...")
    try:
        balance_sel = await get_selector_auto(page, "fb_main_page", "navbar_balance")
        if balance_sel and await page.locator(balance_sel).count() > 0:
            balance_text = await page.locator(balance_sel).inner_text(timeout=5000)
            cleaned_text = re.sub(r'[^\d.]', '', balance_text)
            if cleaned_text:
                print(f"  [Money] Found balance: {balance_text}")
                return float(cleaned_text)
    except Exception as e:
        print(f"  [Money Error] Could not parse balance: {e}")
    return 0.0


async def login(page: Page):
    """Handles the login process for Football.com."""
    print("  [Navigation] Going to Football.com...")
    await page.goto("https://www.football.com/ng/m/", wait_until='domcontentloaded')
    try:
        login_page_selector = await get_selector_auto(page, "fb_login_page", "top_right_login")
        if login_page_selector and await page.locator(login_page_selector).count() > 0:
            await page.click(login_page_selector)
            await asyncio.sleep(5)

        mobile_selector = await get_selector_auto(page, "fb_login_page", "center_input_mobile_number") or "input[type='tel']"
        password_selector = await get_selector_auto(page, "fb_login_page", "center_input_password") or "input[type='password']"
        login_btn_selector = await get_selector_auto(page, "fb_login_page", "bottom_button_login") or "button:has-text('Login')"

        await page.wait_for_selector(mobile_selector, state="visible", timeout=15000)
        # Ensure PHONE and PASSWORD are not None before passing to fill
        if PHONE: await page.fill(mobile_selector, PHONE)
        if PASSWORD: await page.fill(password_selector, PASSWORD)
        await page.click(login_btn_selector)
        await page.wait_for_load_state('domcontentloaded', timeout=30000)
        print("[Login] Football.com Login Successful.")
    except Exception as e:
        print(f"[Login Error] {e}")
        raise


async def extract_all_matches_via_expansion(page: Page, target_date: str) -> List[Dict]:
    """Iterates through all league headers, expands them, and extracts matches for a specific date."""
    print("  [Harvest] Starting 'Expand & Harvest' sequence...")
    all_matches = []
    league_header_sel = await get_selector_auto(page, "fb_schedule_page", "league_header") or ".league-title-wrapper"
    match_card_sel = await get_selector_auto(page, "fb_schedule_page", "match_rows") or ".match-card-section.match-card"
    match_url_sel = await get_selector_auto(page, "fb_schedule_page", "match_url") or ".match-card > a.card-link"
    league_title_sel = await get_selector_auto(page, "fb_schedule_page", "league_title_link") or ".league-link"

    try:
        league_headers = await page.locator(league_header_sel).all()
        print(f"  [Harvest] Found {len(league_headers)} league headers.")

        for i, header_locator in enumerate(league_headers):
            try:
                league_element = header_locator.locator(league_title_sel).first
                league_text = (await league_element.inner_text(timeout=2000)).strip().replace('\n', ' - ') if await league_element.is_visible() else f"Unknown League {i+1}"
                print(f"  -> Processing: {league_text}")

                await header_locator.click(timeout=5000)
                await asyncio.sleep(2.0)

                matches_container = await header_locator.evaluate_handle('(el) => el.nextElementSibling')
                if matches_container:
                    matches_in_section = await matches_container.evaluate("""(container, args) => {
                        const { selectors, leagueText } = args;
                        const results = [];
                        const cards = container.querySelectorAll(selectors.match_card_sel);
                        cards.forEach(card => {
                            const homeEl = card.querySelector('.home-team-name');
                            const awayEl = card.querySelector('.away-team-name');
                            const timeEl = card.querySelector('.time');
                            const linkEl = card.querySelector(selectors.match_url_sel);
                            if (linkEl && homeEl && awayEl) {
                                results.push({ home: homeEl.innerText.trim(), away: awayEl.innerText.trim(), time: timeEl ? timeEl.innerText.trim() : "N/A", league: leagueText, url: linkEl.href, date: args.targetDate });
                            }
                        });
                        return results;
                    }""", {"selectors": {"match_card_sel": match_card_sel, "match_url_sel": match_url_sel}, "leagueText": league_text})
                    if matches_in_section:
                        all_matches.extend(matches_in_section)
            except Exception as e:
                print(f"    [Harvest Error] Failed to process a league: {e}")
    except Exception as e:
        print(f"  [Harvest] Overall harvesting error: {e}")

    print(f"  [Harvest] Total matches found: {len(all_matches)}")
    return all_matches


async def run_football_com_booking(browser: Browser):
    """
    Main function to handle Football.com login, match mapping, and bet placement.
    """
    print("\n--- Running Football.com Booking ---")
    
    # 1. Get pending predictions
    pending_predictions = []
    if os.path.exists(PREDICTIONS_CSV):
        with open(PREDICTIONS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            pending_predictions = [row for row in reader if row.get('status') == 'pending']

    if not pending_predictions:
        print("  [Info] No pending predictions to book.")
        return

    # Group predictions by date
    predictions_by_date = {}
    for pred in pending_predictions:
        date_str = pred.get('date')
        if date_str:
            if date_str not in predictions_by_date:
                predictions_by_date[date_str] = []
            predictions_by_date[date_str].append(pred)

    context = None
    page = None
    try:
        # 2. Login or load session
        if AUTH_FILE.exists():
            print("  [Auth] Found saved session. Loading state...")
            context = await browser.new_context(storage_state=AUTH_FILE, viewport={'width': 375, 'height': 812})
            page = await context.new_page()
            await page.goto("https://www.football.com/ng/m/", wait_until='domcontentloaded', timeout=180000)
        else:
            print("  [Auth] No saved session found. Performing new login...")
            context = await browser.new_context(viewport={'width': 375, 'height': 812})
            page = await context.new_page()
            await login(page)
            await context.storage_state(path=str(AUTH_FILE)) # Fix: Ensure path is a string
        
        asyncio.create_task(fb_universal_popup_dismissal(page, monitor_forever=True))

        # 3. Process each day's predictions
        for target_date, day_predictions in predictions_by_date.items():
            print(f"\n--- Booking for Date: {target_date} ---")
            
            # Navigate to the correct day's schedule
            target_dt = dt.strptime(target_date, "%d.%m.%Y")
            day_of_week = (target_dt.weekday() + 1) % 7
            base_url = f"https://www.football.com/ng/m/sport/football/?sort=2&tab=Matches&time={day_of_week}"
            await page.goto(base_url, timeout=180000)
            await page.wait_for_load_state('networkidle', timeout=300000)

            # Harvest and Map
            all_site_matches = await extract_all_matches_via_expansion(page, target_date)
            mapped_matches = await map_matches_with_gemini(day_predictions, all_site_matches)

            # Place bets
            selected_bets = 0
            processed_urls = set()
            for match_id, match_url in mapped_matches.items():
                if not match_url or match_url in processed_urls: continue
                
                found_pred = next((p for p in day_predictions if str(p.get('fixture_id', '')).strip() == str(match_id).strip()), None)
                if not found_pred or found_pred['prediction'] == 'SKIP': continue

                print(f"[Match Found] {found_pred['home_team']} vs {found_pred['away_team']}")
                processed_urls.add(match_url)

                try:
                    await page.goto(match_url, wait_until='domcontentloaded', timeout=180000)
                    frame = await get_main_frame(page)
                    if not frame: continue

                    count_before = await get_bet_slip_count(page)
                    all_markets = await extract_all_markets(page) # Changed frame to page
                    btn_selector = await choose_best_bet_with_gemini(all_markets, found_pred, page)
                    
                    if btn_selector:
                        await frame.locator(btn_selector).click(timeout=5000)
                        await asyncio.sleep(1)

                        count_after = count_before
                        for _ in range(5): # Retry check 
                            count_after = await get_bet_slip_count(page)
                            if count_after > count_before: break
                            await asyncio.sleep(1)
                        
                        if count_after > count_before:
                            selected_bets += 1
                            print(f"    [Success] Bet added. Slip count: {count_before} -> {count_after}")
                            update_prediction_status(match_id, target_date, 'booked')
                        else:
                            print(f"    [Error] Clicked, but counter didn't increase.")
                            update_prediction_status(match_id, target_date, 'dropped')
                    else:
                        print("    [Skip] Strategy could not identify a valid button.")
                        update_prediction_status(match_id, target_date, 'dropped')
                except Exception as e:
                    print(f"    [Error] Match processing failed: {e}")
                    update_prediction_status(match_id, target_date, 'dropped')
                    await log_error_state(page, f"process_bet_task_{match_id}", e)

            if selected_bets > 0:
                print(f"[Betting] Finalizing accumulator with {selected_bets} bets for {target_date}...")
                # Add logic here to navigate to bet slip and place the final bet
            else:
                print(f"[Info] No bets selected for {target_date}.")

    except Exception as e:
        print(f"[FATAL BOOKING ERROR] {e}")
        if page: await log_error_state(page, "football_com_fatal", e)
    finally:
        if page and not page.is_closed(): await page.close()
        if context: await context.close()
