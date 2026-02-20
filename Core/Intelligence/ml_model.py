# ml_model.py: ml_model.py: Machine Learning component for ensemble predictions.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: MLModel

"""
ML Model Module
Handles machine learning predictions, model training, and feature engineering.
Responsible for ensemble ML-based prediction capabilities.
"""

import os
import joblib
import numpy as np
from typing import Dict, Any, Optional
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier


class MLModel:
    """Machine Learning component for ensemble predictions"""

    MODEL_DIR = "Data/Models"
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

        # xG calculation (simplified - would need RuleEngine for full calculation)
        home_dist_scored = {"0": 0.4, "1": 0.3, "2": 0.2, "3+": 0.1}  # Placeholder
        away_dist_scored = {"0": 0.4, "1": 0.3, "2": 0.2, "3+": 0.1}  # Placeholder

        home_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in home_dist_scored.items())
        away_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in away_dist_scored.items())

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
    def train_models() -> bool:
        """Train ML models using historical prediction data"""
        from Data.Access.db_helpers import PREDICTIONS_CSV
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
        from sklearn.model_selection import cross_val_score
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
