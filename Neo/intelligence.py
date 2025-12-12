# intelligence.py

import asyncio
import base64
import json
import os
import re
from dotenv import load_dotenv
from pathlib import Path
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import (
    GenerationConfig,
    HarmBlockThreshold,
    HarmCategory,
)
from playwright.async_api import Page

# Import from new helper structure
from Helpers.utils import LOG_DIR
from Helpers.Site_Helpers.page_logger import log_page_html
from Helpers.Neo_Helpers.Managers.api_key_manager import gemini_api_call_with_rotation, key_manager
from Helpers.Neo_Helpers.Managers.db_manager import load_knowledge, save_knowledge, knowledge_db
from Helpers.Neo_Helpers.Managers.vision_manager import get_visual_ui_analysis


# --- The AI Mapper Logic ---


def clean_json_response(text: str) -> str:
    """
    Cleans Gemini response to ensure valid JSON parsing.
    Removes Markdown fences and attempts to fix common escape issues.
    """
    # 1. Remove Markdown code blocks
    text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```$", "", text, flags=re.MULTILINE)

    # 2. Fix simple invalid escapes (e.g., \d in strings -> \\d)
    # This matches a backslash NOT followed by a valid escape char (", \, /, b, f, n, r, t, u)
    # and doubles it. This prevents "Invalid \escape" errors.
    text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)

    return text.strip()





async def analyze_page_and_update_selectors(
    page: Page,
    context_key: str,
    force_refresh: bool = False,
    info: Optional[str] = None,
):
    """
    The "memory creator" for Leo. This function is the core of the auto-healing mechanism.
    1. Checks if selectors exist. If they do and not force_refresh, skips.
    2. Captures Visual UI Inventory (The What).
    3. Captures HTML (The How).
    4. Maps Visuals to HTML Selectors with STANDARDIZED KEYS for critical items.
    """
    Focus = info
    # --- INTELLIGENT SKIP LOGIC ---
    if not force_refresh and context_key in knowledge_db and knowledge_db[context_key]:
        print(f"    [AI INTEL] Selectors found for '{context_key}'. Skipping AI analysis.")
        return

    print(
        f"    [AI INTEL] Starting Full Discovery for context: '{context_key}' (Force: {force_refresh})..."
    )

    print(f"    [AI INTEL] Capturing page state for '{context_key}'...")
    await log_page_html(page, context_key)

    # Step 1: Get Visual Context
    ui_visual_context = await get_visual_ui_analysis(page, context_key) # This now uses the screenshot taken above
    if not ui_visual_context:
        return

    PAGE_LOG_DIR = LOG_DIR / "Page"
    files = list(PAGE_LOG_DIR.glob(f"*{context_key}.html"))
    if not files:
        print(f"    [AI INTEL ERROR] No HTML file found for context: {context_key}")
        return

    html_file = max(files, key=os.path.getmtime)
    print(f"    [AI INTEL] Using logged HTML: {html_file.name}")

    try:
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception as e:
        print(f"    [AI INTEL ERROR] Failed to load HTML: {e}")
        return

    # Optional: Minimal clean to save tokens
    html_content = re.sub(
        r"<script.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE
    )
    html_content = re.sub(
        r"<style.*?</style>", "", html_content, flags=re.DOTALL | re.IGNORECASE
    )
    html_content = html_content[:100000]  # Truncate if too long

    # Step 3: Map Visuals to HTML (with Extraction Rules)
    print("    [AI INTEL] Mapping UI Elements to HTML Selectors...")
    prompt = f"""
    You are an elite front-end reverse-engineer tasked with mapping every visible UI element from a screenshot to a precise, working CSS selector using the provided HTML.
    You have two responsibilities:
    1. Map critical Flashscore/Football.com elements using EXACT predefined keys
    2. Map all other visible elements using a rigid, predictable naming convention
    CRITICAL RULES — FOLLOW EXACTLY:
    ### 1. MANDATORY CORE ELEMENTS (Use These Exact Keys If Present)
    Important: {Focus}
    Use these keys EXACTLY as written if the element exists on the page:
    {{
    "sport_container": "Main container holding all football matches and leagues",
    "league_header": "Header row containing country and league name",
    "match_rows": "Selector that matches ALL individual match rows",
    "match_row_home_team_name": "Element inside a match row containing the home team name",
    "match_row_away_team_name": "Element inside a match row containing the away team name",
    "match_row_time": "Element inside a match row showing kick-off time",
    "next_day_button": "Button or icon that navigates to tomorrow's fixtures",
    "prev_day_button": "Button or icon that navigates to previous day",
    "league_category": "Country name (e.g., ENGLAND) in league header",
    "league_title_link": "Clickable league name link in header",
    "event_row_link": "Anchor tag inside match row linking to match detail page",
    "cookie_accept_button": "Primary accept button in cookie/privacy banner",
    "tab_live": "Live matches tab",
    "tab_finished": "Finished matches tab",
    "tab_scheduled": "Scheduled/upcoming matches tab",
    "draw": "a league_header text to show that a league has a draw table. a.headerLeague__link span:contains("Draw")",
    # =========================================================================
    # MATCH HEADER (METADATA)
    # =========================================================================
    "meta_breadcrumb_country": "Country name in breadcrumb (e.g. Armenia), found with class '.tournamentHeader__country'",
    "meta_breadcrumb_league": "League name in breadcrumb (e.g. Premier League), found with class '.tournamentHeader__league a'",
    "meta_match_time": "Exact match start time/date, found with class '.duelParticipant__startTime'",
    "meta_match_status": "Status text (e.g., Finished, 1st Half), found with class '.fixedHeaderDuel__detailStatus'",
    
    # --- Home Team Header ---
    "header_home_participant": "Container for home team info, found with class '.duelParticipant__home'",
    "header_home_image": "Home team logo image, found with class '.duelParticipant__home .participant__image'",
    "header_home_name": "Home team text name, found with class '.duelParticipant__home .participant__participantName'",
    
    # --- Away Team Header ---
    "header_away_participant": "Container for away team info, found with class '.duelParticipant__away'",
    "header_away_image": "Away team logo image, found with class '.duelParticipant__away .participant__image'",
    "header_away_name": "Away team text name, found with class '.duelParticipant__away .participant__participantName'",
    
    # --- Score Board ---
    "header_score_wrapper": "Container for the big score display, found with class '.detailScore__wrapper'",
    "header_score_home": "Home team score, found with class '.detailScore__wrapper span:nth-child(1)'",
    "header_score_divider": "The hyphen or 'vs' between scores, found with class '.detailScore__divider'",
    "header_score_away": "Away team score, found with class '.detailScore__wrapper span:nth-child(3)'",

    # =========================================================================
    # NAVIGATION TABS
    # =========================================================================
    "nav_tab_summary": "Summary tab link, found via 'a[href=\"#match-summary\"]'",
    "nav_tab_news": "News tab link, found via 'a[href=\"#news\"]'",
    "nav_tab_odds": "Odds tab link, found via 'a[href=\"#odds-comparison\"]'",
    "nav_tab_h2h": "Head-to-Head tab link, found via 'a[href=\"#h2h\"]'",
    "nav_tab_standings": "Standings tab link, found via 'a[href=\"#standings\"]'",
    "nav_tab_photos": "Photos/Media tab link, found via 'a[href=\"#match-photos\"]'",

    # =========================================================================
    # H2H TAB CONTENT (Deep Dive)
    # =========================================================================
    # --- Filters ---
    "h2h_filter_container": "Container for Overall/Home/Away buttons, found with class '.h2h__filter'",
    "h2h_btn_overall": "Filter button 'Overall', found via '.h2h__filter div:nth-of-type(1)'",
    "h2h_btn_home": "Filter button 'Home', found via '.h2h__filter div:nth-of-type(2)'",
    "h2h_btn_away": "Filter button 'Away', found via '.h2h__filter div:nth-of-type(3)'",

    # --- Sections ---
    "h2h_section_home_last_5": "Container for Home Team's last matches, found with class '.h2h__section:nth-of-type(1)'",
    "h2h_section_away_last_5": "Container for Away Team's last matches, found with class '.h2h__section:nth-of-type(2)'",
    "h2h_section_mutual": "Container for Head-to-Head mutual matches, found with class '.h2h__section:nth-of-type(3)'",
    "h2h_section_title": "The title text (e.g., 'LAST MATCHES: PYUNIK YEREVAN'), found with class '.h2h__sectionHeader'",

    # --- Rows (Iterate these) ---
    "h2h_row_general": "Common selector for ANY match row in H2H, found with class '.h2h__row'",
    "h2h_row_link": "the h2h_row_general link, which is the match",
    "h2h_row_date": "Date of past match, found with class '.h2h__date'",
    "h2h_row_league_icon": "Competition icon/tooltip, found with class '.h2h__eventIcon'",
    "h2h_row_participant_home": "Home team name in history row, found with class '.h2h__homeParticipant'",
    "h2h_row_participant_away": "Away team name in history row, found with class '.h2h__awayParticipant'",
    "h2h_row_score_home": "Home score in history row, found via '.h2h__result span:nth-child(1)'",
    "h2h_row_score_away": "Away score in history row, found via '.h2h__result span:nth-child(2)'",
    "h2h_row_win_marker": "Highlighted bold text indicating the winner, found with class '.fontBold'",
    
    # --- Badges ---
    "h2h_badge_win": "Green 'W' icon, found with class '.h2h__icon--win' or title='Win'",
    "h2h_badge_draw": "Orange 'D' icon, found with class '.h2h__icon--draw' or title='Draw'",
    "h2h_badge_loss": "Red 'L' icon, found with class '.h2h__icon--lost' or title='Loss'",

    # --- Interaction ---
    "h2h_show_more_home": "Button to load more home history, found via '.h2h__section:nth-of-type(1) .showMore'",
    "h2h_show_more_away": "Button to load more away history, found via '.h2h__section:nth-of-type(2) .showMore'",
    "h2h_show_more_mutual": "Button to load more mutual history, found via '.h2h__section:nth-of-type(3) .showMore'",

    "standings_table": "Main standings table container that holds all rows",
    "standings_table_body": "Table body with team rows",
    "standings_header_row": "Table header row with column titles",
    "standings_row": "Individual team row (repeatable)",
    "standings_header_cell_rank": "Position/rank column header",
    "standings_header_cell_team": "Team name column header",
    "standings_header_cell_played": "Matches played column header",
    "standings_header_cell_points": "Points column header",
    "standings_col_rank": "Team's position number",
    "standings_col_team_name": "Team name (clickable)",
    "standings_col_team_link": "Link to team page",
    "standings_col_team_logo": "Team logo image",
    "standings_col_matches_played": "MP/GP column value",
    "standings_col_wins": "Wins (W) column",
    "standings_col_draws": "Draws (D) column",
    "standings_col_losses": "Losses (L) column",
    "standings_col_goals": "Goals column (could be GF:GA or combined)",
    "standings_col_goal_diff": "Goal difference (±GD) column",
    "standings_col_points": "Total points",
    "standings_col_form": "Last 5 matches visual results",
    "standings_form_badge_1": "Most recent match result",
    "standings_form_badge_2": "2nd most recent match",
    "standings_form_badge_3": "3rd most recent match",
    "standings_form_badge_4": "4th most recent match",
    "standings_form_badge_5": "5th most recent match (oldest)",
    "standings_form_icon_win": "Win indicator (usually green W)",
    "standings_form_icon_draw": "Draw indicator (orange D)",
    "standings_form_icon_loss": "Loss indicator (red L)",
    "standings_filter_overall": "Overall standings filter",
    "standings_filter_home": "Home form standings filter",
    "standings_filter_away": "Away form standings filter",
    "standings_legend_container": "Legend explaining colors/symbols",
    "standings_qualification_row": "Row styled for qualification",
    "standings_relegation_row": "Row styled for relegation",
    
    # --- Tooltips/Popups ---
    "tooltip_container": "General container for popups, found with class '[data-testid=\"wcl-tooltip\"]'",
    "tooltip_close_btn": "Close/Understand button, found via '[data-testid=\"wcl-tooltip-actionButton\"]'"

    # fb_login_page keys
    "top_right_login": "official logical method",
    "center_text_mobile_number_placeholder": "Input field placeholder for entering mobile number",
    "center_text_password_placeholder": "Input field placeholder for entering password",
    "bottom_button_text_login": "Primary login button text at the bottom",
    "center_link_forgot_password": "Link to recover forgotten password",
    "center_text_mobile_country_code": "Text displaying the mobile country code",
    "top_container_nav_bar": "Top navigation bar container",
    "top_icon_back": "Back icon in the top navigation bar",
    "top_icon_close": "Close icon for popup. the close icon is usually at the top right corner.",
    "top_tab_register": "Register tab in the navigation menu",
    "top_tab_login": "Login tab in the navigation menu",
    # fb_main_page keys
    "navbar_balance": "Element showing user balance in the navbar",
    "currency": "Element showing currency class in the navbar_balance",
    "search_button": "Search button/icon in the main page",
    "search_input": "Search input field",
    "bet_slip_fab_icon_button": "Floating action button (FAB) icon/button to open the bet slip section from anywhere on the match page",
    # fb_schedule_page keys
    "pre_match_list_league_container": "Main container holding all pre_match football leagues and matches",
    "league_title_wrapper": "Header row containing country, league name and number of matches in pre_match list",
    "league_title_link": "Clickable league name link in league_title_wrapper",
    "league_wrapper_collapsed": "Same as just 'league_wrapper'(when league_title_wrapper is clicked). Contains the matches for the given league",
    "league_row": "Contains the league_title_wrapper and the league_wrapper_collapsed, which is make up a league. So the league_row is one league",
    "match_card": "Selector with each match details (home team, away team, date, time, league name(and url), and the match page url) in pre_match list",
    "match_card_link": "Anchor tag inside match_card linking to match detail page",
    "match_region_league_name": "Selector with the match region and league name (e.g England - Premier League)",
    "match_card_home_team": "Element inside a match_card containing the home team name",
    "match_card_away_team": "Element inside a match_card containing the away team name",
    "match_card_date": "Element inside a match_card showing match date",
    "match_card_time": "Element inside a match_card showing kick_off time",
    "match_card_league_link": "Clickable href of region-league name in match_card(e.g International Clubs - UEFA Champions League)",
    "match_url": "The href link of the match_card to the match detail page ",
    "bet_slip_fab_icon_button": "Floating action button (FAB) icon/button to open the bet slip section from anywhere on the match page",
    # fb_match_page keys
    "tooltip_icon_close": "tooltip in the top right side of the match page",
    "dialog_container": "popup dialog in the match page",
    "dialog_container_wrapper": "dialog_container that prevents inactive in on the page when the dialog_container appears",
    "intro_dialog": "body of the dialog_container in the match page",
    "intro_dialog_btn": "intro_dialog button for 'Next' and 'Got it'",
    "match_smart_picks_container": "Container for match football.com AI smart picks section",
    "match_smart_picks_dropdown": "Dropdown to reveal different smart pick analysis options",
    "smart_pick_item": "Selector for each individual smart pick item in the smart picks section",
    "match_market_category_tab": "container for market category tabs (e.g., 'All', 'Main', 'Early wins', 'Corners', 'Goals', etc.)",
    "match_market_search_icon_button": "Search icon/button to search for specific betting markets available for the match",
    "match_market_search_input": "Input field to type in betting market search terms available for the match",
    "match_market_details_container": "Container that holds a betting market details for the match. This is the main wrapper for a market group (e.g., 1X2, Over/Under). Clicking on a market header expands it to show all available betting options.",
    "match_market_name": "Element showing the name/title of a specific betting market for the match (e.g Home to win either half, Away to win either half, etc.)",
    "match_market_info_tooltip": "Tooltip icon/button that shows additional information about a specific betting market when clicked",
    "match_market_info_tooltip_text": "The text content inside the tooltip that provides additional information about a specific betting market",
    "match_market_tooltip_ok_button": "OK button inside the betting market tooltip to close it",
    "match_market_table": "Table inside a betting market that lists all available betting options along with their odds",
    "match_market_table_header": "Header row of the betting market table that contains column titles (e.g., 'outcome(value)', 'over', 'under')",
    "match_market_table_row": "Row inside the betting market table representing a single betting option(1.5(in the outcome column), 1.85(in the over column), 1.95(in the under column), etc.)",
    "match_market_odds_button": "The clickable element representing a single betting outcome (e.g., 'Home', 'Over 2.5') that displays the odds. This element should be unique for each outcome.",
    "bet_slip_container": "Container for the bet slip section that shows selected bets and allows users to manage their bets",
    "bet_slip_predicitions_counter": "Text Element inside the bet slip that displays the number of predictions/bets added to the slip. Could be class "real-theme" and "is-zero real-theme(whenthe counter is zero)",
    "bet_slip_remove_all_button": "Button inside the bet slip that allows users to clear all selected bets from the slip",
    "bet_slip_single_bet_tab": "Tab inside the bet slip for placing single bets",
    "bet_slip_multiple_bet_tab": "Tab inside the bet slip for placing multiple bets (accumulators)",
    "bet_slip_system_bet_tab": "Tab inside the bet slip for placing system bets",
    "bet_slip_outcome_list": "List inside the bet slip that shows all selected betting outcomes",
    "bet_slip_outcome_item": "Item inside the bet slip outcome list representing a single selected betting outcome",
    "bet_slip_outcome_remove_button": "Button inside a bet slip outcome item that allows users to remove that specific outcome from the bet slip",
    "bet_slip_outcome_details": "Element inside a bet slip outcome item that displays details about the selected betting outcome (e.g., market name, outcome, odds, match teams etc.). clicking on this element usually navigates to the match page.",
    "match_url": "The URL link to the match detail page from the bet slip outcome details",
    "navbar_balance": "Element showing user currency and balance in the bet slip section",
    "real_match_button": "Button that switches from virtual match to real match all with real money for the selected bet_slip_outcome_item in the bet slip section",
    "stake_input_field_button": "Input field/button to enter stake amount for the selected bet_slip_outcome_item in the bet slip section",
    "stake_input_keypad_button": "Keypad button inside the stake input field to enter stake amount for the selected bet_slip_outcome_item in the bet slip section",
    "keypad_1": "Keypad button for digit '1'",
    "keypad_2": "Keypad button for digit '2'",
    "keypad_3": "Keypad button for digit '3'",
    "keypad_4": "Keypad button for digit '4'",
    "keypad_5": "Keypad button for digit '5'",
    "keypad_6": "Keypad button for digit '6'",
    "keypad_7": "Keypad button for digit '7'",
    "keypad_8": "Keypad button for digit '8'",
    "keypad_9": "Keypad button for digit '9'",
    "keypad_0": "Keypad button for digit '0'",
    "keypad_dot": "Keypad button for decimal point",
    "keypad_clear": "Keypad button to clear the entered stake amount",
    "keypad_done": "Keypad button to confirm the entered stake amount",
    "bet_slip_total_odds": "Element showing total odds for all selected bets in the bet slip",
    "bet_slip_potential_win": "Element showing potential winnings for the entered stake amount in the bet slip",
    "bet_slip_early_win_checkbox": "Checkbox in the bet slip to enable or disable early win cash out option",
    "bet_slip_one_cut_checkbox": "Checkbox in the bet slip to enable or disable one cut option",
    "bet_slip_cut_one_checkbox": "Checkbox in the bet slip to enable or disable cut one option",
    "bet_slip_accept_odds_change_button": "Button in the bet slip to accept any odds changes before placing the bet",
    "bet_slip_book_bet_button": "Button to reveal a bottom sheet/modal get the betslip shareable link, code, and image",
    "bet_code": "Element showing the unique bet code for sharing or retrieving the bet slip",
    "bet_link": "Element showing the unique bet link URL for sharing or retrieving the bet slip",
    "bet_image": "Element showing the bet slip image/graphic for sharing or saving",
    "place_bet_button": "Button to confirm and place the bet with the entered stake amount",
    "bet_slip_fab_icon_button": "Floating action button (FAB) icon/button to open the bet slip section from anywhere on the match page",
    # fb_withdraw_page keys
    "withdrawable_balance": "Element showing user withdrawable balance on the withdraw page",
    "withdraw_input_amount_field": "Input field to enter amount to withdraw on the withdraw page",
    "withdraw_button_submit": "Button to submit the withdrawal request on the withdraw page",
    "withdrawal_pin_field": "four digits input box for withdrawal pin",
    "keypad_1": "Keypad button for digit '1'",
    "keypad_2": "Keypad button for digit '2'",
    "keypad_3": "Keypad button for digit '3'",
    "keypad_4": "Keypad button for digit '4'",
    "keypad_5": "Keypad button for digit '5'",
    "keypad_6": "Keypad button for digit '6'",
    "keypad_7": "Keypad button for digit '7'",
    "keypad_8": "Keypad button for digit '8'",
    "keypad_9": "Keypad button for digit '9'",
    "keypad_0": "Keypad button for digit '0'",
    "keypad_dot": "Keypad button for decimal point",
    "keypad_clear": "Keypad button to clear the entered withdrawal pin",
    "keypad_done": "Keypad button to confirm the entered withdrawal pin",
    }}

    ### 2. ALL OTHER ELEMENTS → Strict Naming Convention
    Pattern: <location>*<type>*<content_or_purpose>
    Examples: top_button_login, header_icon_search, center_text_premier_league
    ### 3. Selector Quality Rules
    - Return ONLY a valid JSON object: {{"key": "selector"}}
    - Prefer: IDs > data-* attributes > unique classes > class combinations
    - FORBIDDEN: Do not use the non-standard `:contains()` pseudo-class. Do not use selectors containing `skeleton` or `ska__`. Use standard CSS. Avoid long chains (>4 levels) and overly specific text.
    - Must match exactly what is visible in the screenshot
    - For repeated elements (e.g., match rows), selector must match ALL instances
    - Lastly, if an element is not present in the html, omit that key from the output. We now have Fooball.com elements as well.
    
    Valid Selectors: The majority are standard CSS selectors, utilizing valid syntax such as class names (e.g., .m-input-wrapper), attribute selectors (e.g., [placeholder="Mobile Number"]), pseudo-classes (e.g., :not([style*="display: none"])), combinators (e.g., >, descendant spaces), and structural pseudo-classes (e.g., :nth-child(1)). These are compatible with Playwright and Chromium's querySelectorAll() implementation. Examples include:
    "div.m-input-wrapper.mobile-number input[placeholder=\\"Mobile Number\\"]"
    ".m-featured-match-card-container .featured-match-top a.tournament"
    "div.categories-container > div.active.category"

    Invalid or Non-Standard Selectors: A subset employs the :contains("text") pseudo-class, which is not part of standard CSS (it originated in jQuery/Sizzle but was never adopted in CSS specifications). Playwright does not support :contains as a custom extension; instead, it offers :text="text" or :has-text("text") for text-based matching. Using :contains will likely result in a selector error or failure to locate elements. Affected entries include:
    "div.categories h1.tournament-name:contains(\\"Championship\\")" (and similar variants for other leagues like "Liga MX, Apertura", "Brasileiro Serie A", etc.).
    These should be refactored to use Playwright's text selectors (e.g., text="Championship") or combined selectors (e.g., div.categories h1.tournament-name:has-text("Championship") if exact matching is needed).

    Edge Cases with Potential Issues:
    Selectors using :has() (e.g., "div.categories > div.category:has(img[src*="2e911d8614a00112a34f431c9477795.png"])") are valid in CSS Level 4 and supported in recent Chromium versions (Chrome 105+). Playwright, running on up-to-date Chromium, should handle them without issue.
    Attribute substring matches (e.g., [src*="hot-encore"]) are standard and supported.
    No XPath or other non-CSS formats are present, so all are interpreted as CSS by default in Playwright (unless prefixed explicitly).
    
    3. **SELECTOR QUALITY**:
       - Return valid JSON: {{"key": "selector"}}
       - Prefer IDs > Classes > Attributes.
       - AVOID :contains() (use :has-text() if needed, or better yet simple CSS).
       - NO MARKDOWN in response.
    """

    prompt_tail = f"""
    ### INPUT
    --- VISUAL INVENTORY ---
    {ui_visual_context}
    --- CLEANED HTML SOURCE ---
    {html_content}
    Return ONLY the JSON mapping. No explanations. No markdown.
    """

    full_prompt = prompt + prompt_tail

    try:
        response = await gemini_api_call_with_rotation(
            full_prompt, # type: ignore
            generation_config=GenerationConfig(response_mime_type="application/json")  # type: ignore
        )
        # Fix for JSON Decode Errors
        cleaned_json = clean_json_response(response.text)
        new_selectors = json.loads(cleaned_json)

        knowledge_db[context_key] = new_selectors
        save_knowledge()
        print(f"    [AI INTEL] Successfully mapped {len(new_selectors)} elements.")
    except Exception as e:
        print(f"    [AI INTEL ERROR] Failed to generate selectors map: {e}")
        return

    return None


async def attempt_visual_recovery(page: Page, context_name: str) -> bool:
    """
    Emergency AI Recovery Mechanism.
    1. Takes a screenshot of the 'stuck' state.
    2. Sends it to Gemini to identify blocking overlays (Ads, Popups, Modals).
    3. Asks for the CSS selector to click (Close, X, No Thanks).
    4. Executes the click.
    Returns True if a recovery action was taken.
    """
    print(f"    [AI RECOVERY] Analyzing screen for blockers/popups in context: {context_name}...")
    await analyze_page_and_update_selectors(page, context_name)
    # 1. Capture the "Crime Scene"
    try:
        screenshot_bytes = await page.screenshot(full_page=False)  # Viewport only is better for popups
    except Exception as e:
        print(f"    [AI RECOVERY] Could not capture screenshot: {e}")
        return False

    # 2. Ask Gemini for the Solution
    prompt = """
    Analyze this screenshot for any blocking elements like:
    - Pop-up ads or Banners
    - "Install App" modals
    - "Free Bet" notifications
    - Onboarding/Tutorial overlays (e.g. "Next", "Skip", "Got it")
    - Cookie/GDPR overlays

    If a blocking element exists, identify the VALID CSS selector for the button to DISMISS or CLOSE it.
    
    IMPORTANT: 
    1. Return STANDARD CSS SELECTORS only (e.g., div.close, button[aria-label='Close']). 
    2. DO NOT use jQuery extensions like :contains() or :has-text(). 
    3. If the button has specific text (e.g. "Next", "Skip"), include that text in the 'button_text' field of the JSON.

    Return a pure JSON object:
    {{
        "blocker_detected": true/false,
        "description": "Short description of the popup",
        "action_selector": "css_selector",
        "button_text": "Text inside the button if available (e.g. Next, Skip)"
    }}
    """

    try:
        response = await gemini_api_call_with_rotation(
            [prompt, {"mime_type": "image/png", "data": screenshot_bytes}], # type: ignore
            generation_config=GenerationConfig(response_mime_type="application/json")  # type: ignore
        )
        cleaned_json = clean_json_response(response.text)
        result = json.loads(cleaned_json)

        if result.get("blocker_detected"):
            selector = result.get("action_selector")
            btn_text = result.get("button_text")
            desc = result.get("description")
            print(f"    [AI RECOVERY] Blocker Detected: {desc}")

            # 3. Execute the Fix
            clicked = False

            # Strategy A: Selector from AI
            if selector:
                print(f"    [AI RECOVERY] Trying CSS selector: {selector}")
                try:
                    if await page.locator(selector).count() > 0:
                        await page.click(selector, timeout=2000)
                        clicked = True
                except:
                    pass

            # Strategy B: Text Fallback (Smart Recovery)
            if not clicked and btn_text:
                print(f"    [AI RECOVERY] Selector failed. Trying text match: '{btn_text}'")
                try:
                    # Look for button-like elements with this text
                    await page.get_by_text(btn_text, exact=False).first.click(timeout=2000)
                    clicked = True
                except:
                    pass

            if clicked:
                print("    [AI RECOVERY] Click successful. Waiting for UI to settle...")
                await asyncio.sleep(2)
                return True
            else:
                print("    [AI RECOVERY] Failed to dismiss popup. No working selector or text found.")
        else:
            print("    [AI RECOVERY] No obvious blockers detected by AI.")

    except Exception as e:
        print(f"    [AI RECOVERY ERROR] {e}")

    return False


def get_selector(context: str, element_key: str) -> str:
    """Legacy synchronous accessor (does not auto-heal)."""
    return knowledge_db.get(context, {}).get(element_key, "")


async def get_selector_auto(page: Page, context_key: str, element_key: str) -> str:
    """
    SMART ACCESSOR:
    1. Checks if selector exists in DB.
    2. Validates if selector is present on the current page.
    3. If missing or invalid, AUTOMATICALLY triggers AI re-analysis and returns fresh selector.
    """
    # 1. Quick Lookup
    selector = knowledge_db.get(context_key, {}).get(element_key)

    # 2. Validation
    is_valid = False
    if selector:
        # --- NEW: Wait up to 2 minutes for the selector to be attached to the DOM ---
        # This prevents premature auto-healing due to network lag or slow rendering.
        #print(f"    [Selector Validate] Waiting for '{element_key}' ('{selector}')...")
        try:
            # Use wait_for_selector which is more robust for this check.
            # 'attached' means it's in the DOM, not necessarily visible.
            await page.wait_for_selector(selector, state='attached', timeout=120000) # 2 minutes
            is_valid = True
            #print(f"    [Selector Validate] ✓ Found '{element_key}'.")
        except Exception as e:
            print(f"    [Selector Stale] '{element_key}' ('{selector}') not found after 2 min wait.")
            is_valid = False

    # 3. Auto-Healing
    if not is_valid:
        print(
            f"    [Auto-Heal] Selector '{element_key}' in '{context_key}' invalid/missing. Initiating AI repair..."
        )
        info = f"Selector '{element_key}' in '{context_key}' invalid/missing."
        # Run AI Analysis (which now captures its own snapshot)
        await analyze_page_and_update_selectors(page, context_key, force_refresh=True, info=info) # This will now take a fresh screenshot

        # C. Re-fetch
        selector = knowledge_db.get(context_key, {}).get(element_key)

        if selector:
            print(f"    [Auto-Heal Success] New selector for '{element_key}': {selector}")
        else:
            print(f"    [Auto-Heal Failed] AI could not find '{element_key}' even after refresh.")

    result = selector or ""
    return str(result)


async def extract_league_data(
    page: Page, context_key: str = "home_page"
) -> Dict[str, List[str]]:
    selectors = knowledge_db.get(context_key, {})
    if not selectors:
        return {"leagues": []}

    required = ["sport_container", "league_header", "match_rows"]
    if not all(k in selectors for k in required):
        return {"leagues": []}

    try:
        data = await page.evaluate(
            """(selectors) => {
            const container = document.querySelector(selectors.sport_container);
            if (!container) return { leagues: [] };

            const results = [];
            let currentLeagueStr = "";
            let currentMatches = [];

            const getText = (parent, sel) => {
                if (!sel) return "";
                const el = parent.querySelector(sel);
                return el ? el.innerText.trim() : "";
            };

            const children = Array.from(container.children);
            const flushCurrentLeague = () => {
                if (currentLeagueStr) {
                    const fullString = currentLeagueStr + (currentMatches.length ? ', ' + currentMatches.join(', ') : '');
                    results.push(fullString);
                }
            };

            children.forEach(el => {
                let header = null;
                if (el.matches(selectors.league_header)) header = el;
                else if (el.querySelector(selectors.league_header)) header = el.querySelector(selectors.league_header);

                if (header) {
                    flushCurrentLeague();
                    const country = getText(header, selectors.league_category) || "Unknown";
                    const name = getText(header, selectors.league_title_link) || "League";
                    const linkEl = header.querySelector(selectors.league_title_link);
                    const href = linkEl ? linkEl.href : "";

                    currentLeagueStr = `${country}: ${name}, ${href}`;
                    currentMatches = [];
                }
                else if (el.matches(selectors.match_rows)) {
                    if (currentLeagueStr) {
                        const linkEl = selectors.event_row_link ?
                                       el.querySelector(selectors.event_row_link) :
                                       el.querySelector('a');
                        if (linkEl && linkEl.href) currentMatches.push(linkEl.href);
                    }
                }
            });

            flushCurrentLeague();
            return { leagues: results };
        }""",
            selectors,
        )

        return data

    except Exception as e:
        print(f"    [EXTRACT ERROR] Failed to extract data: {e}")
        return {"leagues": []}


async def fb_universal_popup_dismissal(
    page: Page,
    context: str = "fb_generic",
    html: Optional[str] = None,
    monitor_interval: int = 0,
) -> bool:
    """
    Universal pop-up dismissal with HTML analysis, pattern detection,
    overlay visibility check, multi-click handling, and Gemini fallback.
    
    Args:
        page: Playwright Page object
        context: Page context for selector lookup (e.g., "fb_login_page")
        html: Optional HTML content (auto-fetched if None)
        monitor_interval: Seconds between checks (0 = single run)
    
    Returns:
        bool: True if pop-up was dismissed, False otherwise
    """

    async def single_dismiss_attempt() -> bool:
        try:
            # Step 1: Fetch HTML if not provided
            if html is None:
                html_content = await page.content()
            else:
                html_content = html

            # Step 2: Detect known pop-up patterns in HTML
            patterns = {
                "overlay_classes": [
                    "dialog-mask",
                    "modal-backdrop",
                    "overlay",
                    "mask",
                    "un-op-70%",
                    "un-h-100vh",
                    "backdrop",
                    "popup-overlay",
                ],
                "popup_wrappers": [
                    "m-popOver-wrapper",
                    "popup-hint",
                    "modal-dialog",
                    "tooltip",
                    "popover",
                    "dialog-container",
                ],
                "close_selectors": [
                    "svg.close-circle-icon",
                    "button.close",
                    '[data-dismiss="modal"]',
                    'button:has-text("Close")',
                ],
                "multi_step_indicators": [
                    "Next",
                    "Got it",
                    "Step",
                    "of",
                    "intro",
                    "guide",
                    "tour",
                    "Continue",
                ],
            }

            has_overlay = any(p in html_content.lower() for p in patterns["overlay_classes"])
            has_popup = any(p in html_content.lower() for p in patterns["popup_wrappers"])
            potential_multi = any(ind in html_content for ind in patterns["multi_step_indicators"])

            if not (has_overlay or has_popup):
                print("    [AI Pop-up] No pop-up patterns detected (skipped)")
                return False

            print(
                f"    [AI Pop-up] Detected: Overlay={has_overlay}, Popup={has_popup}, Multi={potential_multi}"
            )

            # Step 3: Try AI selector first
            close_sel = await get_selector_auto(page, context, "top_icon_close")
            if not close_sel:
                close_sel = await get_selector_auto(page, context, "notification_popup_close_icon")

            if close_sel:
                close_btn = page.locator(close_sel).first
                if await close_btn.count() > 0 and await close_btn.is_visible(timeout=1500):
                    await close_btn.click(timeout=2000)
                    print("    [AI Pop-up] ✓ Closed via AI selector")
                    await asyncio.sleep(0.8)
                    if potential_multi:
                        print("    [AI Pop-up] Checking multi-step...")
                        return await single_dismiss_attempt()
                    return True

            # Step 4: Fallback selectors (visible-only)
            fallback_selectors = patterns["close_selectors"] + [
                'button:has-text("Next")',
                'button:has-text("Got it")',
                'button:has-text("Dismiss")',
                'button:has-text("Close")',
                'svg[aria-label="Close"]',
                'button[aria-label="Close"]',
            ]

            for sel in fallback_selectors:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible(timeout=1000):
                    await btn.click(timeout=2000)
                    print(f"    [AI Pop-up] ✓ Closed via fallback: {sel}")
                    await asyncio.sleep(0.8)
                    if any(step in sel for step in ["Next", "Got it"]) and potential_multi:
                        print("    [AI Pop-up] Multi-step; continuing...")
                        return await single_dismiss_attempt()
                    return True

            # Step 5: Gemini Vision Fallback
            print("    [AI Pop-up] Using Gemini vision fallback...")

            screenshot_bytes = await page.screenshot(full_page=True, type="png")
            img_data = base64.b64encode(screenshot_bytes).decode("utf-8")

            prompt = f"""
            Analyze this webpage screenshot + HTML for pop-up/modal dismissal.
            IDENTIFY:
            1. Close buttons (X icons, Close buttons)
            2. Next/Continue/Got it buttons (multi-step)
            3. Overlay dismissal areas

            Output STRICT JSON only:

            {{
            "selectors": ["primary_close_selector", "backup_selector"],
            "multi_click": true/false,
            "steps": 1,
            "type": "modal|tooltip|guide|popover|none",
            "reason": "brief explanation"
            }}

            If no pop-up: {{"selectors": [], "multi_click": false, "steps": 0, "type": "none", "reason": "No pop-up"}}

            HTML: {html_content[:4000]}...
            """

            response = await gemini_api_call_with_rotation(
                [prompt, {"inline_data": {"mime_type": "image/png", "data": img_data}}],
                generation_config=GenerationConfig(temperature=0.0, response_mime_type="application/json"),  # type: ignore
                safety_settings={ # type: ignore
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                },
            )

            try:
                if response.text:
                    cleaned_text = clean_json_response(response.text)
                    gemini_output = json.loads(cleaned_text)
                    print(f"    [Gemini] Analysis: {gemini_output}")

                    selectors = gemini_output.get("selectors", [])
                    multi_click = gemini_output.get("multi_click", False)
                    steps = gemini_output.get("steps", 1)

                    if selectors and steps > 0:
                        for i, sel in enumerate(selectors[:steps]):
                            btn = page.locator(sel).first
                            if await btn.count() > 0 and await btn.is_visible(timeout=2000):
                                await btn.click(timeout=3000)
                                print(f"    [AI Pop-up] ✓ Gemini selector {i+1}/{steps}: {sel}")
                                await asyncio.sleep(1.0)
                                if multi_click and i < steps - 1:
                                    print("    [AI Pop-up] Multi-step continuing...")

                        # Update knowledge base
                        if context not in knowledge_db:
                            knowledge_db[context] = {}
                        if selectors:
                            knowledge_db[context]["gemini_popup_close"] = selectors[0]
                            save_knowledge()
                        return True
            except (json.JSONDecodeError, ValueError) as e:
                print(f"    [Gemini] Parse error: {e}")

            print("    [AI Pop-up] No dismissible elements found")
            return False

        except Exception as e:
            print(f"    [AI Pop-up] Attempt failed: {e}")
            return False

    if monitor_interval > 0:
        print(f"    [AI Pop-up] Continuous monitoring every {monitor_interval}s...")
        while True:
            await single_dismiss_attempt()
            await asyncio.sleep(monitor_interval)
    else:
        attempts = 0
        max_attempts = 3
        while attempts < max_attempts:
            if await single_dismiss_attempt():
                return True
            attempts += 1
            await asyncio.sleep(0.5)
        return False
