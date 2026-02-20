# learning_engine.py: learning_engine.py: Self-learning component for weight adjustment.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: LearningEngine

"""
LearningEngine Module
Handles prediction learning, performance analysis, and weight adaptation with region-specific granularity.
"""
# Refactored for Clean Architecture (v2.7)
# This script delegates complex analysis to specialized AI sub-modules.

# selector_manager.py: Intelligent selector retrieval and auto-healing.
# Refactored for Clean Architecture (v2.7)
# This script provides resilient UI element locating with AI fallbacks.

import json
import os
import csv
from collections import defaultdict
from typing import Dict, Any, List, Tuple

class LearningEngine:
    """Self-learning component that analyzes prediction performance and adjusts weights per region/league."""

    LEARNING_DB = "Data/Store/learning_weights.json"
    
    # Map text reasons back to rule keys for learning attribution
    REASON_TO_RULE_MAP = {
        "H2H home strong": "h2h_home_win",
        "H2H away strong": "h2h_away_win",
        "H2H drawish": "h2h_draw",
        "Top vs Bottom": "standings_top_vs_bottom",
        "strong GD": "standings_gd_strong",
        "weak GD": "standings_gd_weak",
        "scores 2+": "form_score_2plus",
        "concedes 2+": "form_concede_2plus",
        "fails to score": "form_no_score",
        "strong defense": "form_clean_sheet",
        "xG advantage": "xg_advantage",
        "Close xG suggests draw": "xg_draw"
    }

    DEFAULT_WEIGHTS = {
        "h2h_home_win": 3.0,
        "h2h_away_win": 3.0,
        "h2h_draw": 3.0,
        "h2h_over25": 3.0,
        "standings_top_vs_bottom": 5.0,
        "standings_table_advantage": 3.0,
        "standings_gd_strong": 2.0,
        "standings_gd_weak": 2.0,
        "form_score_2plus": 3.0,
        "form_score_3plus": 2.0,
        "form_concede_2plus": 3.0,
        "form_no_score": 4.0,
        "form_clean_sheet": 4.0,
        "form_vs_top_win": 3.0,
        "xg_advantage": 4.0,  # Increased default influence of xG
        "xg_draw": 2.0,
        "confidence_calibration": {
            "Very High": 0.70,
            "High": 0.60,
            "Medium": 0.50,
            "Low": 0.40
        }
    }

    @staticmethod
    def load_weights(region_league: str = "GLOBAL") -> Dict[str, Any]:
        """
        Load learned weights for a specific region/league.
        Falls back to GLOBAL if specific weights don't exist.
        """
        all_weights = {}
        if os.path.exists(LearningEngine.LEARNING_DB):
            try:
                with open(LearningEngine.LEARNING_DB, 'r') as f:
                    all_weights = json.load(f)
            except:
                pass
        
        # If the file is the old flat format, migrate it to the new structure
        if "h2h_home_win" in all_weights:
            all_weights = {"GLOBAL": all_weights}

        # 1. Try exact match
        if region_league in all_weights:
            return LearningEngine._merge_defaults(all_weights[region_league])
            
        # 2. Try Region match (if "Region - League" format)
        if " - " in region_league:
            region = region_league.split(" - ")[0]
            # Potential future expansion: Region-level fallbacks
        
        # 3. Fallback to GLOBAL
        return LearningEngine._merge_defaults(all_weights.get("GLOBAL", {}))

    @staticmethod
    def _merge_defaults(weights: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all keys exist by merging with defaults."""
        merged = LearningEngine.DEFAULT_WEIGHTS.copy()
        # Deep merge for confidence_calibration
        if "confidence_calibration" in weights:
            merged["confidence_calibration"].update(weights["confidence_calibration"])
            del weights["confidence_calibration"]
            
        merged.update(weights)
        return merged

    @staticmethod
    def save_all_weights(all_weights: Dict[str, Any]):
        """Save the entire weights dictionary to file."""
        os.makedirs("Data/Store", exist_ok=True)
        with open(LearningEngine.LEARNING_DB, 'w') as f:
            json.dump(all_weights, f, indent=2)

    @staticmethod
    def analyze_performance() -> Tuple[Dict[str, Dict[str, Dict[str, int]]], Dict[str, Dict[str, Dict[str, int]]]]:
        """
        Analyze prediction performance breakdown by Region/League and Rule.
        Returns: (rule_performance, confidence_performance)
        where each is { RegionLeague: { Key: { 'correct': int, 'total': int } } }
        """
        from Data.Access.db_helpers import PREDICTIONS_CSV
        
        if not os.path.exists(PREDICTIONS_CSV):
            return {}, {}

        # Structure: League -> Rule -> Stats
        performance = defaultdict(lambda: defaultdict(lambda: {"correct": 0, "total": 0}))
        
        # Structure: League -> Confidence -> Stats
        conf_performance = defaultdict(lambda: defaultdict(lambda: {"correct": 0, "total": 0}))

        try:
            with open(PREDICTIONS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Only analyze resolved matches
                    if row.get('outcome_correct') not in ['True', 'False']:
                        continue
                        
                    is_correct = row.get('outcome_correct') == 'True'
                    region_league = row.get('region_league', 'Unknown')
                    prediction_conf = row.get('confidence', 'Medium')
                    reasoning_text = row.get('reason', '')
                    
                    # Track confidence accuracy
                    conf_performance[region_league][prediction_conf]["total"] += 1
                    conf_performance["GLOBAL"][prediction_conf]["total"] += 1
                    if is_correct:
                        conf_performance[region_league][prediction_conf]["correct"] += 1
                        conf_performance["GLOBAL"][prediction_conf]["correct"] += 1

                    # Track rule accuracy based on reasoning text
                    for phrase, rule_key in LearningEngine.REASON_TO_RULE_MAP.items():
                        if phrase in reasoning_text:
                            performance[region_league][rule_key]["total"] += 1
                            performance["GLOBAL"][rule_key]["total"] += 1
                            if is_correct:
                                performance[region_league][rule_key]["correct"] += 1
                                performance["GLOBAL"][rule_key]["correct"] += 1
                                
        except Exception as e:
            print(f"Error analyzing performance: {e}")
            return {}, {}

        # Convert defaultdicts to regular dicts for return
        return dict(performance), dict(conf_performance)

    @staticmethod
    def update_weights() -> Dict[str, Any]:
        """
        Update learning weights based on historical performance for each league.
        """
        rule_perf, conf_perf = LearningEngine.analyze_performance()
        
        # Load existing (or init new structure)
        if os.path.exists(LearningEngine.LEARNING_DB):
            try:
                with open(LearningEngine.LEARNING_DB, 'r') as f:
                    all_weights = json.load(f)
                # Migration check
                if "h2h_home_win" in all_weights:
                    all_weights = {"GLOBAL": all_weights}
            except:
                all_weights = {"GLOBAL": LearningEngine.DEFAULT_WEIGHTS.copy()}
        else:
            all_weights = {"GLOBAL": LearningEngine.DEFAULT_WEIGHTS.copy()}

        # Update weights for each league found in performance history
        # We also explicitly update GLOBAL based on global stats
        leagues_to_update = set(rule_perf.keys()) | set(conf_perf.keys()) | {"GLOBAL"}
        
        for league in leagues_to_update:
            if league not in all_weights:
                all_weights[league] = LearningEngine.DEFAULT_WEIGHTS.copy()
            
            league_weights = all_weights[league]
            
            # 1. Update Rule Weights
            if league in rule_perf:
                for rule, stats in rule_perf[league].items():
                    if stats["total"] >= 5: # Lower threshold for faster adaptation
                        accuracy = stats["correct"] / stats["total"]
                        current_val = league_weights.get(rule, LearningEngine.DEFAULT_WEIGHTS.get(rule, 3.0))
                        
                        # Dynamic Adjustment Factor (0.05 step)
                        if accuracy > 0.65:
                            new_val = min(current_val + 0.1, 10.0)
                        elif accuracy < 0.45:
                            new_val = max(current_val - 0.1, 0.5)
                        else:
                            new_val = current_val # Stable
                            
                        league_weights[rule] = round(new_val, 2)

            # 2. Update Confidence Calibration
            # Adjust expectation of truthfulness for each confidence level
            if league in conf_perf:
                if "confidence_calibration" not in league_weights:
                    league_weights["confidence_calibration"] = LearningEngine.DEFAULT_WEIGHTS["confidence_calibration"].copy()
                
                for level, stats in conf_perf[league].items():
                    if stats["total"] >= 10 and level in league_weights["confidence_calibration"]:
                        actual_acc = stats["correct"] / stats["total"]
                        # Slowly nudge the calibration towards reality
                        current_cal = league_weights["confidence_calibration"][level]
                        # Weighted average update (mostly sticky)
                        new_cal = (current_cal * 0.9) + (actual_acc * 0.1)
                        league_weights["confidence_calibration"][level] = round(new_cal, 3)

        LearningEngine.save_all_weights(all_weights)
        return all_weights
