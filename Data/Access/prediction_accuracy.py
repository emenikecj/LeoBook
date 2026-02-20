# prediction_accuracy.py: prediction_accuracy.py: Analytical tools for measuring prediction success.
# Part of LeoBook Data — Access Layer
#
# Functions: get_market_option(), calculate_accuracy_by_date(), calculate_overall_accuracy(), calculate_accuracy_by_confidence(), format_date_for_display(), format_date_range(), print_accuracy_report()

"""
Prediction Accuracy Analysis Module
Analyzes prediction accuracy and generates reports for the LeoBook system.
"""

import csv
import re
import os
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path

from .db_helpers import PREDICTIONS_CSV


def get_market_option(prediction: str, home_team: str, away_team: str) -> str:
    """
    Normalize prediction string into a generic market option.
    """
    pred_lower = prediction.lower()
    home_lower = home_team.lower()
    away_lower = away_team.lower()

    if pred_lower == 'home win' or pred_lower == home_lower: # Direct team name often means win
        return "Home Win"
    if pred_lower == f"{home_lower} to win":
        return "Home Win"
        
    if pred_lower == 'away win' or pred_lower == away_lower:
        return "Away Win"
    if pred_lower == f"{away_lower} to win":
        return "Away Win"

    if 'or draw' in pred_lower:
        if home_lower in pred_lower:
            return "Home or Draw"
        if away_lower in pred_lower:
            return "Away or Draw"
        
    if 'or' in pred_lower and home_lower in pred_lower and away_lower in pred_lower:
         return "Home or Away"

    if 'btts' in pred_lower or 'both teams to score' in pred_lower:
        if 'no' in pred_lower:
            return "BTTS No"
        return "BTTS Yes"
    
    if 'over' in pred_lower and '2.5' in pred_lower:
        return "Over 2.5"
    if 'under' in pred_lower and '2.5' in pred_lower:
        return "Under 2.5"
        
    if '(dnb)' in pred_lower:
        return "Draw No Bet"

    if '2-3 goals' in pred_lower:
        return "2-3 Goals"

    # Match Over/Under (Starts with Over/Under)
    # e.g. "Over 2.5", "Under 3.5 Goals"
    if re.match(r'^(over|under)\s+\d+(\.\d+)?', pred_lower):
        match = re.search(r'(over|under)\s+(\d+(\.\d+)?)', pred_lower)
        if match:
            type_ = match.group(1).title()
            val = match.group(2)
            return f"{type_} {val}"

    # Team Over/Under (Ends with or contains " Over/Under value" but didn't start with it)
    # e.g. "Atletico-Mg U20 Over 0.5", "Team Over 1.5"
    if re.search(r'\s+(over|under)\s+\d+(\.\d+)?', pred_lower):
        match = re.search(r'\s+(over|under)\s+(\d+(\.\d+)?)', pred_lower)
        if match:
            type_ = match.group(1).title()
            val = match.group(2)
            return f"Team {type_} {val}"

    # Return the specific prediction name if no category matched
    return prediction.title()


def calculate_accuracy_by_date(predictions: List[Dict]) -> Dict[str, Dict]:
    """
    Calculate accuracy metrics for each date in the predictions.

    Returns:
        Dict mapping date strings to accuracy data:
        {
            "date": {
                "total_predictions": int,
                "correct_predictions": int,
                "accuracy_percentage": float,
                "formatted_date": str,
                "confidence_stats": Dict[str, Dict], # { 'Very High': {'total': x, 'correct': y, 'acc': z} }
                "market_stats": Dict[str, Dict]      # { 'Home Win': {'total': x, 'correct': y, 'acc': z} }
            }
        }
    """
    accuracy_by_date = {}

    for pred in predictions:
        outcome = pred.get('outcome_correct')
        if outcome in ['True', 'False']:
            date = pred.get('date', 'Unknown')
            confidence = pred.get('confidence', 'Low').strip() # Default to Low if missing
            
            # Normalize confidence
            if confidence.lower() in ['very high', 'very_high']:
                confidence = 'Very High'
            elif confidence.lower() in ['high']:
                confidence = 'High'
            else:
                confidence = 'Low'

            # Get generic market option
            home_team = pred.get('home_team', '')
            away_team = pred.get('away_team', '')
            prediction_text = pred.get('prediction', '')
            market_option = get_market_option(prediction_text, home_team, away_team)

            if date not in accuracy_by_date:
                accuracy_by_date[date] = {
                    'total_predictions': 0,
                    'correct_predictions': 0,
                    'accuracy_percentage': 0.0,
                    'formatted_date': format_date_for_display(date),
                    'confidence_stats': {
                        'Very High': {'total': 0, 'correct': 0, 'acc': 0.0},
                        'High': {'total': 0, 'correct': 0, 'acc': 0.0},
                        'Low': {'total': 0, 'correct': 0, 'acc': 0.0}
                    },
                    'market_stats': {} 
                }

            # Update Daily Totals
            accuracy_by_date[date]['total_predictions'] += 1
            if outcome == 'True':
                accuracy_by_date[date]['correct_predictions'] += 1

            # Update Confidence Stats
            accuracy_by_date[date]['confidence_stats'][confidence]['total'] += 1
            if outcome == 'True':
                accuracy_by_date[date]['confidence_stats'][confidence]['correct'] += 1
            
            # Update Market Stats
            if market_option not in accuracy_by_date[date]['market_stats']:
                accuracy_by_date[date]['market_stats'][market_option] = {'total': 0, 'correct': 0, 'acc': 0.0}
            
            accuracy_by_date[date]['market_stats'][market_option]['total'] += 1
            if outcome == 'True':
                accuracy_by_date[date]['market_stats'][market_option]['correct'] += 1

    # Calculate percentages
    for date, data in accuracy_by_date.items():
        if data['total_predictions'] > 0:
            data['accuracy_percentage'] = round(
                (data['correct_predictions'] / data['total_predictions']) * 100, 1
            )
        
        # Calculate Confidence Percentages
        for conf, c_data in data['confidence_stats'].items():
             if c_data['total'] > 0:
                 c_data['acc'] = round((c_data['correct'] / c_data['total']) * 100, 1)

        # Calculate Market Percentages
        for mkt, m_data in data['market_stats'].items():
            if m_data['total'] > 0:
                m_data['acc'] = round((m_data['correct'] / m_data['total']) * 100, 1)

    return accuracy_by_date


def calculate_overall_accuracy(predictions: List[Dict]) -> Dict:
    """
    Calculate overall accuracy across all reviewed predictions.

    Returns:
        Dict with overall accuracy metrics
    """
    from typing import Optional
    from datetime import date

    total_reviewed = 0
    total_correct = 0
    date_range: Dict[str, Optional[date]] = {'earliest': None, 'latest': None}

    for pred in predictions:
        outcome = pred.get('outcome_correct')
        if outcome in ['True', 'False']:
            total_reviewed += 1
            if outcome == 'True':
                total_correct += 1

            date_str = pred.get('date')
            if date_str:
                try:
                    date_obj = datetime.strptime(date_str, "%d.%m.%Y").date()
                    if date_range['earliest'] is None or date_obj < date_range['earliest']:
                        date_range['earliest'] = date_obj
                    if date_range['latest'] is None or date_obj > date_range['latest']:
                        date_range['latest'] = date_obj
                except ValueError:
                    continue

    overall_accuracy = 0.0
    if total_reviewed > 0:
        overall_accuracy = round((total_correct / total_reviewed) * 100, 1)

    return {
        'total_reviewed_predictions': total_reviewed,
        'correct_predictions': total_correct,
        'overall_accuracy_percentage': overall_accuracy,
        'date_range': date_range
    }


def calculate_accuracy_by_confidence(predictions: List[Dict]) -> Dict[str, Dict]:
    """
    Calculate accuracy metrics for each confidence level in the predictions.

    Returns:
        Dict mapping confidence levels to accuracy data:
        {
            "Very High": {
                "total_predictions": int,
                "correct_predictions": int,
                "accuracy_percentage": float
            },
            "High": {...},
            "Low": {...}
        }
    """
    # Define confidence level mappings
    confidence_mapping = {
        'Very High': ['Very High', 'very high', 'VERY HIGH'],
        'High': ['High', 'high', 'HIGH'],
        'Low': ['Low', 'low', 'LOW', 'Medium', 'medium', 'MEDIUM']  # Include Medium as Low for simplicity
    }

    accuracy_by_confidence = {}

    # Initialize confidence levels
    for conf_level in confidence_mapping.keys():
        accuracy_by_confidence[conf_level] = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'accuracy_percentage': 0.0
        }

    for pred in predictions:
        outcome = pred.get('outcome_correct')
        confidence = pred.get('confidence', '').strip()

        if outcome in ['True', 'False']:
            # Determine confidence level
            conf_level = 'Low'  # Default to Low
            for level, aliases in confidence_mapping.items():
                if confidence in aliases:
                    conf_level = level
                    break

            accuracy_by_confidence[conf_level]['total_predictions'] += 1
            if outcome == 'True':
                accuracy_by_confidence[conf_level]['correct_predictions'] += 1

    # Calculate percentages for each confidence level
    for conf_level, data in accuracy_by_confidence.items():
        if data['total_predictions'] > 0:
            data['accuracy_percentage'] = round(
                (data['correct_predictions'] / data['total_predictions']) * 100, 1
            )

    return accuracy_by_confidence


def format_date_for_display(date_str: str) -> str:
    """
    Format date string for display (e.g., "12.13.2025" -> "Friday, 13th December, 2025")
    """
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']

        day_name = day_names[date_obj.weekday()]
        day = date_obj.day
        month_name = month_names[date_obj.month - 1]
        year = date_obj.year

        # Add ordinal suffix to day
        if 11 <= day <= 13:
            day_suffix = 'th'
        else:
            day_suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        day_with_suffix = f"{day}{day_suffix}"

        return f"{day_name}, {day_with_suffix} {month_name}, {year}"
    except (ValueError, IndexError):
        return date_str


def format_date_range(date_range: Dict) -> str:
    """
    Format date range for display
    """
    if not date_range['earliest'] or not date_range['latest']:
        return "Unknown date range"

    earliest_formatted = format_date_for_display(date_range['earliest'].strftime("%d.%m.%Y"))
    latest_formatted = format_date_for_display(date_range['latest'].strftime("%d.%m.%Y"))

    if date_range['earliest'] == date_range['latest']:
        return earliest_formatted
    else:
        return f"{earliest_formatted} to {latest_formatted}"


def print_accuracy_report():
    """
    Print the prediction accuracy report to console.
    This function reads predictions from CSV and generates the accuracy report.
    """
    if not os.path.exists(PREDICTIONS_CSV):
        print("  [Accuracy] No predictions CSV found.")
        return

    # Read predictions
    predictions = []
    try:
        with open(PREDICTIONS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            predictions = list(reader)
    except Exception as e:
        print(f"  [Accuracy Error] Failed to read predictions: {e}")
        return

    # Filter for reviewed predictions only (must have actual resolved outcomes)
    reviewed_predictions = [
        pred for pred in predictions
        if pred.get('outcome_correct') in ['True', 'False']
    ]

    total_pending = sum(1 for p in predictions if p.get('status') == 'pending')
    
    if not reviewed_predictions:
        if total_pending > 0:
            print(f"  [Accuracy] {total_pending} predictions still pending — no outcomes resolved yet. Skipping report.")
        else:
            print("  [Accuracy] No reviewed predictions found.")
        return

    # Calculate accuracy by date
    accuracy_by_date = calculate_accuracy_by_date(reviewed_predictions)

    # Sort dates chronologically
    sorted_dates = sorted(accuracy_by_date.keys(),
                         key=lambda d: datetime.strptime(d, "%d.%m.%Y") if d != 'Unknown' else datetime.max.date())

    # Print individual date accuracies
    print("\n  [Prediction Accuracy Report]")
    print("  " + "="*50)

    for date in sorted_dates:
        if date == 'Unknown':
            continue

        data = accuracy_by_date[date]
        if data['total_predictions'] > 0:
            print(f"  {data['formatted_date']}: {data['accuracy_percentage']}% Accurate - {data['total_predictions']} Predictions")
            
            # Print Daily Confidence Breakdown
            c_stats = data['confidence_stats']
            conf_parts = []
            for conf in ['Very High', 'High', 'Low']:
                if c_stats[conf]['total'] > 0:
                     conf_parts.append(f"{conf}: {c_stats[conf]['acc']}% ({c_stats[conf]['total']})")
            
            if conf_parts:
                print(f"    Confidence: {' | '.join(conf_parts)}")

            # Print Top 3 Market Options
            m_stats = data['market_stats']
            # Sort by total count (popularity), then accuracy
            sorted_markets = sorted(m_stats.items(), key=lambda x: (x[1]['total'], x[1]['acc']), reverse=True)
            top_3 = sorted_markets[:3]
            
            if top_3:
                market_parts = []
                for mkt, m_data in top_3:
                    market_parts.append(f"{mkt}: {m_data['acc']}% ({m_data['total']})")
                print(f"    Top Markets: {' | '.join(market_parts)}")
            
            print("  " + "-"*30) # Separator for readability

    # Calculate accuracy by confidence level
    accuracy_by_confidence = calculate_accuracy_by_confidence(reviewed_predictions)

    # Print confidence-based accuracy
    print("  " + "="*50)
    print("  [Confidence-Based Accuracy]")

    confidence_order = ['Very High', 'High', 'Low']
    for conf_level in confidence_order:
        if conf_level in accuracy_by_confidence:
            data = accuracy_by_confidence[conf_level]
            if data['total_predictions'] > 0:
                print(f"  {conf_level} Confidence: {data['accuracy_percentage']}% Accurate - {data['total_predictions']} Reviewed Predictions")

    # Calculate and print overall accuracy
    overall_stats = calculate_overall_accuracy(reviewed_predictions)
    date_range_str = format_date_range(overall_stats['date_range'])

    print("  " + "="*50)
    print(f"  {date_range_str}: {overall_stats['overall_accuracy_percentage']}% Accurate - {overall_stats['total_reviewed_predictions']} Predictions")
    print()


# Module-level functions for external use
__all__ = [
    'calculate_accuracy_by_date',
    'calculate_overall_accuracy',
    'calculate_accuracy_by_confidence',
    'print_accuracy_report',
    'format_date_for_display'
]
