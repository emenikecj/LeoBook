# betting_markets.py: betting_markets.py: Analysis of specific betting market probabilities.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: BettingMarkets

"""
Betting Markets Module
Generates predictions for comprehensive betting markets with a focus on safety and certainty.
"""

from typing import List, Dict, Any

class BettingMarkets:
    """Generates predictions for various betting markets"""

    @staticmethod
    def generate_betting_market_predictions(
        home_team: str, away_team: str, home_score: float, away_score: float, draw_score: float,
        btts_prob: float, over25_prob: float, scores: List[Dict], home_xg: float, away_xg: float,
        reasoning: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate predictions for comprehensive betting markets.
        Returns a dictionary of market predictions with confidence scores.
        """
        predictions: Dict[str, Dict[str, Any]] = {}

        # Helper function to calculate confidence score
        def calc_confidence(base_score: float, threshold: float = 0.5) -> float:
            if base_score > threshold:
                return min(base_score / threshold, 1.0)
            return (base_score / threshold) * 0.5

        # Calculate Over 1.5 Probability from score distribution
        over15_prob = 0.0
        total_prob_analyzed = 0.0
        if scores:
            for s in scores:
                try:
                    score_str = s['score']
                    h_str, a_str = score_str.split('-')
                    h = 3.5 if '3+' in h_str else float(h_str)
                    a = 3.5 if '3+' in a_str else float(a_str)
                    prob = s['prob']
                    total_prob_analyzed += prob
                    if h + a > 1.5:
                        over15_prob += prob
                except Exception:
                    pass
            
            if total_prob_analyzed > 0:
                over15_prob /= total_prob_analyzed
            else:
                over15_prob = min(over25_prob + 0.2, 0.95)
        else:
            over15_prob = min(over25_prob + 0.2, 0.95)

        # 1. Full Time Result (1X2)
        outcomes = [
            (draw_score, "Draw", "Draw most likely outcome"),
            (home_score, f"{home_team} to win", f"{home_team} favored to win"),
            (away_score, f"{away_team} to win", f"{away_team} favored to win")
        ]
        best_score, prediction, reason = max(outcomes, key=lambda x: x[0])
        predictions["1X2"] = {
            "market_type": "Full Time Result (1X2)",
            "market_prediction": prediction,
            "confidence_score": calc_confidence(best_score, 20 if prediction != "Draw" else 18),
            "reason": reason
        }

        # 2. Double Chance
        dc_boost = 1.25 if any("draw" in r.lower() for r in reasoning) else 1.0

        if home_score + draw_score > away_score + 2:
            base_conf = calc_confidence((home_score + draw_score) / 2, 12)
            if away_xg > home_xg + 0.5:
                base_conf *= 0.7
            dc_pred = f"{home_team} or Draw"
            dc_reason = f"{home_team} unlikely to lose"
        elif away_score + draw_score > home_score + 2:
            base_conf = calc_confidence((away_score + draw_score) / 2, 12)
            if home_xg > away_xg + 0.5:
                base_conf *= 0.7
            dc_pred = f"{away_team} or Draw"
            dc_reason = f"{away_team} unlikely to lose"
        else:
            if any("close xg" in r.lower() for r in reasoning):
                stronger_side = home_team if home_score >= away_score else away_team
                dc_pred = f"{stronger_side} or Draw"
                dc_reason = f"Close match favors DC ({stronger_side})"
                base_conf = 0.85
            else:
                dc_pred = f"{home_team} or {away_team}"
                dc_reason = "Draw unlikely (12)"
                base_conf = calc_confidence(max(home_score, away_score), 10)

        predictions["double_chance"] = {
            "market_type": "Double Chance",
            "market_prediction": dc_pred,
            "confidence_score": min(base_conf * dc_boost, 0.98),
            "reason": dc_reason
        }

        # 3. Draw No Bet
        if home_score > away_score + 3:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": f"{home_team} to win (DNB)",
                "confidence_score": calc_confidence(home_score - away_score, 8),
                "reason": f"{home_team} clear favorite"
            }
        elif away_score > home_score + 3:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": f"{away_team} to win (DNB)",
                "confidence_score": calc_confidence(away_score - home_score, 8),
                "reason": f"{away_team} clear favorite"
            }

        # 4. Over/Under Markets
        under_penalty = 0.6 if any("scores 2+" in r for r in reasoning) else 1.0

        if over15_prob > 0.75:
            predictions["over_1.5"] = {
                "market_type": "Over/Under 1.5 Goals",
                "market_prediction": "Over 1.5",
                "confidence_score": over15_prob,
                "reason": "Safe goal expectation"
            }

        if over25_prob > 0.65:
            predictions["over_under"] = {
                "market_type": "Over/Under 2.5 Goals",
                "market_prediction": "Over 2.5",
                "confidence_score": over25_prob,
                "reason": f"High goal expectation: {home_xg + away_xg:.1f} xG"
            }
        elif over25_prob < 0.35:
            predictions["over_under"] = {
                "market_type": "Over/Under 2.5 Goals",
                "market_prediction": "Under 2.5",
                "confidence_score": (1 - over25_prob) * under_penalty,
                "reason": f"Low goal expectation: {home_xg + away_xg:.1f} xG"
            }

        # 5. Team Goals (Safe Options)
        if home_xg > 1.3:
            predictions["home_over_0.5"] = {
                "market_type": "Home Team Over 0.5 Goals",
                "market_prediction": f"{home_team} Over 0.5",
                "confidence_score": 0.85,
                "reason": f"{home_team} expected to score"
            }
        if away_xg > 1.3:
            predictions["away_over_0.5"] = {
                "market_type": "Away Team Over 0.5 Goals",
                "market_prediction": f"{away_team} Over 0.5",
                "confidence_score": 0.85,
                "reason": f"{away_team} expected to score"
            }

        # 6. BTTS
        btts_conf = btts_prob if btts_prob > 0.5 else 1 - btts_prob
        if any("scores 2+" in r for r in reasoning) and btts_prob > 0.45:
            btts_conf = max(btts_conf, 0.75)

        predictions["btts"] = {
            "market_type": "Both Teams To Score (BTTS)",
            "market_prediction": "BTTS Yes" if btts_prob > 0.5 else "BTTS No",
            "confidence_score": btts_conf,
            "reason": f"BTTS probability: {btts_prob:.2f}"
        }

        # 7. Winner and BTTS
        if home_score > away_score + 2 and btts_prob > 0.6:
            predictions["winner_btts"] = {
                "market_type": "Winner & BTTS",
                "market_prediction": f"{home_team} to win & BTTS Yes",
                "confidence_score": min(home_score / 12, btts_prob) * 0.9,
                "reason": f"{home_team} likely to win with both teams scoring"
            }
        elif away_score > home_score + 2 and btts_prob > 0.6:
            predictions["winner_btts"] = {
                "market_type": "Winner & BTTS",
                "market_prediction": f"{away_team} to win & BTTS Yes",
                "confidence_score": min(away_score / 12, btts_prob) * 0.9,
                "reason": f"{away_team} likely to win with both teams scoring"
            }

        return predictions

    @staticmethod
    def select_best_market(predictions: Dict[str, Dict[str, Any]], risk_preference: str = "medium") -> Dict[str, Any]:
        """
        Select the single best market with strong logical consistency and preference for safer options.
        """
        if not predictions:
            return {}

        def format_selection(market: Dict[str, Any], key_name: str) -> Dict[str, Any]:
            return {
                "market_key": key_name,
                "market_type": market["market_type"],
                "prediction": market["market_prediction"],
                "confidence": market["confidence_score"],
                "reason": market["reason"]
            }

        dc = predictions.get("double_chance")

        # Logical overrides
        all_reasons_lower = " ".join(p.get("reason", "") for p in predictions.values()).lower()
        goals_expected = "scores 2+" in all_reasons_lower or "concedes 2+" in all_reasons_lower

        # 1. Strong draw signal → Double Chance
        if dc and ("draw" in dc.get("reason", "").lower() or "close xg" in dc.get("reason", "").lower()):
            if dc["confidence_score"] > 0.65:
                return format_selection(dc, "logical_override_draw")

        # 2. Clear goal expectation → Over or BTTS Yes
        if goals_expected:
            over25 = predictions.get("over_under")
            btts = predictions.get("btts")
            over15 = predictions.get("over_1.5")

            if over25 and "Over" in over25["market_prediction"] and over25["confidence_score"] > 0.6:
                return format_selection(over25, "logical_override_goals")
            if btts and "Yes" in btts["market_prediction"] and btts["confidence_score"] > 0.6:
                return format_selection(btts, "logical_override_goals")
            if over15 and over15["confidence_score"] > 0.7:
                return format_selection(over15, "logical_override_goals_safe")

        # Detect directional Double Chance (X1 or X2, not 12)
        has_directional_dc = False
        if dc and " or Draw" in dc["market_prediction"]:
            has_directional_dc = True

        # High-confidence safe markets first
        high_conf = [p for p in predictions.values() if p["confidence_score"] >= 0.80]
        if high_conf:
            high_conf.sort(key=lambda x: x["confidence_score"], reverse=True)
            valid = []
            for c in high_conf:
                if goals_expected and "Under" in c["market_prediction"]:
                    continue
                if "BTTS No" in c["market_prediction"] and has_directional_dc:
                    continue
                valid.append(c)

            if valid:
                # Prefer explicitly safe market types
                safe_types = ["Double Chance", "Over 1.5 Goals", "Team Over 0.5", "Draw No Bet"]
                best_safe = next((m for m in valid if any(st in m["market_type"] for st in safe_types)), None)
                selected = best_safe or valid[0]
                return format_selection(selected, "best_safe" if best_safe else "best_high_conf")

        # Medium-confidence safe markets
        safe_keys = ["double_chance", "over_1.5", "draw_no_bet", "home_over_0.5", "away_over_0.5"]
        safe_cands = [predictions[k] for k in safe_keys if k in predictions and predictions[k]["confidence_score"] > 0.60]
        if safe_cands:
            safe_cands.sort(key=lambda x: x["confidence_score"], reverse=True)
            for cand in safe_cands:
                if goals_expected and "Under" in cand["market_prediction"]:
                    continue
                return format_selection(cand, "safe_bet")

        # Fallback – avoid BTTS No if good DC exists
        sorted_all = sorted(predictions.values(), key=lambda x: x["confidence_score"], reverse=True)
        top = sorted_all[0]
        if "BTTS No" in top["market_prediction"] and has_directional_dc and dc["confidence_score"] > 0.55:
            return format_selection(dc, "fallback_swap_dc")

        return format_selection(top, "fallback")
