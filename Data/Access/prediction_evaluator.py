# prediction_evaluator.py: prediction_evaluator.py: Logic for resolving betting market outcomes.
# Part of LeoBook Data — Access Layer
#
# Functions: evaluate_prediction()

"""
Prediction Evaluator Module
Handles prediction evaluation logic for all betting markets.
Responsible for determining if predictions are correct based on actual match outcomes.
"""

import re
from typing import Optional, Dict, Any


def evaluate_prediction(prediction: str, actual_score: str, home_team: str, away_team: str) -> Optional[bool]:
    """
    Evaluates if a prediction is correct based on the actual score.
    This function understands various betting markets from model.py.

    Args:
        prediction (str): The prediction made, e.g., "Coleraine to win", "Hapoel Hadera or Draw", "Both Teams To Score No".
        actual_score (str): The final score, e.g., "2-0".
        home_team (str): The name of the home team.
        away_team (str): The name of the away team.

    Returns:
        Optional[bool]: True if correct, False if incorrect, None if format is unrecognized.
    """
    try:
        home_goals, away_goals = map(int, actual_score.split('-'))
        total_goals = home_goals + away_goals
    except (ValueError, TypeError):
        return None # Cannot determine outcome from score

    # Normalize prediction string - keep original case for team name matching
    prediction_str = prediction.strip()

    # Create normalized versions for different matching strategies
    prediction_lower = prediction_str.lower()
    home_team_lower = home_team.lower().strip()
    away_team_lower = away_team.lower().strip()

    # --- Market Evaluation Logic ---

    # 1. 1X2: "Team to win" or "Draw"
    if prediction_str.endswith(" to win"):
        team_name = prediction_str.replace(" to win", "").strip()
        if team_name.lower() == home_team_lower:
            return home_goals > away_goals
        elif team_name.lower() == away_team_lower:
            return away_goals > home_goals
    if prediction_lower == 'draw':
        return home_goals == away_goals

    # 2. Double Chance: "Team or Draw"
    if " or Draw" in prediction_str:
        team_name = prediction_str.replace(" or Draw", "").strip()
        if team_name.lower() == home_team_lower:
            return home_goals >= away_goals  # Home win or draw
        elif team_name.lower() == away_team_lower:
            return away_goals >= home_goals  # Away win or draw

    # 3. Draw No Bet: "Team to win (DNB)" or "Team" (where prediction is just the team name)
    if prediction_str.endswith(" to win (DNB)"):
        team_name = prediction_str.replace(" to win (DNB)", "").strip()
        if team_name.lower() == home_team_lower:
            return home_goals > away_goals
        elif team_name.lower() == away_team_lower:
            return away_goals > home_goals

    if prediction_str == home_team:
        return home_goals > away_goals
    if prediction_str == away_team:
        return away_goals > home_goals

    # 4. BTTS: "Both Teams To Score Yes/No"
    if prediction_str == "Both Teams To Score Yes":
        return home_goals > 0 and away_goals > 0
    if prediction_str == "Both Teams To Score No":
        return home_goals == 0 or away_goals == 0

    # 5. Over/Under Markets: "Over 2.5", "Under 1.5"
    if prediction_lower.startswith('over '):
        try:
            value = float(prediction_lower.split('over')[1].strip())
            return total_goals > value
        except (ValueError, IndexError): pass
    if prediction_lower.startswith('under '):
        try:
            value = float(prediction_lower.split('under')[1].strip())
            return total_goals < value
        except (ValueError, IndexError): pass

    # 6. Goal Range: "2-3 goals", "4-6 goals", "0-1 goals"
    if 'goals' in prediction_lower:
        range_match = re.match(r'(\d+)-(\d+) goals', prediction_lower)
        if range_match:
            low, high = map(int, range_match.groups())
            return low <= total_goals <= high

        plus_match = re.match(r'(\d+)\+ goals', prediction_lower)
        if plus_match:
            low = int(plus_match.groups()[0])
            return total_goals >= low

    # 7. Correct Score: "2-1", "1-0", "0-0"
    if re.match(r'^\d+-\d+$', prediction_str):
        try:
            pred_h, pred_a = map(int, prediction_str.split('-'))
            return home_goals == pred_h and away_goals == pred_a
        except ValueError: pass

    # 8. Clean Sheet: "Team Clean Sheet"
    if prediction_str.endswith(" Clean Sheet"):
        team_name = prediction_str.replace(" Clean Sheet", "").strip()
        if team_name.lower() == home_team_lower:
            return away_goals == 0
        elif team_name.lower() == away_team_lower:
            return home_goals == 0

    # 9. Asian Handicap: "Team -1", "Team +0.5"
    handicap_match = re.match(r'(.+?)\s*([+-]\d+(?:\.\d+)?)$', prediction_str)
    if handicap_match:
        team_name, handicap_str = handicap_match.groups()
        try:
            handicap = float(handicap_str)
            if team_name.strip().lower() == home_team_lower:
                return (home_goals + handicap) > away_goals
            elif team_name.strip().lower() == away_team_lower:
                return (away_goals + handicap) > home_goals
        except ValueError:
            pass

    # 10. Combo Bets: "Team to win & Over 2.5", "Team to win & BTTS Yes"
    if " to win & " in prediction_str:
        parts = prediction_str.split(" to win & ")
        if len(parts) == 2:
            team_name = parts[0].strip()
            condition = parts[1].strip().lower()

            # Determine win condition
            if team_name.lower() == home_team_lower:
                win_condition = home_goals > away_goals
            elif team_name.lower() == away_team_lower:
                win_condition = away_goals > home_goals
            else:
                win_condition = False

            # Determine secondary condition
            if condition == "over 2.5":
                secondary_condition = total_goals > 2.5
            elif condition == "btts yes":
                secondary_condition = home_goals > 0 and away_goals > 0
            elif condition == "btts no":
                secondary_condition = home_goals == 0 or away_goals == 0
            else:
                secondary_condition = False

            return win_condition and secondary_condition

    # 11. Team Over/Under: "Team Over 1.5"
    if " Over " in prediction_str:
        parts = prediction_str.split(" Over ")
        if len(parts) == 2:
            team_name = parts[0].strip()
            try:
                value = float(parts[1].strip())
                if team_name.lower() == home_team_lower:
                    return home_goals > value
                elif team_name.lower() == away_team_lower:
                    return away_goals > value
            except ValueError:
                pass

    # 12. Winner and BTTS combinations
    if " & BTTS " in prediction_str:
        parts = prediction_str.split(" & BTTS ")
        if len(parts) == 2:
            winner_part = parts[0].strip()
            btts_part = parts[1].strip()

            # Parse winner
            if winner_part.endswith(" to win"):
                team_name = winner_part.replace(" to win", "").strip()
                if team_name.lower() == home_team_lower:
                    win_condition = home_goals > away_goals
                elif team_name.lower() == away_team_lower:
                    win_condition = away_goals > home_goals
                else:
                    win_condition = False
            else:
                win_condition = False

            # Parse BTTS
            if btts_part.lower() == "yes":
                btts_condition = home_goals > 0 and away_goals > 0
            elif btts_part.lower() == "no":
                btts_condition = home_goals == 0 or away_goals == 0
            else:
                btts_condition = False

            return win_condition and btts_condition

    # Fallback: Check if prediction matches team names exactly
    if prediction_str == home_team:
        return home_goals > away_goals
    if prediction_str == away_team:
        return away_goals > home_goals

    return None # Return None if prediction format is not recognized
