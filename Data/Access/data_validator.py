# data_validator.py: data_validator.py: Integrity checks for extracted match data.
# Part of LeoBook Data — Access Layer
#
# Classes: DataValidator

"""
Data Validator Module
Advanced data validation and quality assurance system.
Responsible for validating data integrity, quality checks, and comprehensive reporting.
"""

import json
import os
import statistics
from datetime import datetime as dt
from typing import Dict, Any, List


class DataValidator:
    """Advanced data validation and quality assurance system"""

    VALIDATION_LOG = "Data/Store/validation_report.json"

    @staticmethod
    def validate_standings_data(standings: List[Dict]) -> Dict[str, Any]:
        """Comprehensive validation of standings data"""
        issues = []
        stats = {
            "total_teams": len(standings),
            "position_range": [],
            "goal_differences": [],
            "points_distribution": []
        }

        if not standings:
            return {"valid": False, "issues": ["No standings data"], "stats": stats}

        positions = []
        for team in standings:
            try:
                pos = int(team.get("position", 0))
                points = int(team.get("points", 0))
                gd = int(team.get("goal_difference", 0))

                positions.append(pos)
                stats["goal_differences"].append(gd)
                stats["points_distribution"].append(points)

                # Position validation
                if pos < 1 or pos > 50:
                    issues.append(f"Invalid position {pos} for {team.get('team_name', 'Unknown')}")

                # Points validation (rough check)
                if points < 0 or points > 150:
                    issues.append(f"Suspicious points {points} for {team.get('team_name', 'Unknown')}")

            except (ValueError, TypeError):
                issues.append(f"Invalid numeric data for {team.get('team_name', 'Unknown')}")

        # Position continuity check
        if positions:
            expected_positions = set(range(1, len(positions) + 1))
            actual_positions = set(positions)
            missing = expected_positions - actual_positions
            duplicates = [x for x in positions if positions.count(x) > 1]

            if missing:
                issues.append(f"Missing positions: {sorted(missing)}")
            if duplicates:
                issues.append(f"Duplicate positions: {list(set(duplicates))}")

        # Statistical validation
        if stats["goal_differences"]:
            mean_gd = statistics.mean(stats["goal_differences"])
            std_gd = statistics.stdev(stats["goal_differences"]) if len(stats["goal_differences"]) > 1 else 0

            outliers = [gd for gd in stats["goal_differences"] if abs(gd - mean_gd) > 3 * std_gd]
            if outliers:
                issues.append(f"Statistical outliers in goal difference: {outliers}")

        stats["position_range"] = [min(positions), max(positions)] if positions else []

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "stats": stats
        }

    @staticmethod
    def validate_h2h_data(h2h_data: Dict) -> Dict[str, Any]:
        """Validate H2H data quality"""
        issues = []

        for section_name, matches in h2h_data.items():
            if section_name == "parsing_errors":
                continue
            if not isinstance(matches, list):
                issues.append(f"Invalid {section_name} format")
                continue

            for i, match in enumerate(matches):
                required_fields = ["home", "away", "score", "date"]
                for field in required_fields:
                    if field not in match:
                        issues.append(f"Missing {field} in {section_name}[{i}]")

                # Score validation
                score = match.get("score", "")
                if "-" not in str(score):
                    issues.append(f"Invalid score format in {section_name}[{i}]: {score}")
                else:
                    try:
                        hg, ag = map(int, score.replace(" ", "").split("-"))
                        if hg < 0 or ag < 0 or hg > 10 or ag > 10:
                            issues.append(f"Suspicious score in {section_name}[{i}]: {score}")
                    except:
                        issues.append(f"Non-numeric score in {section_name}[{i}]: {score}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "total_matches": sum(len(v) for k, v in h2h_data.items() if isinstance(v, list))
        }

    @staticmethod
    def validate_prediction_consistency(prediction: Dict) -> Dict[str, Any]:
        """Validate prediction internal consistency"""
        issues = []

        confidence = prediction.get("confidence", "Low")
        ml_confidence = prediction.get("ml_confidence", 0.5)

        # Confidence alignment check
        if confidence == "Very High" and ml_confidence < 0.65:
            issues.append("Confidence mismatch: Very High but low ML confidence")
        elif confidence == "Low" and ml_confidence > 0.7:
            issues.append("Confidence mismatch: Low but high ML confidence")

        # xG alignment with prediction
        xg_home = prediction.get("xg_home", 0)
        xg_away = prediction.get("xg_away", 0)
        pred_type = prediction.get("type", "")

        if pred_type.startswith("HOME") and xg_away > xg_home + 0.5:
            issues.append("xG contradicts home win prediction")
        elif pred_type.startswith("AWAY") and xg_home > xg_away + 0.5:
            issues.append("xG contradicts away win prediction")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "confidence_alignment": abs({"Very High": 0.8, "High": 0.65, "Medium": 0.5, "Low": 0.35}.get(confidence, 0.5) - ml_confidence) < 0.2
        }

    @staticmethod
    def generate_quality_report():
        """Generate comprehensive data quality report"""
        report = {
            "timestamp": dt.now().isoformat(),
            "predictions_quality": {},
            "standings_quality": {},
            "h2h_quality": {},
            "system_health": {}
        }

        # Predictions quality
        predictions_file = "Data/Store/predictions.csv"
        if os.path.exists(predictions_file):
            with open(predictions_file, 'r', encoding='utf-8') as f:
                import csv
                reader = csv.DictReader(f)
                predictions = list(reader)

            total = len(predictions)
            reviewed = sum(1 for p in predictions if p.get('status') == 'reviewed')
            correct = sum(1 for p in predictions if p.get('outcome_correct') == 'True')

            report["predictions_quality"] = {
                "total_predictions": total,
                "reviewed": reviewed,
                "correct": correct,
                "accuracy": correct / reviewed if reviewed > 0 else 0,
                "coverage": reviewed / total if total > 0 else 0
            }

        # System health
        report["system_health"] = {
            "learning_weights_exist": os.path.exists("Data/Store/learning_weights.json"),
            "ml_models_exist": os.path.exists("Data/Models/random_forest.pkl"),
            "selectors_knowledge": os.path.exists("Config/knowledge.json")
        }

        # Save report
        os.makedirs("Data/Store", exist_ok=True)
        with open(DataValidator.VALIDATION_LOG, 'w') as f:
            json.dump(report, f, indent=2)

        return report

    @staticmethod
    def run_comprehensive_validation():
        """Run all validation checks and return summary"""
        print("=== DATA QUALITY VALIDATION ===")

        report = DataValidator.generate_quality_report()

        print(f"Predictions: {report['predictions_quality'].get('total_predictions', 0)} total")
        accuracy = report['predictions_quality'].get('accuracy', 0)
        coverage = report['predictions_quality'].get('coverage', 0)
        print(".1f")
        print(".1f")
        print(f"System Health: {sum(report['system_health'].values())}/3 components healthy")

        return report
