# mapping.py: mapping.py: Prediction mapper for Football.com markets.
# Part of LeoBook Modules — Football.com Booking
#
# Functions: find_market_and_outcome()

"""
Market Mapping Logic
Translates prediction text into site-specific market and outcome names.
"""

import re
from typing import Dict

async def find_market_and_outcome(prediction: Dict) -> tuple:
    """Map prediction to market name and outcome name."""
    pred_text = prediction.get('prediction', '').strip()
    if not pred_text or pred_text == 'SKIP':
        return "", ""

    home_team = prediction.get('home_team', '').strip()
    away_team = prediction.get('away_team', '').strip()

    # Normalize strings
    pt_upper = pred_text.upper()
    ht_upper = home_team.upper()
    at_upper = away_team.upper()

    # --- 0. Draw No Bet (Explicit) ---
    if "DNB" in pt_upper or "DRAW NO BET" in pt_upper:
        if ht_upper in pt_upper or "HOME" in pt_upper: return "Draw No Bet", "Home"
        if at_upper in pt_upper or "AWAY" in pt_upper: return "Draw No Bet", "Away"
        # Fallback if team name not explicit (contextual)
        return "Draw No Bet", "Home" # Risky default, better to rely on parsing

    # --- 1. 1X2 (Match Winner) ---
    if pt_upper == "DRAW":
        return "1X2", "Draw"
    
    # Clean parens for Team Name checks
    clean_pt = pt_upper.replace("(", "").replace(")", "")
    
    if clean_pt in [f"{ht_upper} TO WIN", f"{ht_upper} WIN", ht_upper, "1"]:
        return "1X2", "Home"
    if clean_pt in [f"{at_upper} TO WIN", f"{at_upper} WIN", at_upper, "2"]:
        return "1X2", "Away"
    if pt_upper == "X": return "1X2", "Draw"
    
    # --- 1.5 Team Win (Alternative) ---
    if f"{ht_upper} TO WIN" in pt_upper: return "1X2", "Home"
    if f"{at_upper} TO WIN" in pt_upper: return "1X2", "Away"

    # --- 2. Double Chance ---
    if "OR DRAW" in pt_upper:
        if ht_upper in pt_upper: return "Double Chance", "Home or Draw"
        if at_upper in pt_upper: return "Double Chance", "Draw or Away"
    if f"{ht_upper} OR {at_upper}" in pt_upper or f"{at_upper} OR {ht_upper}" in pt_upper or "12" in pt_upper:
        return "Double Chance", "Home or Away"
    if "1X" in pt_upper: return "Double Chance", "Home or Draw"
    if "X2" in pt_upper: return "Double Chance", "Draw or Away"

    # --- 3. Both Teams To Score (GG/NG) ---
    if "BTTS" in pt_upper or "BOTH TEAMS TO SCORE" in pt_upper:
        if "NO" in pt_upper: return "GG/NG", "No"
        return "GG/NG", "Yes"  # Default to Yes if just BTTS

    # --- 4. Over/Under ---
    if ("OVER" in pt_upper or "UNDER" in pt_upper) and "&" not in pt_upper and "AND" not in pt_upper:
        match = re.search(r'(OVER|UNDER)[_\s]+(\d+\.5)', pt_upper)
        if match:
            line = match.group(2)
            type_str = match.group(1).title()
            return "Over/Under", f"{type_str} {line}"

    # --- 6. Goal Range ---
    if "GOALS" in pt_upper and "-" in pt_upper:
        # e.g., "1-2 GOALS" -> "1-2 Goals"
        match = re.search(r'(\d+-\d+)\s*GOALS', pt_upper)
        if match:
             return "Goal Bounds", match.group(1)

    return "", ""
