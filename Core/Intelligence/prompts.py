# prompts.py: prompts.py: Centralized management of AI prompts and element keys.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: get_keys_for_context()

"""
Prompts Module
Centralized storage and management for AI prompts and element keys.
Allows dynamic selection of keys based on context to save tokens and improve accuracy.
"""

from typing import Dict, List, Optional

# --- SHARED ELEMENTS (Used across multiple pages) ---
SHARED_KEYS = {
    "sport_container": "Main container holding all football matches and leagues",
    "league_header": "Header row containing country and league name",
    "match_rows": "Selector that matches ALL individual match rows",
    "cookie_accept_button": "Primary accept button in cookie/privacy banner",
    "top_icon_close": "Close icon for popup",
    "bet_slip_fab_icon_button": "Floating action button (FAB) to open the bet slip",
    "navbar_balance": "Element showing user balance in the navbar",
    "currency": "Currency display element (e.g. NGN, $)",
    "tooltip_container": "General container for popups/tooltips",
    "tooltip_close_btn": "Close/Understand button for tooltips",
}

# --- FLASHSCORE SPECIFIC ---
FLASHSCORE_MATCH_KEYS = {
    "meta_breadcrumb_country": "Country name in breadcrumb",
    "meta_breadcrumb_league": "League name in breadcrumb",
    "meta_match_time": "Exact match start time/date",
    "meta_match_status": "Status text (e.g., Finished, 1st Half)",
    "header_home_name": "Home team text name",
    "header_away_name": "Away team text name",
    "header_score_home": "Home team score",
    "header_score_away": "Away team score",
    "nav_tab_summary": "Summary tab link",
    "nav_tab_odds": "Odds tab link",
    "nav_tab_h2h": "Head-to-Head tab link",
    "nav_tab_standings": "Standings tab link",
}

FLASHSCORE_H2H_KEYS = {
    "h2h_filter_container": "Container for Overall/Home/Away buttons",
    "h2h_btn_overall": "Filter button 'Overall'",
    "h2h_btn_home": "Filter button 'Home'",
    "h2h_btn_away": "Filter button 'Away'",
    "h2h_row_general": "Common selector for ANY match row in H2H",
    "h2h_row_date": "Date of past match",
    "h2h_row_participant_home": "Home team name in history row",
    "h2h_row_participant_away": "Away team name in history row",
    "h2h_row_score_home": "Home score in history row",
    "h2h_row_score_away": "Away score in history row",
}

FLASHSCORE_STANDINGS_KEYS = {
    "standings_table": "The main standings table container",
    "standings_row": "Selector for an individual team row",
    "standings_col_rank": "The rank/position number",
    "standings_col_team_name": "The clickable team name text",
    "standings_col_matches_played": "Matches played count",
    "standings_col_points": "Total points",
    "standings_col_form": "Container for the last 5 match badges",
}

# --- FOOTBALL.COM SPECIFIC ---
FB_LOGIN_KEYS = {
    "top_right_login": "Login button in header",
    "center_input_mobile_number": "Input field for mobile number",
    "center_input_password": "Input field for password",
    "bottom_button_login": "Primary login button at the bottom",
    "top_tab_login": "Login tab in the navigation menu",
}

FB_MAIN_KEYS = {
    "full_schedule_button": "Link to the full schedule page",
    "search_button": "Search button/icon",
    "search_input": "Search input field",
}

FB_SCHEDULE_KEYS = {
    "filter_dropdown_today": "Dropdown button to select date filter (Today, Tomorrow, etc.)",
    "pre_match_list_league_container": "Main container holding all pre_match football leagues",
    "league_title_wrapper": "Header row with country, league name, and count",
    "league_title_link": "Clickable league name link",
    "league_wrapper_collapsed": "Container for matches when league is expanded",
    "league_row": "Single league row containing header and matches",
    "match_card": "Individual match card selector",
    "match_card_link": "Link to match detail page",
    "match_region_league_name": "Text for region and league name",
    "match_card_home_team": "Home team name text",
    "match_card_away_team": "Away team name text",
    "match_card_date": "Match date text",
    "match_card_time": "Kick-off time text",
    "match_url": "The link to the match detail page",
}

FB_MATCH_KEYS = {
    "tooltip_icon_close": "Close icon for tooltips/popups on match page",
    "dialog_container": "Popup dialog container",
    "match_smart_picks_container": "Container for AI smart picks section",
    "match_market_category_tab": "Container for market category tabs (All, Main, etc.)",
    "match_market_search_input": "Input for market search",
    "match_market_details_container": "Wrapper for a market group",
    "match_market_name": "Title of a specific market",
    "match_market_table": "Table containing betting options",
    "match_market_odds_button": "Clickable betting outcome/odds button",
}

FB_SLIP_KEYS = {
    "bet_slip_container": "Container for the bet slip",
    "bet_slip_predicitions_counter": "Number of picks in slip",
    "bet_slip_remove_all_button": "Clear all bets button",
    "bet_slip_outcome_list": "List of selected bets",
    "bet_slip_outcome_item": "Individual bet item in slip",
    "stake_input_field_button": "Input field for stake amount",
    "place_bet_button": "Primary button to place the bet",
    "bet_code": "Shareable bet code text",
    "bet_link": "Shareable bet link text",
}

FB_BETSLIP_KEYS = {
    "bet_slip_container": "Container for the bet slip section",
    "bet_slip_outcome_list": "List containing all selected betting outcomes",
    "bet_slip_outcome_item": "Individual outcome item in the bet slip",
    "bet_slip_outcome_details": "Details of the selected outcome (market, odds, teams)",
    "bet_slip_total_odds": "Element showing total odds for the bet slip",
    "bet_slip_potential_win": "Element showing potential winnings",
    "bet_slip_stake_input": "Input field for the stake amount",
    "place_bet_button": "Main button to confirm and place the bet",
    "bet_code": "Text element showing the final bet code",
    "bet_link": "URL element for the shareable bet link",
}

FB_WITHDRAW_KEYS = {
    "withdrawable_balance": "User withdrawable balance",
    "withdraw_input_amount_field": "Input for withdrawal amount",
    "withdraw_button_submit": "Submit withdrawal button",
    "withdrawal_pin_field": "Input for withdrawal PIN",
}

# --- MAP CONTEXT TO KEYS ---
CONTEXT_MAP = {
    "fb_login_page": [SHARED_KEYS, FB_LOGIN_KEYS],
    "fb_main_page": [SHARED_KEYS, FB_MAIN_KEYS],
    "fb_schedule_page": [SHARED_KEYS, FB_SCHEDULE_KEYS],
    "fb_match_page": [SHARED_KEYS, FB_MATCH_KEYS, FB_SLIP_KEYS],
    "fb_betslip": [SHARED_KEYS, FB_BETSLIP_KEYS],
    "fb_withdraw_page": [SHARED_KEYS, FB_WITHDRAW_KEYS],
    "flashscore_match": [SHARED_KEYS, FLASHSCORE_MATCH_KEYS],
    "flashscore_h2h": [SHARED_KEYS, FLASHSCORE_MATCH_KEYS, FLASHSCORE_H2H_KEYS],
    "flashscore_standings": [SHARED_KEYS, FLASHSCORE_MATCH_KEYS, FLASHSCORE_STANDINGS_KEYS],
}

def get_keys_for_context(context_key: str) -> Dict[str, str]:
    """Dynamically build the keys list based on context"""
    keys = {}
    
    # Try to find exact match
    if context_key in CONTEXT_MAP:
        for partial_map in CONTEXT_MAP[context_key]:
            keys.update(partial_map)
    else:
        # Fallback to shared keys if unknown
        keys.update(SHARED_KEYS)
        
    return keys

# --- PROMPT TEMPLATES ---

BASE_VISUAL_INSTRUCTIONS = """
Analyze this webpage screenshot and provide a pixel-perfect visual inventory of every visible element. 
Examine every UI component, button, text field, and interactive element.

Focus on:
1. LAYOUT & STRUCTURE
2. INTERACTIVE CONTROLS
3. CONTENT ELEMENTS
4. SYSTEM ELEMENTS (Popups, Modals)

Format each element as:
"Element Description: Exact visible text (function if no text)"
Include: position, state, repetition patterns.

Be exhaustive but concise. Here are the elements of interest for this specific page:
"""

BASE_MAPPING_INSTRUCTIONS = """
You are a specialized UI Automation Assistant. Your task is to map logical UI components to their corresponding CSS selectors based on the provided document structure.

CRITICAL RULES:
1. MANDATORY: Use EXACT keys provided in the list below.
2. SELECTOR RULES: Prefer ID > Data Attributes > Unique Class. Avoid brittle paths.
3. DATA AGNOSTIC: Do not include dynamic content (scores, names, dates) in selectors.
4. EFFICIENCY: Keep selectors as simple as possible. Avoid deep nesting.
5. COMPATIBILITY: Standard CSS selectors only. Use :has-text() for Playwright when text is the only unique identifier.

Return ONLY a valid JSON object: {"key": "selector"}
"""

STATE_DISCOVERY_PROMPT = """
You are the navigator for Leo AI. Analyze this HTML content from a webpage.
Your task is to identify the CURRENT STATE of the automation.

HTML CONTENT:
{html_content}

Based on the HTML structure and content, determine:

1. CATEGORY: (e.g., "Login Page", "Match List", "Market Selection", "Blocked by Ad", "Empty State")
2. PURPOSE: What is the primary task a user performs here?
3. MILESTONE: Is there an indicator that we are on the right track? (e.g., "Home Team name in HTML", "Betslip container present")
4. EXITS: List the 3 most important buttons/links to move to a NEW state based on the HTML.

Return ONLY a JSON object:
{{
  "state": "category_name",
  "is_modal": true/false,
  "milestone_found": "description",
  "primary_exit_selector": ".css-selector"
}}
"""

RECOVERY_PROMPT = """
I am stuck on this webpage. There might be a popup, ad, or modal blocking my interaction.
Analyze this HTML content and identify potential blocking elements.

HTML CONTENT:
{html_content}

Look for elements that commonly block interaction:
- Modal overlays, popups, dialogs
- Cookie banners, privacy notices
- Ad overlays, promotional content
- Login prompts, age verification
- Error messages, alerts

If you find a blocking element with a dismiss/close button, return its CSS selector.
Common dismiss patterns: text containing "Close", "X", "Accept", "OK", "Continue", "No Thanks", "Later"

Return ONLY a JSON object: {{"selector": ".your-selector"}} or {{"selector": null}}
"""
