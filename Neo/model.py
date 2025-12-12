

# model.py
# FINAL 2026 VERSION — Full Goal-Based + Rule-Based Hybrid Intelligence
# Uses actual goals from last 10 matches + H2H + Standings
# Predicts: Winner, xG, BTTS, Over/Under, Correct Score

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from collections import Counter
import json
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
import joblib


class LearningEngine:
    """Self-learning component that analyzes prediction performance and adjusts weights"""

    LEARNING_DB = "DB/learning_weights.json"

    DEFAULT_WEIGHTS = {
        "h2h_home_win": 3,
        "h2h_away_win": 3,
        "h2h_draw": 4,
        "h2h_over25": 3,
        "standings_top_vs_bottom": 6,
        "standings_table_advantage": 3,
        "standings_gd_strong": 2,
        "standings_gd_weak": 2,
        "form_score_2plus": 4,
        "form_score_3plus": 2,
        "form_concede_2plus": 4,
        "form_no_score": 5,
        "form_clean_sheet": 5,
        "form_vs_top_win": 3,
        "xg_advantage": 3,
        "xg_draw": 2,
        "confidence_calibration": {
            "Very High": 0.75,
            "High": 0.60,
            "Medium": 0.50,
            "Low": 0.40
        }
    }

    @staticmethod
    def load_weights():
        """Load learned weights from file"""
        if os.path.exists(LearningEngine.LEARNING_DB):
            try:
                with open(LearningEngine.LEARNING_DB, 'r') as f:
                    return json.load(f)
            except:
                pass
        return LearningEngine.DEFAULT_WEIGHTS.copy()

    @staticmethod
    def save_weights(weights):
        """Save learned weights to file"""
        os.makedirs("DB", exist_ok=True)
        with open(LearningEngine.LEARNING_DB, 'w') as f:
            json.dump(weights, f, indent=2)

    @staticmethod
    def analyze_performance():
        """Analyze past predictions to calculate rule effectiveness"""
        from Helpers.DB_Helpers.db_helpers import PREDICTIONS_CSV
        import csv

        if not os.path.exists(PREDICTIONS_CSV):
            return {}

        rule_performance = {
            "h2h_home_win": {"correct": 0, "total": 0},
            "h2h_away_win": {"correct": 0, "total": 0},
            "h2h_draw": {"correct": 0, "total": 0},
            "h2h_over25": {"correct": 0, "total": 0},
            "standings_top_vs_bottom": {"correct": 0, "total": 0},
            "standings_table_advantage": {"correct": 0, "total": 0},
            "standings_gd_strong": {"correct": 0, "total": 0},
            "standings_gd_weak": {"correct": 0, "total": 0},
            "form_score_2plus": {"correct": 0, "total": 0},
            "form_score_3plus": {"correct": 0, "total": 0},
            "form_concede_2plus": {"correct": 0, "total": 0},
            "form_no_score": {"correct": 0, "total": 0},
            "form_clean_sheet": {"correct": 0, "total": 0},
            "form_vs_top_win": {"correct": 0, "total": 0},
            "xg_advantage": {"correct": 0, "total": 0},
            "xg_draw": {"correct": 0, "total": 0},
        }

        # Read predictions and analyze which rules contributed to correct predictions
        with open(PREDICTIONS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('outcome_correct') != 'True' or not row.get('reason'):
                    continue

                prediction_type = row.get('prediction', row.get('type', ''))
                is_correct = row.get('outcome_correct') == 'True'
                reasoning = row.get('reason', '')

                # Analyze which rules were triggered based on reasoning
                if 'H2H home strong' in reasoning:
                    rule_performance["h2h_home_win"]["total"] += 1
                    if is_correct: rule_performance["h2h_home_win"]["correct"] += 1

                if 'H2H away strong' in reasoning:
                    rule_performance["h2h_away_win"]["total"] += 1
                    if is_correct: rule_performance["h2h_away_win"]["correct"] += 1

                if 'H2H drawish' in reasoning:
                    rule_performance["h2h_draw"]["total"] += 1
                    if is_correct: rule_performance["h2h_draw"]["correct"] += 1

                if 'Top vs Bottom' in reasoning:
                    rule_performance["standings_top_vs_bottom"]["total"] += 1
                    if is_correct: rule_performance["standings_top_vs_bottom"]["correct"] += 1

                if 'strong GD' in reasoning:
                    rule_performance["standings_gd_strong"]["total"] += 1
                    if is_correct: rule_performance["standings_gd_strong"]["correct"] += 1

                if 'weak GD' in reasoning:
                    rule_performance["standings_gd_weak"]["total"] += 1
                    if is_correct: rule_performance["standings_gd_weak"]["correct"] += 1

                if 'scores 2+' in reasoning:
                    rule_performance["form_score_2plus"]["total"] += 1
                    if is_correct: rule_performance["form_score_2plus"]["correct"] += 1

                if 'concedes 2+' in reasoning:
                    rule_performance["form_concede_2plus"]["total"] += 1
                    if is_correct: rule_performance["form_concede_2plus"]["correct"] += 1

                if 'fails to score' in reasoning:
                    rule_performance["form_no_score"]["total"] += 1
                    if is_correct: rule_performance["form_no_score"]["correct"] += 1

                if 'strong defense' in reasoning:
                    rule_performance["form_clean_sheet"]["total"] += 1
                    if is_correct: rule_performance["form_clean_sheet"]["correct"] += 1

                if 'xG advantage' in reasoning:
                    rule_performance["xg_advantage"]["total"] += 1
                    if is_correct: rule_performance["xg_advantage"]["correct"] += 1

                if 'Close xG suggests draw' in reasoning:
                    rule_performance["xg_draw"]["total"] += 1
                    if is_correct: rule_performance["xg_draw"]["correct"] += 1

        return rule_performance

    @staticmethod
    def update_weights():
        """Update weights based on performance analysis"""
        performance = LearningEngine.analyze_performance()
        current_weights = LearningEngine.load_weights()

        for rule, stats in performance.items():
            if stats["total"] >= 10:  # Minimum sample size
                accuracy = stats["correct"] / stats["total"]
                # Adjust weight based on accuracy
                # If accuracy > 0.6, increase weight; if < 0.4, decrease weight
                if accuracy > 0.6:
                    current_weights[rule] = min(current_weights[rule] * 1.1, 10)  # Cap at 10
                elif accuracy < 0.4:
                    current_weights[rule] = max(current_weights[rule] * 0.9, 0.5)  # Floor at 0.5

        LearningEngine.save_weights(current_weights)
        return current_weights


class MLModel:
    """Machine Learning component for ensemble predictions"""

    MODEL_DIR = "DB/models"
    FEATURES = [
        'home_position', 'away_position', 'home_gd', 'away_gd',
        'home_form_wins', 'home_form_draws', 'home_form_losses',
        'away_form_wins', 'away_form_draws', 'away_form_losses',
        'home_goals_scored', 'home_goals_conceded',
        'away_goals_scored', 'away_goals_conceded',
        'h2h_home_wins', 'h2h_away_wins', 'h2h_draws',
        'home_xg', 'away_xg', 'league_size'
    ]

    @staticmethod
    def prepare_features(vision_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract and prepare features for ML prediction"""
        h2h_data = vision_data.get("h2h_data", {})
        standings = vision_data.get("standings", [])
        home_team = h2h_data.get("home_team")
        away_team = h2h_data.get("away_team")

        if not home_team or not away_team or not standings:
            return None

        # Basic team data
        rank = {t["team_name"]: t["position"] for t in standings}
        gd = {t["team_name"]: t.get("goal_difference", 0) for t in standings}

        home_position = rank.get(home_team, 20)
        away_position = rank.get(away_team, 20)
        home_gd = gd.get(home_team, 0)
        away_gd = gd.get(away_team, 0)

        # Form data
        home_form = h2h_data.get("home_last_10_matches", [])
        away_form = h2h_data.get("away_last_10_matches", [])

        home_wins = sum(1 for m in home_form if
                       (m.get("winner") == "Home" and m.get("home") == home_team) or
                       (m.get("winner") == "Away" and m.get("away") == home_team))
        home_draws = sum(1 for m in home_form if m.get("winner") == "Draw")
        home_losses = len(home_form) - home_wins - home_draws

        away_wins = sum(1 for m in away_form if
                       (m.get("winner") == "Home" and m.get("home") == away_team) or
                       (m.get("winner") == "Away" and m.get("away") == away_team))
        away_draws = sum(1 for m in away_form if m.get("winner") == "Draw")
        away_losses = len(away_form) - away_wins - away_draws

        # Goal stats
        home_scored = sum(int(m.get("score", "0-0").split("-")[0 if m.get("home") == home_team else 1]) for m in home_form if m.get("score"))
        home_conceded = sum(int(m.get("score", "0-0").split("-")[1 if m.get("home") == home_team else 0]) for m in home_form if m.get("score"))
        away_scored = sum(int(m.get("score", "0-0").split("-")[0 if m.get("home") == away_team else 1]) for m in away_form if m.get("score"))
        away_conceded = sum(int(m.get("score", "0-0").split("-")[1 if m.get("home") == away_team else 0]) for m in away_form if m.get("score"))

        # H2H stats
        h2h = h2h_data.get("head_to_head", [])
        h2h_home_wins = sum(1 for m in h2h if
                           (m.get("winner") == "Home" and m.get("home") == home_team) or
                           (m.get("winner") == "Away" and m.get("away") == home_team))
        h2h_away_wins = sum(1 for m in h2h if
                           (m.get("winner") == "Home" and m.get("home") == away_team) or
                           (m.get("winner") == "Away" and m.get("away") == away_team))
        h2h_draws = sum(1 for m in h2h if m.get("winner") == "Draw")

        # xG calculation
        home_dist = RuleEngine.predict_goals_distribution(home_form, home_team, True)
        away_dist = RuleEngine.predict_goals_distribution(away_form, away_team, False)
        home_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in home_dist["goals_scored"].items())
        away_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in away_dist["goals_scored"].items())

        return {
            'home_position': home_position,
            'away_position': away_position,
            'home_gd': home_gd,
            'away_gd': away_gd,
            'home_form_wins': home_wins,
            'home_form_draws': home_draws,
            'home_form_losses': home_losses,
            'away_form_wins': away_wins,
            'away_form_draws': away_draws,
            'away_form_losses': away_losses,
            'home_goals_scored': home_scored,
            'home_goals_conceded': home_conceded,
            'away_goals_scored': away_scored,
            'away_goals_conceded': away_conceded,
            'h2h_home_wins': h2h_home_wins,
            'h2h_away_wins': h2h_away_wins,
            'h2h_draws': h2h_draws,
            'home_xg': home_xg,
            'away_xg': away_xg,
            'league_size': len(standings)
        }

    @staticmethod
    def train_models():
        """Train ML models using historical prediction data"""
        from Helpers.DB_Helpers.db_helpers import PREDICTIONS_CSV
        import csv

        if not os.path.exists(PREDICTIONS_CSV):
            return False

        # Load historical data
        data = []
        with open(PREDICTIONS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('outcome_correct') in ['True', 'False']:
                    # We need to reconstruct features from stored data
                    # This is a simplified version - in practice you'd store features
                    data.append(row)

        if len(data) < 50:  # Need minimum data for training
            return False

        # Create training data (simplified - you'd extract proper features)
        X = []
        y = []

        for row in data:
            # Extract basic features from stored reasoning/tags
            # This is a placeholder - you'd need to store proper features
            features = [0] * len(MLModel.FEATURES)  # Placeholder
            target = 1 if row.get('outcome_correct') == 'True' else 0
            X.append(features)
            y.append(target)

        X = np.array(X)
        y = np.array(y)

        if len(X) == 0:
            return False

        # Train models
        os.makedirs(MLModel.MODEL_DIR, exist_ok=True)

        # Random Forest
        rf = RandomForestClassifier(n_estimators=100, random_state=42)
        rf.fit(X, y)
        joblib.dump(rf, os.path.join(MLModel.MODEL_DIR, 'random_forest.pkl'))

        # Gradient Boosting
        gb = GradientBoostingClassifier(n_estimators=100, random_state=42)
        gb.fit(X, y)
        joblib.dump(gb, os.path.join(MLModel.MODEL_DIR, 'gradient_boosting.pkl'))

        # Cross-validation scores
        rf_scores = cross_val_score(rf, X, y, cv=5)
        gb_scores = cross_val_score(gb, X, y, cv=5)

        print(f"ML Models trained - RF: {rf_scores.mean():.3f}, GB: {gb_scores.mean():.3f}")
        return True

    @staticmethod
    def predict(features: Dict[str, Any]) -> Dict[str, Any]:
        """Make ML predictions using ensemble of trained models"""
        rf_path = os.path.join(MLModel.MODEL_DIR, 'random_forest.pkl')
        gb_path = os.path.join(MLModel.MODEL_DIR, 'gradient_boosting.pkl')

        if not (os.path.exists(rf_path) and os.path.exists(gb_path)):
            return {"confidence": 0.5, "prediction": "UNKNOWN"}

        try:
            # Load models
            rf = joblib.load(rf_path)
            gb = joblib.load(gb_path)

            # Prepare feature vector
            feature_vector = np.array([[features.get(f, 0) for f in MLModel.FEATURES]])

            # Get predictions
            rf_pred = rf.predict_proba(feature_vector)[0][1]  # Probability of correct prediction
            gb_pred = gb.predict_proba(feature_vector)[0][1]

            # Ensemble prediction
            ensemble_confidence = (rf_pred + gb_pred) / 2

            return {
                "confidence": ensemble_confidence,
                "rf_confidence": rf_pred,
                "gb_confidence": gb_pred,
                "prediction": "HIGH" if ensemble_confidence > 0.6 else "MEDIUM" if ensemble_confidence > 0.4 else "LOW"
            }

        except Exception as e:
            print(f"ML Prediction error: {e}")
            return {"confidence": 0.5, "prediction": "UNKNOWN"}


class RuleEngine:
    @staticmethod
    def check_threshold(count: int, total: int, rule_type: str) -> bool:
        if total == 0:
            return False
        if rule_type == "majority":
            return count >= (total // 2 + 1)
        elif rule_type == "third":
            return count >= max(3, total // 3)
        elif rule_type == "quarter":
            return count >= max(2, total // 4)
        return False

    @staticmethod
    def classify_opponent_strength(rank: int, league_size: int) -> str:
        if rank <= (league_size // 4):
            return 'top'
        elif rank <= (league_size // 2):
            return 'mid'
        else:
            return 'bottom'

    @staticmethod
    def _parse_match_result(match: Dict, team_name: str) -> Tuple[str, int, int, str]:
        if not match:
            return "L", 0, 0, ""
        home = match.get("home", "")
        away = match.get("away", "")
        score = match.get("score", "0-0")
        winner = match.get("winner", "")
        try:
            gf, ga = map(int, score.replace(" ", "").split("-"))
        except:
            gf, ga = 0, 0

        if winner == "Draw":
            result = "D"
        elif (winner == "Home" and home == team_name) or (winner == "Away" and away == team_name):
            result = "W"
        else:
            result = "L"

        opponent = away if home == team_name else home
        return result, gf, ga, opponent

    @staticmethod
    def generate_form_tags(
        last_10_matches: List[Dict],
        team_name: str,
        standings: List[Dict]
    ) -> List[str]:
        matches = [m for m in last_10_matches if m]
        N = len(matches)
        if N < 3:
            return []

        team_to_rank = {t["team_name"]: t["position"] for t in standings}
        league_size = len(standings) or 20

        counts = {'SNG':0, 'CS':0, 'S1+':0, 'S2+':0, 'S3+':0,
                  'C1+':0, 'C2+':0, 'C3+':0, 'W':0, 'D':0, 'L':0}
        strength_counts = {'top': counts.copy(), 'mid': counts.copy(), 'bottom': counts.copy()}

        for match in matches:
            result, gf, ga, opponent = RuleEngine._parse_match_result(match, team_name)

            if gf == 0: counts['SNG'] += 1
            if ga == 0: counts['CS'] += 1
            if gf >= 1: counts['S1+'] += 1
            if gf >= 2: counts['S2+'] += 1
            if gf >= 3: counts['S3+'] += 1
            if ga >= 1: counts['C1+'] += 1
            if ga >= 2: counts['C2+'] += 1
            if ga >= 3: counts['C3+'] += 1
            if result == 'W': counts['W'] += 1
            if result == 'D': counts['D'] += 1
            if result == 'L': counts['L'] += 1

            if opponent in team_to_rank:
                strength = RuleEngine.classify_opponent_strength(team_to_rank[opponent], league_size)
                s = strength_counts[strength]
                if gf == 0: s['SNG'] += 1
                if ga == 0: s['CS'] += 1
                if gf >= 1: s['S1+'] += 1
                if gf >= 2: s['S2+'] += 1
                if gf >= 3: s['S3+'] += 1
                if ga >= 1: s['C1+'] += 1
                if ga >= 2: s['C2+'] += 1
                if ga >= 3: s['C3+'] += 1
                if result == 'W': s['W'] += 1
                if result == 'D': s['D'] += 1
                if result == 'L': s['L'] += 1

        tags = []
        team_slug = team_name.replace(" ", "_").upper()

        # Simplified tagging: majority → strong tag, third → normal tag (no "_third" suffix)
        for key, cnt in counts.items():
            if RuleEngine.check_threshold(cnt, N, "majority"):
                tags.append(f"{team_slug}_FORM_{key}")
            elif RuleEngine.check_threshold(cnt, N, "third"):
                tags.append(f"{team_slug}_FORM_{key}")

        for strength, s in strength_counts.items():
            s_N = sum(1 for m in matches
                      if (opp := RuleEngine._parse_match_result(m, team_name)[3]) in team_to_rank
                      and RuleEngine.classify_opponent_strength(team_to_rank[opp], league_size) == strength)
            if s_N < 2:
                continue
            for key, cnt in s.items():
                if RuleEngine.check_threshold(cnt, s_N, "third"):
                    tags.append(f"{team_slug}_FORM_{key}_vs_{strength.upper()}")

        return list(set(tags))

    @staticmethod
    def generate_h2h_tags(h2h_list: List[Dict], home_team: str, away_team: str) -> List[str]:
        matches = [m for m in h2h_list if m]
        if not matches:
            return []

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        counts = {
            f'{home_slug}_WINS_H2H': 0,
            f'{away_slug}_WINS_H2H': 0,
            'H2H_D': 0,
            'H2H_O25': 0,
            'H2H_U25': 0,
            'H2H_BTTS': 0
        }

        for m in matches:
            try:
                hg, ag = map(int, m.get("score", "0-0").replace(" ", "").split("-"))
            except:
                continue
            total = hg + ag

            # Winner from perspective of current fixture teams
            if (m.get("winner") == "Home" and m.get("home") == home_team) or \
               (m.get("winner") == "Away" and m.get("away") == home_team):
                counts[f'{home_slug}_WINS_H2H'] += 1
            elif (m.get("winner") == "Home" and m.get("home") == away_team) or \
                 (m.get("winner") == "Away" and m.get("away") == away_team):
                counts[f'{away_slug}_WINS_H2H'] += 1
            else:
                counts['H2H_D'] += 1

            if total > 2:
                counts['H2H_O25'] += 1
            else:
                counts['H2H_U25'] += 1
            if hg > 0 and ag > 0:
                counts['H2H_BTTS'] += 1

        tags = []
        N = len(matches)
        for key, cnt in counts.items():
            if RuleEngine.check_threshold(cnt, N, "majority"):
                tags.append(key)
            elif RuleEngine.check_threshold(cnt, N, "third"):
                tags.append(f"{key}_third")

        return list(set(tags))

    @staticmethod
    def generate_standings_tags(standings: List[Dict], home_team: str, away_team: str) -> List[str]:
        if not standings:
            return []
        league_size = len(standings)
        rank = {t["team_name"]: t["position"] for t in standings}
        gd = {t["team_name"]: t.get("goal_difference", (t.get("goals_for") or 0) - (t.get("goals_against") or 0)) for t in standings}

        hr = rank.get(home_team, 999)
        ar = rank.get(away_team, 999)
        hgd = gd.get(home_team, 0)
        agd = gd.get(away_team, 0)

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        tags = []
        if hr <= 3: tags.append(f"{home_slug}_TOP3")
        if hr > league_size - 5: tags.append(f"{home_slug}_BOTTOM5")
        if ar <= 3: tags.append(f"{away_slug}_TOP3")
        if ar > league_size - 5: tags.append(f"{away_slug}_BOTTOM5")
        if hgd > 0: tags.append(f"{home_slug}_GD_POS")
        if hgd < 0: tags.append(f"{home_slug}_GD_NEG")
        if agd > 0: tags.append(f"{away_slug}_GD_POS")
        if agd < 0: tags.append(f"{away_slug}_GD_NEG")
        if hr < ar - 8: tags.append(f"{home_slug}_TABLE_ADV8+")
        if ar < hr - 8: tags.append(f"{away_slug}_TABLE_ADV8+")
        if hgd > 10: tags.append(f"{home_slug}_GD_POS_STRONG")
        if hgd < -10: tags.append(f"{home_slug}_GD_NEG_WEAK")
        if agd > 10: tags.append(f"{away_slug}_GD_POS_STRONG")
        if agd < -10: tags.append(f"{away_slug}_GD_NEG_WEAK")
        return list(set(tags))

    @staticmethod
    def predict_goals_distribution(last_10_matches: List[Dict], team_name: str, is_home_game: bool) -> Dict[str, Dict]:
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

            # Simple home/away adjustment
            if is_home_game and not is_home_match:
                goals_for = int(goals_for * 1.25)
            elif not is_home_game and is_home_match:
                goals_for = int(goals_for * 0.80)

            scored.append(min(goals_for, 5))
            conceded.append(min(goals_against, 5))

        def make_dist(lst):
            c = Counter(lst)
            total = len(lst) or 1
            return {
                "0": c[0]/total,
                "1": c[1]/total,
                "2": c[2]/total,
                "3+": (c[3] + c[4] + c[5])/total
            }

        return {
            "goals_scored": make_dist(scored),
            "goals_conceded": make_dist(conceded)
        }

    @staticmethod
    def generate_betting_market_predictions(
        home_team: str, away_team: str, home_score: float, away_score: float, draw_score: float,
        btts_prob: float, over25_prob: float, scores: List[Dict], home_xg: float, away_xg: float,
        reasoning: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Generate predictions for comprehensive betting markets"""

        predictions = {}

        # Helper function to calculate confidence score
        def calc_confidence(base_score: float, threshold: float = 0.5) -> float:
            return min(base_score / threshold, 1.0) if base_score > threshold else base_score / threshold * 0.5

        # 1. Full Time Result (1X2)
        max_score = max(home_score, away_score, draw_score)
        if draw_score == max_score:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": "Draw",
                "confidence_score": calc_confidence(draw_score, 6),
                "reason": "Draw most likely outcome"
            }
        elif home_score == max_score:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": f"{home_team} to win",
                "confidence_score": calc_confidence(home_score, 8),
                "reason": f"{home_team} favored to win"
            }
        else:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": f"{away_team} to win",
                "confidence_score": calc_confidence(away_score, 8),
                "reason": f"{away_team} favored to win"
            }

        # 2. Double Chance
        if home_score + draw_score > away_score + 2:
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{home_team} or Draw",
                "confidence_score": calc_confidence((home_score + draw_score) / 2, 6),
                "reason": f"{home_team} unlikely to lose"
            }
        elif away_score + draw_score > home_score + 2:
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{away_team} or Draw",
                "confidence_score": calc_confidence((away_score + draw_score) / 2, 6),
                "reason": f"{away_team} unlikely to lose"
            }
        else:
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{home_team} or {away_team}",
                "confidence_score": calc_confidence(max(home_score, away_score), 5),
                "reason": "Draw unlikely"
            }

        # 3. Draw No Bet
        if home_score > away_score + 3:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": home_team,
                "confidence_score": calc_confidence(home_score - away_score, 3),
                "reason": f"{home_team} clear favorite"
            }
        elif away_score > home_score + 3:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": away_team,
                "confidence_score": calc_confidence(away_score - home_score, 3),
                "reason": f"{away_team} clear favorite"
            }
        else:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": home_team,
                "confidence_score": 0.4,  # Low confidence when close
                "reason": "Very close match"
            }

        # 4. BTTS (Both Teams To Score)
        btts_confidence = btts_prob if btts_prob > 0.5 else 1 - btts_prob
        predictions["btts"] = {
            "market_type": "Both Teams To Score (BTTS)",
            "market_prediction": "Yes" if btts_prob > 0.5 else "No",
            "confidence_score": btts_confidence,
            "reason": f"BTTS probability: {btts_prob:.2f}"
        }

        # 5. Over/Under Total Goals
        if over25_prob > 0.7:
            predictions["over_under"] = {
                "market_type": "Over/Under Total Goals",
                "market_prediction": "Over 2.5",
                "confidence_score": over25_prob,
                "reason": f"High goal expectation: {home_xg + away_xg:.1f}"
            }
        elif over25_prob < 0.3:
            predictions["over_under"] = {
                "market_type": "Over/Under Total Goals",
                "market_prediction": "Under 2.5",
                "confidence_score": 1 - over25_prob,
                "reason": f"Low goal expectation: {home_xg + away_xg:.1f}"
            }
        else:
            predictions["over_under"] = {
                "market_type": "Over/Under Total Goals",
                "market_prediction": "Over 2.5",
                "confidence_score": over25_prob,
                "reason": f"Moderate goal expectation: {home_xg + away_xg:.1f}"
            }

        # 6. BTTS and Win combinations
        if btts_prob > 0.6 and home_score > away_score + 2:
            predictions["btts_win"] = {
                "market_type": "BTTS and Win",
                "market_prediction": f"BTTS and {home_team} to win",
                "confidence_score": min(btts_prob, home_score / 10),
                "reason": f"{home_team} likely to win with goals"
            }
        elif btts_prob > 0.6 and away_score > home_score + 2:
            predictions["btts_win"] = {
                "market_type": "BTTS and Win",
                "market_prediction": f"BTTS and {away_team} to win",
                "confidence_score": min(btts_prob, away_score / 10),
                "reason": f"{away_team} likely to win with goals"
            }
        elif btts_prob > 0.6 and draw_score > max(home_score, away_score):
            predictions["btts_win"] = {
                "market_type": "BTTS and Win",
                "market_prediction": "BTTS and Draw",
                "confidence_score": min(btts_prob, draw_score / 8),
                "reason": "Draw expected with both teams scoring"
            }

        # 7. Goal Range
        expected_goals = home_xg + away_xg
        if expected_goals < 1.5:
            predictions["goal_range"] = {
                "market_type": "Goal Range",
                "market_prediction": "0-1 goals",
                "confidence_score": max(0.3, 2 - expected_goals),
                "reason": f"Low scoring match expected: {expected_goals:.1f} goals"
            }
        elif expected_goals < 3:
            predictions["goal_range"] = {
                "market_type": "Goal Range",
                "market_prediction": "2-3 goals",
                "confidence_score": 0.6,
                "reason": f"Moderate scoring expected: {expected_goals:.1f} goals"
            }
        elif expected_goals < 5:
            predictions["goal_range"] = {
                "market_type": "Goal Range",
                "market_prediction": "4-6 goals",
                "confidence_score": min(0.8, expected_goals / 6),
                "reason": f"High scoring match expected: {expected_goals:.1f} goals"
            }
        else:
            predictions["goal_range"] = {
                "market_type": "Goal Range",
                "market_prediction": "7+ goals",
                "confidence_score": min(0.9, expected_goals / 8),
                "reason": f"Very high scoring match expected: {expected_goals:.1f} goals"
            }

        # 8. Correct Score (from top predictions)
        if scores and scores[0]["prob"] > 0.08:
            predictions["correct_score"] = {
                "market_type": "Correct Score",
                "market_prediction": scores[0]["score"],
                "confidence_score": scores[0]["prob"] * 2,  # Scale up for significance
                "reason": f"Most probable score: {scores[0]['prob']:.3f} probability"
            }

        # 9. Asian Handicap (simplified)
        goal_diff = abs(home_xg - away_xg)
        if goal_diff > 1:
            if home_xg > away_xg:
                predictions["asian_handicap"] = {
                    "market_type": "Asian Handicap",
                    "market_prediction": f"{home_team} -1",
                    "confidence_score": min(0.8, goal_diff / 2),
                    "reason": f"{home_team} expected to win by margin"
                }
            else:
                predictions["asian_handicap"] = {
                    "market_type": "Asian Handicap",
                    "market_prediction": f"{away_team} -1",
                    "confidence_score": min(0.8, goal_diff / 2),
                    "reason": f"{away_team} expected to win by margin"
                }

        # 10. Clean Sheet
        home_defense_strength = sum(1 for r in reasoning if "strong defense" in r and home_team in r)
        away_defense_strength = sum(1 for r in reasoning if "strong defense" in r and away_team in r)

        if home_defense_strength > 0:
            predictions["clean_sheet"] = {
                "market_type": "Clean Sheet",
                "market_prediction": f"{home_team} Clean Sheet",
                "confidence_score": min(0.7, home_defense_strength * 0.3),
                "reason": f"{home_team} strong defensive record"
            }
        elif away_defense_strength > 0:
            predictions["clean_sheet"] = {
                "market_type": "Clean Sheet",
                "market_prediction": f"{away_team} Clean Sheet",
                "confidence_score": min(0.7, away_defense_strength * 0.3),
                "reason": f"{away_team} strong defensive record"
            }

        # 11. Winner and Over/Under
        if home_score > away_score + 3 and over25_prob > 0.65:
            predictions["winner_over_under"] = {
                "market_type": "Winner & Over/Under",
                "market_prediction": f"{home_team} to win & Over 2.5",
                "confidence_score": min(home_score / 12, over25_prob),
                "reason": f"{home_team} strong favorite with high goals expected"
            }
        elif away_score > home_score + 3 and over25_prob > 0.65:
            predictions["winner_over_under"] = {
                "market_type": "Winner & Over/Under",
                "market_prediction": f"{away_team} to win & Over 2.5",
                "confidence_score": min(away_score / 12, over25_prob),
                "reason": f"{away_team} strong favorite with high goals expected"
            }

        # 12. Team Over/Under Goals
        home_expected = home_xg
        away_expected = away_xg

        if home_expected > 1.2:
            predictions["team_over_under"] = {
                "market_type": "Team Over/Under Goals",
                "market_prediction": f"{home_team} Over 1.5",
                "confidence_score": min(0.8, home_expected / 2),
                "reason": f"{home_team} expected {home_expected:.1f} goals"
            }
        elif away_expected > 1.2:
            predictions["team_over_under"] = {
                "market_type": "Team Over/Under Goals",
                "market_prediction": f"{away_team} Over 1.5",
                "confidence_score": min(0.8, away_expected / 2),
                "reason": f"{away_team} expected {away_expected:.1f} goals"
            }

        # 13. Winner and BTTS
        if home_score > away_score + 2 and btts_prob > 0.55:
            predictions["winner_btts"] = {
                "market_type": "Final Result & BTTS",
                "market_prediction": f"{home_team} to win & BTTS Yes",
                "confidence_score": min(home_score / 10, btts_prob),
                "reason": f"{home_team} likely to win with both teams scoring"
            }
        elif away_score > home_score + 2 and btts_prob > 0.55:
            predictions["winner_btts"] = {
                "market_type": "Final Result & BTTS",
                "market_prediction": f"{away_team} to win & BTTS Yes",
                "confidence_score": min(away_score / 10, btts_prob),
                "reason": f"{away_team} likely to win with both teams scoring"
            }

        return predictions

    @staticmethod
    def analyze(vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        MAIN PREDICTION ENGINE — Returns full market predictions
        """
        h2h_data = vision_data.get("h2h_data", {})
        standings = vision_data.get("standings", [])
        home_team = h2h_data.get("home_team")
        away_team = h2h_data.get("away_team")

        if not home_team or not away_team:
            return {"type": "SKIP", "confidence": "Low", "reason": "Missing teams"}

        home_form = [m for m in h2h_data.get("home_last_10_matches", []) if m][:10]
        away_form = [m for m in h2h_data.get("away_last_10_matches", []) if m][:10]
        h2h_raw = h2h_data.get("head_to_head", [])

        # Filter H2H to last ~18 months
        cutoff = datetime.now() - timedelta(days=540)
        h2h = []
        for m in h2h_raw:
            if not m:
                continue
            try:
                date_str = m.get("date", "")
                if date_str:
                    if "-" in date_str and len(date_str.split("-")[0]) == 4:
                        d = datetime.strptime(date_str, "%Y-%m-%d")
                    else:
                        d = datetime.strptime(date_str, "%d.%m.%Y")
                    if d >= cutoff:
                        h2h.append(m)
            except:
                h2h.append(m)  # keep if date parse fails

        # Generate all tags
        home_tags = RuleEngine.generate_form_tags(home_form, home_team, standings)
        away_tags = RuleEngine.generate_form_tags(away_form, away_team, standings)
        h2h_tags = RuleEngine.generate_h2h_tags(h2h, home_team, away_team)
        standings_tags = RuleEngine.generate_standings_tags(standings, home_team, away_team)

        # Prepare ML features
        ml_features = MLModel.prepare_features(vision_data)
        ml_prediction = MLModel.predict(ml_features) if ml_features else {"confidence": 0.5, "prediction": "UNKNOWN"}

        # Load learned weights
        weights = LearningEngine.load_weights()

        # Weighted rule voting using learned weights
        home_score = away_score = draw_score = over25_score = 0
        reasoning = []

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        # H2H signals with learned weights
        if any(t.startswith(f"{home_slug}_WINS_H2H") for t in h2h_tags):
            home_score += weights.get("h2h_home_win", 3); reasoning.append("H2H home strong")
        if any(t.startswith(f"{away_slug}_WINS_H2H") for t in h2h_tags):
            away_score += weights.get("h2h_away_win", 3); reasoning.append("H2H away strong")
        if any(t.startswith("H2H_D") for t in h2h_tags):
            draw_score += weights.get("h2h_draw", 4); reasoning.append("H2H drawish")
        if any(t in h2h_tags for t in ["H2H_O25", "H2H_O25_third"]):
            over25_score += weights.get("h2h_over25", 3)

        # Standings signals with learned weights
        if f"{home_slug}_TOP3" in standings_tags and f"{away_slug}_BOTTOM5" in standings_tags:
            home_score += weights.get("standings_top_vs_bottom", 6); reasoning.append("Top vs Bottom")
        if f"{away_slug}_TOP3" in standings_tags and f"{home_slug}_BOTTOM5" in standings_tags:
            away_score += weights.get("standings_top_vs_bottom", 6); reasoning.append("Top vs Bottom")
        if f"{home_slug}_TABLE_ADV8+" in standings_tags: home_score += weights.get("standings_table_advantage", 3)
        if f"{away_slug}_TABLE_ADV8+" in standings_tags: away_score += weights.get("standings_table_advantage", 3)
        if f"{home_slug}_GD_POS_STRONG" in standings_tags: home_score += weights.get("standings_gd_strong", 2); reasoning.append(f"{home_team} strong GD")
        if f"{away_slug}_GD_POS_STRONG" in standings_tags: away_score += weights.get("standings_gd_strong", 2); reasoning.append(f"{away_team} strong GD")
        if f"{home_slug}_GD_NEG_WEAK" in standings_tags: away_score += weights.get("standings_gd_weak", 2); reasoning.append(f"{home_team} weak GD")
        if f"{away_slug}_GD_NEG_WEAK" in standings_tags: home_score += weights.get("standings_gd_weak", 2); reasoning.append(f"{away_team} weak GD")

        # Form signals (goal-centric) with learned weights
        if f"{home_slug}_FORM_S2+" in home_tags: home_score += weights.get("form_score_2plus", 4); over25_score += 2; reasoning.append(f"{home_team} scores 2+")
        if f"{away_slug}_FORM_S2+" in away_tags: away_score += weights.get("form_score_2plus", 4); over25_score += 2; reasoning.append(f"{away_team} scores 2+")
        if f"{home_slug}_FORM_S3+" in home_tags: home_score += weights.get("form_score_3plus", 2); over25_score += 1
        if f"{away_slug}_FORM_S3+" in away_tags: away_score += weights.get("form_score_3plus", 2); over25_score += 1

        if f"{away_slug}_FORM_C2+" in away_tags: home_score += weights.get("form_concede_2plus", 4); over25_score += 2; reasoning.append(f"{away_team} concedes 2+")
        if f"{home_slug}_FORM_C2+" in home_tags: away_score += weights.get("form_concede_2plus", 4); over25_score += 2; reasoning.append(f"{home_team} concedes 2+")

        if f"{home_slug}_FORM_SNG" in home_tags: away_score += weights.get("form_no_score", 5); reasoning.append(f"{home_team} fails to score")
        if f"{away_slug}_FORM_SNG" in away_tags: home_score += weights.get("form_no_score", 5); reasoning.append(f"{away_team} fails to score")

        if f"{home_slug}_FORM_CS" in home_tags: home_score += weights.get("form_clean_sheet", 5); reasoning.append(f"{home_team} strong defense (CS)")
        if f"{away_slug}_FORM_CS" in away_tags: away_score += weights.get("form_clean_sheet", 5); reasoning.append(f"{away_team} strong defense (CS)")

        if any("vs_top" in t.lower() and "_w" in t.lower() for t in home_tags): home_score += weights.get("form_vs_top_win", 3); reasoning.append("Beats top teams")
        if any("vs_top" in t.lower() and "_w" in t.lower() for t in away_tags): away_score += weights.get("form_vs_top_win", 3); reasoning.append("Beats top teams")

        # Goal distribution & probabilities
        home_dist = RuleEngine.predict_goals_distribution(home_form, home_team, True)
        away_dist = RuleEngine.predict_goals_distribution(away_form, away_team, False)

        home_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in home_dist["goals_scored"].items())
        away_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in away_dist["goals_scored"].items())

        # Incorporate xG into voting for alignment with learned weights
        if home_xg > away_xg + 0.5:
            home_score += weights.get("xg_advantage", 3); reasoning.append("Home xG advantage")
        elif away_xg > home_xg + 0.5:
            away_score += weights.get("xg_advantage", 3); reasoning.append("Away xG advantage")
        elif abs(home_xg - away_xg) < 0.3:
            draw_score += weights.get("xg_draw", 2); reasoning.append("Close xG suggests draw")

        keys = ["0", "1", "2", "3+"]
        btts_prob = sum(home_dist["goals_scored"].get(h,0) * away_dist["goals_scored"].get(a,0)
                        for h in keys for a in keys if h != "0" and a != "0")

        over25_prob = sum(home_dist["goals_scored"].get(h,0) * away_dist["goals_scored"].get(a,0)
                          for h in keys for a in keys
                          if int(h.replace("3+", "3")) + int(a.replace("3+", "3")) > 2)

        # Top correct scores
        scores = []
        for hg in "01233+":
            for ag in "01233+":
                p = home_dist["goals_scored"].get(hg, 0) * away_dist["goals_scored"].get(ag, 0)
                if p > 0.03:
                    scores.append({"score": f"{hg.replace('3+', '3+')}-{ag.replace('3+', '3+')}", "prob": round(p, 3)})
        scores.sort(key=lambda x: x["prob"], reverse=True)

        # Final decision logic
        prediction = "SKIP"
        confidence = "Low"

        if not reasoning:
            return {
                "type": "SKIP",
                "confidence": "Low",
                "reason": ["No strong signal"],
                "xg_home": round(home_xg, 2),
                "xg_away": round(away_xg, 2),
                "btts": "YES" if btts_prob > 0.6 else "NO" if btts_prob < 0.4 else "50/50",
                "over_2.5": "YES" if over25_prob > 0.65 else "NO" if over25_prob < 0.45 else "50/50",
                "best_score": scores[0]["score"] if scores else "1-1",
                "top_scores": scores[:5],
                "home_tags": home_tags,
                "away_tags": away_tags,
                "h2h_tags": h2h_tags,
                "standings_tags": standings_tags,
                "h2h_n": len(h2h),
                "home_form_n": len(home_form),
                "away_form_n": len(away_form),
            }

        # Determine base confidence
        if draw_score > max(home_score, away_score) and draw_score >= 4:
            prediction = "DRAW"
            base_confidence = "High" if draw_score >= 6 else "Medium"
        elif home_score > away_score + 3:
            prediction = "HOME_WIN"
            base_confidence = "Very High" if home_score >= 12 else "High"
            if over25_prob > 0.65:
                prediction = "HOME_WIN_AND_OVER_2.5"
        elif away_score > home_score + 3:
            prediction = "AWAY_WIN"
            base_confidence = "Very High" if away_score >= 12 else "High"
            if over25_prob > 0.65:
                prediction = "AWAY_WIN_AND_OVER_2.5"
        elif over25_prob > 0.75:
            prediction = "OVER_2.5"
            base_confidence = "Very High" if over25_prob > 0.85 else "High"
        else:
            base_confidence = "Low"

        # Apply learned confidence calibration
        confidence_calibration = weights.get("confidence_calibration", {})
        calibrated_score = confidence_calibration.get(base_confidence, 0.5)

        # Adjust confidence based on calibration
        if calibrated_score > 0.7:
            confidence = "Very High"
        elif calibrated_score > 0.55:
            confidence = "High"
        elif calibrated_score > 0.45:
            confidence = "Medium"
        else:
            confidence = "Low"

        # Alignment check: Skip if prediction opposes xG significantly
        if prediction.startswith("HOME_WIN") and away_xg > home_xg + 0.5:
            prediction = "SKIP"
            confidence = "Low"
            reasoning.append("xG opposes home win")
        elif prediction.startswith("AWAY_WIN") and home_xg > away_xg + 0.5:
            prediction = "SKIP"
            confidence = "Low"
            reasoning.append("xG opposes away win")
        elif prediction == "DRAW" and abs(home_xg - away_xg) > 1.0:
            prediction = "SKIP"
            confidence = "Low"
            reasoning.append("xG opposes draw")

        # Incorporate ML confidence if available
        final_confidence = confidence
        if ml_prediction["prediction"] != "UNKNOWN":
            ml_confidence_score = ml_prediction["confidence"]
            # Blend rule-based and ML confidence
            blended_confidence = (calibrated_score + ml_confidence_score) / 2

            if blended_confidence > 0.7:
                final_confidence = "Very High"
            elif blended_confidence > 0.55:
                final_confidence = "High"
            elif blended_confidence > 0.45:
                final_confidence = "Medium"
            else:
                final_confidence = "Low"

        # Generate comprehensive betting market predictions with dynamic team names
        betting_markets = RuleEngine.generate_betting_market_predictions(
            home_team, away_team, home_score, away_score, draw_score, btts_prob, over25_prob,
            scores, home_xg, away_xg, reasoning
        )

        # Prioritize safer markets: Double Chance > BTTS > Over/Under > Straight Win
        market_priority = {
            "double_chance": 10,  # Safest - one of two outcomes must happen
            "draw_no_bet": 9,     # Very safe - draw eliminated
            "btts": 8,            # Safe - both teams likely to score
            "over_under": 7,      # Safe - goals are common
            "clean_sheet": 6,     # Moderately safe
            "goal_range": 5,      # Based on xG expectations
            "btts_win": 4,        # Combined but safer than straight win
            "correct_score": 3,   # Specific but can be high probability
            "1X2": 2,            # Straight result - least safe
            "asian_handicap": 1,  # Requires margin - least safe
        }

        # Score each market considering both confidence and safety
        scored_predictions = []
        for market_key, prediction in betting_markets.items():
            confidence_score = prediction.get("confidence_score", 0)
            safety_score = market_priority.get(market_key, 1)

            # For straight wins (1X2), reduce score if confidence is low
            if market_key == "1X2" and confidence_score < 0.7:
                safety_score = 0.5  # Much less attractive for low confidence straight wins

            final_score = confidence_score * safety_score
            scored_predictions.append((final_score, prediction))

        # Select the highest scoring prediction (best balance of confidence + safety)
        best_prediction = max(scored_predictions, key=lambda x: x[0])[1]

        # Format prediction with market context for clarity
        market_type_short = best_prediction["market_type"].split("(")[0].strip()  # Remove parentheses
        prediction_text = best_prediction["market_prediction"]

        # For simple Yes/No markets, add context
        if prediction_text in ["Yes", "No"] and "BTTS" in market_type_short:
            formatted_prediction = f"BTTS {prediction_text}"
        elif prediction_text in ["Yes", "No"]:
            formatted_prediction = f"{market_type_short} {prediction_text}"
        else:
            # For complex predictions, keep as is but ensure clarity
            formatted_prediction = prediction_text

        return {
            "type": formatted_prediction,
            "market_type": best_prediction["market_type"],
            "confidence": final_confidence,
            "reason": reasoning[:3],
            "xg_home": round(home_xg, 2),
            "xg_away": round(away_xg, 2),
            "btts": "YES" if btts_prob > 0.6 else "NO" if btts_prob < 0.4 else "50/50",
            "over_2.5": "YES" if over25_prob > 0.65 else "NO" if over25_prob < 0.45 else "50/50",
            "best_score": scores[0]["score"] if scores else "1-1",
            "top_scores": scores[:5],
            "home_tags": home_tags,
            "away_tags": away_tags,
            "h2h_tags": h2h_tags,
            "standings_tags": standings_tags,
            "ml_confidence": ml_prediction.get("confidence", 0.5),
            "betting_markets": betting_markets,
            "h2h_n": len(h2h),
            "home_form_n": len(home_form),
            "away_form_n": len(away_form),
        }
