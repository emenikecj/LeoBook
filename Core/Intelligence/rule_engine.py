# rule_engine.py: rule_engine.py: Logic-based prediction engine.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: RuleEngine

"""
Rule Engine Module
Core rule-based prediction engine for LeoBook.
Handles main analysis combining rules, xG, ML, and market selection.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import numpy as np

from .learning_engine import LearningEngine
from .tag_generator import TagGenerator
from .goal_predictor import GoalPredictor
from .betting_markets import BettingMarkets
from .rule_config import RuleConfig

class RuleEngine:
    @staticmethod
    def analyze(vision_data: Dict[str, Any], config: RuleConfig = None) -> Dict[str, Any]:
        """
        MAIN PREDICTION ENGINE — Returns full market predictions
        Accepts optional RuleConfig for custom logic.
        """
        if config is None:
            config = RuleConfig()
            
        h2h_data = vision_data.get("h2h_data", {})
        standings = vision_data.get("standings", [])
        home_team = h2h_data.get("home_team")
        away_team = h2h_data.get("away_team")
        region_league = h2h_data.get("region_league", "GLOBAL")

        if not home_team or not away_team:
            return {"type": "SKIP", "confidence": "Low", "reason": "Missing teams"}

        # Scope filtering: skip matches outside this engine's scope
        if not config.matches_scope(region_league, home_team, away_team):
            return {"type": "SKIP", "confidence": "Low", "reason": "Outside engine scope"}

        home_form = [m for m in h2h_data.get("home_last_10_matches", []) if m][:10]
        away_form = [m for m in h2h_data.get("away_last_10_matches", []) if m][:10]
        h2h_raw = h2h_data.get("head_to_head", [])

        # Filter H2H based on config
        cutoff = datetime.now() - timedelta(days=config.h2h_lookback_days)
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

        # Generate all tags using TagGenerator
        home_tags = TagGenerator.generate_form_tags(home_form, home_team, standings)
        away_tags = TagGenerator.generate_form_tags(away_form, away_team, standings)
        h2h_tags = TagGenerator.generate_h2h_tags(h2h, home_team, away_team)
        standings_tags = TagGenerator.generate_standings_tags(standings, home_team, away_team)

        # Goal distribution
        home_dist = GoalPredictor.predict_goals_distribution(home_form, home_team, True)
        away_dist = GoalPredictor.predict_goals_distribution(away_form, away_team, False)

        home_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in home_dist["goals_scored"].items())
        away_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in away_dist["goals_scored"].items())

        # ML prediction removed in cleanup
        ml_prediction = {"confidence": 0.5, "prediction": "UNKNOWN"}

        # --- LOAD REGION-SPECIFIC LEARNED WEIGHTS ---
        weights = LearningEngine.load_weights(region_league)

        # Weighted rule voting using config
        home_score = away_score = draw_score = over25_score = 0
        reasoning = []

        # Incorporate xG into voting (learned weights with config fallback)
        if home_xg > away_xg + 0.5:
            home_score += weights.get("xg_advantage", config.xg_advantage)
            reasoning.append(f"{home_team} has xG advantage")
        elif away_xg > home_xg + 0.5:
            away_score += weights.get("xg_advantage", config.xg_advantage)
            reasoning.append(f"{away_team} has xG advantage")
        elif abs(home_xg - away_xg) < 0.3:
            draw_score += weights.get("xg_draw", config.xg_draw)
            reasoning.append("Close xG suggests draw")

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        # H2H signals
        if any(t.startswith(f"{home_slug}_WINS_H2H") for t in h2h_tags):
            home_score += weights.get("h2h_home_win", config.h2h_home_win); reasoning.append(f"{home_team} strong in H2H")
        if any(t.startswith(f"{away_slug}_WINS_H2H") for t in h2h_tags):
            away_score += weights.get("h2h_away_win", config.h2h_away_win); reasoning.append(f"{away_team} strong in H2H")
        if any(t.startswith("H2H_D") for t in h2h_tags):
            draw_score += weights.get("h2h_draw", config.h2h_draw); reasoning.append("H2H suggests Draw")
        if any(t in h2h_tags for t in ["H2H_O25", "H2H_O25_third"]):
            over25_score += weights.get("h2h_over25", config.h2h_over25)

        # Standings signals
        if f"{home_slug}_TOP3" in standings_tags and f"{away_slug}_BOTTOM5" in standings_tags:
            home_score += weights.get("standings_top_vs_bottom", config.standings_top_vs_bottom); reasoning.append(f"Top ({home_team}) vs Bottom ({away_team})")
        if f"{away_slug}_TOP3" in standings_tags and f"{home_slug}_BOTTOM5" in standings_tags:
            away_score += weights.get("standings_top_vs_bottom", config.standings_top_vs_bottom); reasoning.append(f"Top ({away_team}) vs Bottom ({home_team})")
        
        if f"{home_slug}_TABLE_ADV8+" in standings_tags: home_score += weights.get("standings_table_advantage", config.standings_table_advantage)
        if f"{away_slug}_TABLE_ADV8+" in standings_tags: away_score += weights.get("standings_table_advantage", config.standings_table_advantage)
        
        if f"{home_slug}_GD_POS_STRONG" in standings_tags: home_score += weights.get("standings_gd_strong", config.standings_gd_strong); reasoning.append(f"{home_team} has strong GD")
        if f"{away_slug}_GD_POS_STRONG" in standings_tags: away_score += weights.get("standings_gd_strong", config.standings_gd_strong); reasoning.append(f"{away_team} has strong GD")
        if f"{home_slug}_GD_NEG_WEAK" in standings_tags: away_score += weights.get("standings_gd_weak", config.standings_gd_weak); reasoning.append(f"{home_team} has weak GD")
        if f"{away_slug}_GD_NEG_WEAK" in standings_tags: home_score += weights.get("standings_gd_weak", config.standings_gd_weak); reasoning.append(f"{away_team} has weak GD")

        # Form signals
        if f"{home_slug}_FORM_S2+" in home_tags: home_score += weights.get("form_score_2plus", config.form_score_2plus); over25_score += 2; reasoning.append(f"{home_team} scores 2+ often")
        if f"{away_slug}_FORM_S2+" in away_tags: away_score += weights.get("form_score_2plus", config.form_score_2plus); over25_score += 2; reasoning.append(f"{away_team} scores 2+ often")
        if f"{home_slug}_FORM_S3+" in home_tags: home_score += weights.get("form_score_3plus", config.form_score_3plus); over25_score += 1
        if f"{away_slug}_FORM_S3+" in away_tags: away_score += weights.get("form_score_3plus", config.form_score_3plus); over25_score += 1

        if f"{away_slug}_FORM_C2+" in away_tags: home_score += weights.get("form_concede_2plus", config.form_concede_2plus); over25_score += 2; reasoning.append(f"{away_team} concedes 2+ often")
        if f"{home_slug}_FORM_C2+" in home_tags: away_score += weights.get("form_concede_2plus", config.form_concede_2plus); over25_score += 2; reasoning.append(f"{home_team} concedes 2+ often")

        if f"{home_slug}_FORM_SNG" in home_tags: away_score += weights.get("form_no_score", config.form_no_score); reasoning.append(f"{home_team} fails to score")
        if f"{away_slug}_FORM_SNG" in away_tags: home_score += weights.get("form_no_score", config.form_no_score); reasoning.append(f"{away_team} fails to score")

        if f"{home_slug}_FORM_CS" in home_tags: home_score += weights.get("form_clean_sheet", config.form_clean_sheet); reasoning.append(f"{home_team} has strong defense")
        if f"{away_slug}_FORM_CS" in away_tags: away_score += weights.get("form_clean_sheet", config.form_clean_sheet); reasoning.append(f"{away_team} has strong defense")

        if any("vs_top" in t.lower() and "_w" in t.lower() for t in home_tags): home_score += weights.get("form_vs_top_win", config.form_vs_top_win)
        if any("vs_top" in t.lower() and "_w" in t.lower() for t in away_tags): away_score += weights.get("form_vs_top_win", config.form_vs_top_win)

        # Calculate probabilities
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

        # Generate comprehensive betting market predictions
        betting_markets = BettingMarkets.generate_betting_market_predictions(
            home_team, away_team, home_score, away_score, draw_score, btts_prob, over25_prob,
            scores, home_xg, away_xg, reasoning
        )

        
        # --- SELECTION STRATEGY: Use config's risk preference ---
        selection = BettingMarkets.select_best_market(betting_markets, risk_preference=config.risk_preference)
        
        best_prediction = None
        if selection:
             # Find the full market object
             for k, v in betting_markets.items():
                 if v["market_type"] == selection["market_type"] and v["market_prediction"] == selection["prediction"]:
                     best_prediction = v
                     break
        
        # Fallback if no safe bet found
        if not best_prediction and betting_markets:
             best_prediction = list(betting_markets.values())[0]

        if not best_prediction:
             return {"type": "SKIP", "confidence": "Low", "reason": ["No valid markets"]}

        # Format prediction text
        prediction_text = best_prediction["market_prediction"]
        
        # Confidence Calibration (Manual Fallback)
        confidence_calibration = weights.get("confidence_calibration", {})
        # Map score to category
        raw_conf = best_prediction.get("confidence_score", 0.5)
        
        if raw_conf > 0.8: base_conf = "Very High"
        elif raw_conf > 0.65: base_conf = "High"
        elif raw_conf > 0.5: base_conf = "Medium"
        else: base_conf = "Low"
        
        calibrated_score = confidence_calibration.get(base_conf, raw_conf) # Use calibrated expectation if available
        
        # Final Confidence Label
        if calibrated_score > 0.75: final_confidence = "Very High"
        elif calibrated_score > 0.60: final_confidence = "High"
        elif calibrated_score > 0.45: final_confidence = "Medium"
        else: final_confidence = "Low"

        # --- DATA INTEGRITY SANITY CHECKS ---
        # 1. Contradiction Check: Heavily favored by xG vs Prediction
        primary_pred = prediction_text.lower()
        if f"{away_team.lower()} to win" in primary_pred or f"{away_team.lower()} or draw" in primary_pred:
            if home_xg > away_xg + 1.25 and "over 0.5" not in primary_pred: # Allow over markets, block win markets
                reasoning.append(f"WARNING: Contradicts xG ({home_xg} vs {away_xg})")
                final_confidence = "Low"
                # Optionally forceful SKIP
                if "win" in primary_pred:
                     return {"type": "SKIP", "confidence": "Low", "reason": [f"Contradiction: Pred Away Win but {home_team} xG dominance"]}

        if f"{home_team.lower()} to win" in primary_pred or f"{home_team.lower()} or draw" in primary_pred:
            if away_xg > home_xg + 1.25 and "over 0.5" not in primary_pred:
                 reasoning.append(f"WARNING: Contradicts xG ({home_xg} vs {away_xg})")
                 final_confidence = "Low"
                 if "win" in primary_pred:
                     return {"type": "SKIP", "confidence": "Low", "reason": [f"Contradiction: Pred Home Win but {away_team} xG dominance"]}

        # 2. Score sanity
        if scores:
             most_prob_score = scores[0]["score"]
             if most_prob_score == "0-0" and "over 2.5" in primary_pred:
                 final_confidence = "Low" # Contradiction


        # Calculate final recommendation_score for the UI "TOP PREDICTIONS" section
        # Formula: Confidence Score (0-1) * 100, plus bonuses for xG clarity
        raw_confidence = best_prediction.get("confidence_score", 0.5)
        rec_score = int(raw_confidence * 85) # Base weight
        if (home_xg + away_xg) > 2.5: rec_score += 10
        if final_confidence == "Very High": rec_score += 5
        
        return {
            "market_prediction": prediction_text,
            "type": prediction_text,
            "market_type": best_prediction["market_type"],
            "confidence": final_confidence,
            "recommendation_score": min(rec_score, 100),
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
            "total_xg": round(home_xg + away_xg, 2),
        }
