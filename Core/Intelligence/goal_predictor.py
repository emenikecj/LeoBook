# goal_predictor.py: goal_predictor.py: Goal distribution and xG (Expected Goals) calculation.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: GoalPredictor

"""
Goal Predictor Module
Predicts goal distributions and expected goals (xG) for teams.
"""

from typing import List, Dict, Any
from collections import Counter


class GoalPredictor:
    """Predicts goal distributions and expected goals for team analysis"""

    @staticmethod
    def predict_goals_distribution(last_10_matches: List[Dict], team_name: str, is_home_game: bool) -> Dict[str, Dict]:
        """
        Predict goals distribution based on form and home/away advantage.
        Returns probability distribution for goals scored and conceded.
        """
        matches = [m for m in last_10_matches if m]
        if not matches:
            default = {"0": 0.4, "1": 0.3, "2": 0.2, "3+": 0.1}
            return {"goals_scored": default.copy(), "goals_conceded": default.copy()}

        scored = []
        conceded = []

        for m in matches:
            home = m.get("home", "")
            away = m.get("away", "")
            score = m.get("score", "0-0")
            try:
                gf, ga = map(int, score.replace(" ", "").split("-"))
            except:
                continue

            is_home_match = home == team_name
            goals_for = gf if is_home_match else ga
            goals_against = ga if is_home_match else gf

            # Apply home/away adjustment
            if is_home_game and not is_home_match:
                # Team playing at home but this was an away match - boost goals
                goals_for = int(goals_for * 1.25)
            elif not is_home_game and is_home_match:
                # Team playing away but this was a home match - reduce goals
                goals_for = int(goals_for * 0.80)

            scored.append(min(goals_for, 5))  # Cap at 5 for distribution
            conceded.append(min(goals_against, 5))

        def make_dist(lst: List[int]) -> Dict[str, float]:
            """Create probability distribution from goal counts"""
            c = Counter(lst)
            total = len(lst) or 1
            return {
                "0": c[0]/total,
                "1": c[1]/total,
                "2": c[2]/total,
                "3+": (c[3] + c[4] + c[5])/total  # Group 3+ goals together
            }

        return {
            "goals_scored": make_dist(scored),
            "goals_conceded": make_dist(conceded)
        }

    @staticmethod
    def calculate_expected_goals(goals_distribution: Dict[str, float]) -> float:
        """
        Calculate expected goals (xG) from a probability distribution.
        """
        xg = 0.0
        for goal_str, prob in goals_distribution.items():
            if goal_str == "3+":
                # Assume average of 3.5 goals for 3+ category
                xg += 3.5 * prob
            else:
                xg += int(goal_str) * prob
        return round(xg, 2)

    @staticmethod
    def get_match_xg(home_team: str, away_team: str, home_form: List[Dict], away_form: List[Dict]) -> Dict[str, float]:
        """
        Calculate expected goals for a specific match.
        """
        home_dist = GoalPredictor.predict_goals_distribution(home_form, home_team, True)
        away_dist = GoalPredictor.predict_goals_distribution(away_form, away_team, False)

        home_xg = GoalPredictor.calculate_expected_goals(home_dist["goals_scored"])
        away_xg = GoalPredictor.calculate_expected_goals(away_dist["goals_scored"])

        return {
            "home_xg": home_xg,
            "away_xg": away_xg,
            "total_xg": round(home_xg + away_xg, 2),
            "xg_difference": round(home_xg - away_xg, 2)
        }

    @staticmethod
    def predict_score_probabilities(home_xg: float, away_xg: float) -> List[Dict[str, Any]]:
        """
        Predict most probable scores based on expected goals.
        Uses Poisson distribution approximation.
        """
        import math

        scores = []
        max_goals = 5  # Consider scores up to 5-5

        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                # Poisson probability for each score
                home_prob = math.exp(-home_xg) * (home_xg ** home_goals) / math.factorial(home_goals)
                away_prob = math.exp(-away_xg) * (away_xg ** away_goals) / math.factorial(away_goals)
                total_prob = home_prob * away_prob

                if total_prob > 0.01:  # Only include reasonably probable scores
                    score_str = f"{home_goals}-{away_goals}"
                    scores.append({
                        "score": score_str,
                        "probability": round(total_prob, 4),
                        "home_goals": home_goals,
                        "away_goals": away_goals
                    })

        # Sort by probability (highest first)
        scores.sort(key=lambda x: x["probability"], reverse=True)
        return scores[:10]  # Return top 10 most probable scores
