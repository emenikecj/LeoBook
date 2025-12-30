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
        predictions = {}

        # Helper function to calculate confidence score
        def calc_confidence(base_score: float, threshold: float = 0.5) -> float:
            return min(base_score / threshold, 1.0) if base_score > threshold else base_score / threshold * 0.5

        # Calculate SAFE metrics
        # Over 1.5 Probability using top scores
        over15_prob = 0.0
        total_prob_analyzed = 0.0
        if scores:
            for s in scores:
                try:
                    score_str = s['score']
                    h, a = score_str.split('-')
                    # handle 3+
                    h = 3.5 if '3+' in h else float(h)
                    a = 3.5 if '3+' in a else float(a)
                    total_prob_analyzed += s['prob']
                    if h + a > 1.5:
                        over15_prob += s['prob']
                except: pass
            
            # Normalize if we only looked at top N scores
            if total_prob_analyzed > 0:
                over15_prob = over15_prob / total_prob_analyzed
            else:
                over15_prob = min(over25_prob + 0.2, 0.95) # Fallback heuristic
        else:
             over15_prob = min(over25_prob + 0.2, 0.95)

        # 1. Full Time Result (1X2)
        max_score = max(home_score, away_score, draw_score)
        if draw_score == max_score:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": "Draw",
                "confidence_score": calc_confidence(draw_score, 18), # Increased threshold for higher weights
                "reason": "Draw most likely outcome"
            }
        elif home_score == max_score:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": f"{home_team} to win",
                "confidence_score": calc_confidence(home_score, 20), # Increased threshold for higher weights
                "reason": f"{home_team} favored to win"
            }
        else:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": f"{away_team} to win",
                "confidence_score": calc_confidence(away_score, 20), # Increased threshold for higher weights
                "reason": f"{away_team} favored to win"
            }

        # 2. Double Chance - LOGIC REFACTOR
        # Priority Rule: If match is tight (Draw likely), prioritize DC over Under/Over unless purely defensive
        dc_boost = 1.0
        if any("draw" in r.lower() for r in reasoning):
            dc_boost = 1.25 # Boost DC confidence if Draw is suspected
        
        if home_score + draw_score > away_score + 2:
            base_conf = calc_confidence((home_score + draw_score) / 2, 12)
            if away_xg > home_xg + 0.5: base_conf *= 0.7 
            
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{home_team} or Draw",
                "confidence_score": min(base_conf * dc_boost, 0.98),
                "reason": f"{home_team} unlikely to lose"
            }
        elif away_score + draw_score > home_score + 2:
            base_conf = calc_confidence((away_score + draw_score) / 2, 12)
            if home_xg > away_xg + 0.5: base_conf *= 0.7
            
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{away_team} or Draw",
                "confidence_score": min(base_conf * dc_boost, 0.98),
                "reason": f"{away_team} unlikely to lose"
            }
        else:
             # If "Close xG suggests draw"
             if any("close xg" in r.lower() for r in reasoning):
                  # Valid DC option if not 12
                  # Actually, in close games, Home or Draw is often the safest bet if Home has ANY edge
                  stronger_side = home_team if home_score >= away_score else away_team
                  predictions["double_chance"] = {
                        "market_type": "Double Chance",
                        "market_prediction": f"{stronger_side} or Draw",
                        "confidence_score": 0.85, # High confidence for DC in tight games
                        "reason": f"Close match favors DC ({stronger_side})"
                  }
             else:
                predictions["double_chance"] = {
                    "market_type": "Double Chance",
                    "market_prediction": f"{home_team} or {away_team}",
                    "confidence_score": calc_confidence(max(home_score, away_score), 10),
                    "reason": "Draw unlikely (12)"
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

        # 4. BTTS (Both Teams To Score)
        # Boost BTTS if "scores 2+ often" appears for both or reasoning suggests high goals
        btts_conf = btts_prob if btts_prob > 0.5 else 1 - btts_prob
        if any("scores 2+" in r for r in reasoning) and btts_prob > 0.45:
             btts_conf = max(btts_conf, 0.75) # Boost
        
        predictions["btts"] = {
            "market_type": "Both Teams To Score (BTTS)",
            "market_prediction": "BTTS Yes" if btts_prob > 0.5 else "BTTS No",
            "confidence_score": btts_conf,
            "reason": f"BTTS probability: {btts_prob:.2f}"
        }

        # 5. Over/Under Markets
        # Penalize Under 2.5 if reasoning says "scores 2+ often"
        under_penalty = 1.0
        if any("scores 2+" in r for r in reasoning):
            under_penalty = 0.6  # Penalize Under markets significantly
            
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
                "reason": f"High goal expectation: {home_xg + away_xg:.1f}"
            }
        elif over25_prob < 0.35:
            # Apply penalty to Under prediction confidence
            predictions["over_under"] = {
                "market_type": "Over/Under 2.5 Goals",
                "market_prediction": "Under 2.5",
                "confidence_score": (1 - over25_prob) * under_penalty,
                "reason": f"Low goal expectation: {home_xg + away_xg:.1f}"
            }

        # 6. Team Goals (Safe Options)
        if home_xg > 1.3:
            predictions["home_over_0.5"] = {
                "market_type": "Home Team Goals",
                "market_prediction": f"{home_team} Over 0.5",
                "confidence_score": 0.85, 
                "reason": f"{home_team} expected to score"
            }
        if away_xg > 1.3:
            predictions["away_over_0.5"] = {
                "market_type": "Away Team Goals",
                "market_prediction": f"{away_team} Over 0.5",
                "confidence_score": 0.85, 
                "reason": f"{away_team} expected to score"
            }

        # 7. Winner and BTTS (Risky)
        if home_score > away_score + 2 and btts_prob > 0.6:
            predictions["winner_btts"] = {
                "market_type": "Final Result & BTTS",
                "market_prediction": f"{home_team} to win & BTTS Yes",
                "confidence_score": min(home_score / 12, btts_prob) * 0.9,
                "reason": f"{home_team} likely to win with both teams scoring"
            }
        elif away_score > home_score + 2 and btts_prob > 0.6:
            predictions["winner_btts"] = {
                "market_type": "Final Result & BTTS",
                "market_prediction": f"{away_team} to win & BTTS Yes",
                "confidence_score": min(away_score / 12, btts_prob) * 0.9,
                "reason": f"{away_team} likely to win with both teams scoring"
            }

        return predictions

    @staticmethod
    def select_best_market(predictions: Dict[str, Dict], risk_preference: str = "medium") -> Dict[str, Any]:
        """
        Select the best market with strict logical consistency between Reason and Prediction.
        """
        if not predictions:
            return {}

        # --- LOGICAL OVERRIDES ---
        # 1. Draw Logic -> Double Chance
        # If the Double Chance prediction itself mentions "Draw", it's a strong signal.
        dc = predictions.get("double_chance")
        if dc and ("draw" in dc.get("reason", "").lower() or "close xg" in dc.get("reason", "").lower()):
            if dc["confidence_score"] > 0.70:
                return {**dc, "market_key": "logical_override_draw"}

        # 2. Goals Logic -> Over / BTTS
        # Check if any strong reason implies goals
        goals_reason = False
        all_reasons = " ".join([p.get("reason", "") for p in predictions.values()]).lower()
        
        if "scores 2+" in all_reasons or "concedes 2+" in all_reasons:
             goals_reason = True
        
        if goals_reason:
            # If reasoning says goals, we MUST avoid Under and prioritize Over/BTTS if viable
            over = predictions.get("over_under") # This is 2.5
            btts = predictions.get("btts")
            
            # Check Over 2.5
            if over and "Over" in over["market_prediction"] and over["confidence_score"] > 0.6:
                 return {**over, "market_key": "logical_override_goals"}
            
            # Check BTTS Yes
            if btts and "Yes" in btts["market_prediction"] and btts["confidence_score"] > 0.6:
                 return {**btts, "market_key": "logical_override_goals"}
            
            # Fallback to Over 1.5 (Safe Goals)
            over15 = predictions.get("over_1.5")
            if over15 and over15["confidence_score"] > 0.7:
                 return {**over15, "market_key": "logical_override_goals_safe"}


        # --- STANDARD SELECTION ---
        
        # 1. Very High Confidence (Non-Volatile)
        # We exclude volatile markets like Correct Score or high-risk combos unless exceptional
        candidates = [p for p in predictions.values() if p["confidence_score"] >= 0.8]
        if candidates:
            candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
            # Filter out contradictory "Under" bets if logic suggests goals
            valid_candidates = []
            for c in candidates:
                if goals_reason and "under" in c["market_prediction"].lower():
                    continue # Skip Under if we expect goals
                valid_candidates.append(c)
            
            if valid_candidates:
                # Prefer safer types among the elite
                safe_types = ["Double Chance", "Over 1.5", "Team Goals", "Draw No Bet"]
                best_safe = next((m for m in valid_candidates if any(st in m["market_prediction"] for st in safe_types)), None)
                return best_safe if best_safe else valid_candidates[0]

        # 2. Safety First (Conservative)
        # BTTS is NOT safety first unless very high confidence.
        # Strict Safe List: DC, Over 1.5, DNB, Team Goals
        safe_markets_keys = ["double_chance", "over_1.5", "draw_no_bet", "home_over_0.5", "away_over_0.5"]
        safe_candidates = [predictions[k] for k in safe_markets_keys if k in predictions and predictions[k]["confidence_score"] > 0.65]
        
        # Sort by confidence
        if safe_candidates:
            safe_candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
            # Consistency check again
            for safe in safe_candidates:
                 if goals_reason and "under" in safe["market_prediction"].lower():
                     continue
                 return safe

        # 3. Fallback
        sorted_markets = sorted(predictions.values(), key=lambda x: x["confidence_score"], reverse=True)
        return sorted_markets[0] if sorted_markets else {}
