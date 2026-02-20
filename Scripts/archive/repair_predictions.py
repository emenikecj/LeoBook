# repair_predictions.py: Utility to fix malformed prediction results.
# Refactored for Clean Architecture (v2.7)
# This script re-evaluates outcomes for predictions with 'ERROR' or 'TBD' status.

import csv
import os
import sys

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.append(project_root)

from Data.Access.prediction_evaluator import evaluate_prediction
from Data.Access.db_helpers import PREDICTIONS_CSV

def repair_predictions():
    if not os.path.exists(PREDICTIONS_CSV):
        print(f"File not found: {PREDICTIONS_CSV}")
        return

    rows = []
    updated_count = 0
    
    with open(PREDICTIONS_CSV, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            prediction = row.get('prediction')
            actual_score = row.get('actual_score')
            outcome_correct = row.get('outcome_correct')
            home_team = row.get('home_team')
            away_team = row.get('away_team')
            
            # If we have a score but no outcome, OR if it's a DNB market specifically 
            # (to ensure we re-evaluate even if it was previously set to None or empty)
            if actual_score and actual_score != 'N/A' and (not outcome_correct or outcome_correct in ['', 'None']):
                is_correct = evaluate_prediction(prediction, actual_score, home_team, away_team)
                if is_correct is not None:
                    row['outcome_correct'] = str(is_correct)
                    updated_count += 1
                    print(f"Updated: {row['fixture_id']} | {prediction} | {actual_score} -> {is_correct}")
            
            rows.append(row)

    if updated_count > 0:
        with open(PREDICTIONS_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Successfully repaired {updated_count} predictions.")
    else:
        print("No predictions needed repair.")

if __name__ == "__main__":
    repair_predictions()
