# recommend_bets.py: recommend_bets.py: Terminal-based prediction viewer and formatter.
# Part of LeoBook Scripts — Pipeline
#
# Functions: load_data(), calculate_market_reliability(), get_recommendations(), save_recommendations_to_predictions_csv()

import csv
import os
import sys
import argparse
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
from supabase import create_client, Client

# Handle Windows terminal encoding for emojis
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older python
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.append(project_root)

from Data.Access.db_helpers import PREDICTIONS_CSV
from Data.Access.prediction_accuracy import get_market_option

def load_data():
    if not os.path.exists(PREDICTIONS_CSV):
        return []
    with open(PREDICTIONS_CSV, 'r', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))

def calculate_market_reliability(predictions):
    """Calculates accuracy for each market type based on historical results."""
    market_stats = {} # {market_name: {total: 0, correct: 0, recent_total: 0, recent_correct: 0}}
    
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    
    for p in predictions:
        outcome = p.get('outcome_correct')
        if outcome not in ['True', 'False']:
            continue
            
        try:
            p_date = datetime.strptime(p.get('date', ''), "%d.%m.%Y")
        except:
            continue

        market = get_market_option(p.get('prediction', ''), p.get('home_team', ''), p.get('away_team', ''))
        if market not in market_stats:
            market_stats[market] = {'total': 0, 'correct': 0, 'recent_total': 0, 'recent_correct': 0}
            
        market_stats[market]['total'] += 1
        if outcome == 'True':
            market_stats[market]['correct'] += 1
            
        if p_date >= seven_days_ago:
            market_stats[market]['recent_total'] += 1
            if outcome == 'True':
                market_stats[market]['recent_correct'] += 1
            
    reliability = {}
    for m, stats in market_stats.items():
        overall = stats['correct'] / stats['total'] if stats['total'] >= 3 else 0.5
        recent = stats['recent_correct'] / stats['recent_total'] if stats['recent_total'] >= 2 else overall
        reliability[m] = {
            'overall': overall,
            'recent': recent,
            'trend': recent - overall
        }
            
    return reliability

def get_recommendations(target_date=None, show_all_upcoming=False, **kwargs):
    all_predictions = load_data()
    if not all_predictions:
        print("[ALGO] No predictions found in CSV.")
        return {'status': 'empty', 'total': 0, 'scored': 0}

    print(f"[ALGO] Loaded {len(all_predictions)} predictions. Calculating market reliability...")

    # 1. Build reliability index from past results
    reliability = calculate_market_reliability(all_predictions)
    print(f"[ALGO] Built reliability index for {len(reliability)} market types.")
    
    # 2. Filter for future matches
    now = datetime.now()
    recommendations = []
    
    for p in all_predictions:
        # Skip if already reviewed or canceled
        if p.get('status') in ['reviewed', 'match_canceled']:
            continue
            
        try:
            p_date_str = p.get('date')
            p_time_str = p.get('match_time')
            if not p_date_str or not p_time_str or p_time_str == 'N/A':
                continue
                
            p_dt = datetime.strptime(f"{p_date_str} {p_time_str}", "%d.%m.%Y %H:%M")
            
            # Date Filtering
            if target_date:
                if p_date_str != target_date: continue
            elif not show_all_upcoming:
                # Default: Today only, and in the future
                if p_date_str != now.strftime("%d.%m.%Y"): continue
                if p_dt <= now: continue
            else:
                # All upcoming: anything in the future
                if p_dt <= now: continue

            # 3. Calculate Score
            market = get_market_option(p.get('prediction', ''), p.get('home_team', ''), p.get('away_team', ''))
            rel_info = reliability.get(market, {'overall': 0.5, 'recent': 0.5, 'trend': 0.0})
            
            overall_acc = rel_info['overall']
            recent_acc = rel_info['recent']
            
            conf_map = {"Very High": 1.0, "High": 0.85, "Medium": 0.7, "Low": 0.5}
            conf_score = conf_map.get(p.get('confidence'), 0.5)
            
            # Weighted Score: 30% overall reliability, 50% recent momentum, 20% specific match confidence
            total_score = (overall_acc * 0.3) + (recent_acc * 0.5) + (conf_score * 0.2)
            
            trend_icon = "↗️" if rel_info['trend'] > 0.05 else "↘️" if rel_info['trend'] < -0.05 else "➡️" if rel_info['trend'] != 0 else ""

            recommendations.append({
                'match': f"{p['home_team']} vs {p['away_team']}",
                'fixture_id': p.get('fixture_id', ''),
                'time': p_time_str,
                'date': p_date_str,
                'prediction': p['prediction'],
                'market': market,
                'confidence': p['confidence'],
                'overall_acc': f"{overall_acc:.1%}",
                'recent_acc': f"{recent_acc:.1%}",
                'trend': trend_icon,
                'score': total_score,
                'league': p.get('region_league', 'Unknown')
            })
        except Exception:
            continue

    # 4. Sort and Print
    recommendations.sort(key=lambda x: x['score'], reverse=True)

    # ALGO Summary Feedback
    high_conf = [r for r in recommendations if r['score'] >= 0.7]
    print(f"[ALGO] Scored {len(recommendations)} matches. High-confidence picks (≥0.7): {len(high_conf)}")
    if recommendations:
        print(f"[ALGO] Top score: {recommendations[0]['score']:.2f} — {recommendations[0]['match']}")
    
    title = "BETTING RECOMMENDATIONS"
    if target_date: title += f" FOR {target_date}"
    elif show_all_upcoming: title += " (ALL UPCOMING)"
    else: title += " (TODAY'S REMAINING)"
    
    output_lines = []
    output_lines.append(f"\n{'='*65}")
    output_lines.append(f"{title:^65}")
    output_lines.append(f"{'='*65}\n")
    
    if not recommendations:
        output_lines.append("No matches found for the selected criteria.")
    else:
        for i, rec in enumerate(recommendations, 1): # Unlimited
            output_lines.append(f"{i}. {rec['match']} [{rec['league']}]")
            output_lines.append(f"   Time: {rec['date']} {rec['time']}")
            output_lines.append(f"   Prediction: {rec['prediction']} ({rec['confidence']})")
            output_lines.append(f"   Market Confidence: Recent: {rec['recent_acc']} {rec['trend']} (Overall: {rec['overall_acc']})")
            output_lines.append(f"   Recommendation Score: {rec['score']:.2f}")
            output_lines.append(f"{'-'*65}")

    # Print to console with colors
    print(f"\n{'='*65}")
    print(f"{title:^65}")
    print(f"{'='*65}\n")
    if not recommendations:
        print("No matches found for the selected criteria.")
    else:
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['match']} [{rec['league']}]")
            print(f"   Time: {rec['date']} {rec['time']}")
            print(f"   Prediction: \033[92m{rec['prediction']}\033[0m ({rec['confidence']})")
            print(f"   Market Confidence: Recent: {rec['recent_acc']} {rec['trend']} (Overall: {rec['overall_acc']})")
            print(f"   Recommendation Score: {rec['score']:.2f}")
            print(f"{'-'*65}")

    # Save to file if requested
    if kwargs.get('save_to_file'):
        # Use project_root to ensure it lands in the main DB folder
        # If project_root is not defined (e.g. called as module), we determine it
        p_root = globals().get('project_root')
        if not p_root:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            p_root = os.path.dirname(script_dir)
            
        recommendations_dir = os.path.join(p_root, "Data", "Store", "RecommendedBets")
        if not os.path.exists(recommendations_dir):
            os.makedirs(recommendations_dir, exist_ok=True)
            
        file_date = target_date if target_date else now.strftime("%d.%m.%Y")
        
        # 1. Save Human-Readable TXT
        file_path_txt = os.path.join(recommendations_dir, f"recommendations_{file_date}.txt")
        try:
            with open(file_path_txt, 'w', encoding='utf-8') as f:
                f.write("\n".join(output_lines))
            print(f"\n[OK] Recommendations (TXT) saved to: {file_path_txt}")
        except Exception as e:
            print(f"\n[Error] Failed to save TXT recommendations: {e}")

        # 2. Save Structured JSON for App
        import json
        json_path = os.path.join(p_root, "Data", "Store", "recommended.json")
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(recommendations, f, ensure_ascii=False, indent=2)
            print(f"[OK] Recommendations (JSON) saved to: {json_path}")
        except Exception as e:
            print(f"[Error] Failed to save JSON recommendations: {e}")
            
    # 3. Update predictions.csv with recommendation data
    if kwargs.get('save_to_file'):
        save_recommendations_to_predictions_csv(recommendations)

    # Return summary for callers
    return {
        'status': 'ok',
        'total': len(all_predictions),
        'scored': len(recommendations),
        'high_confidence': len([r for r in recommendations if r['score'] >= 0.7]),
        'top_score': recommendations[0]['score'] if recommendations else 0,
        'recommendations': recommendations
    }

def save_recommendations_to_predictions_csv(recommendations):
    """Updates predictions.csv with is_recommended flag and score."""
    if not os.path.exists(PREDICTIONS_CSV):
        print(f"[Error] predictions.csv not found at {PREDICTIONS_CSV}")
        return

    # Create a lookup map for faster access
    # Key: fixture_id (preferred) or home_away_date fallback
    rec_map = {r['fixture_id']: r for r in recommendations if r.get('fixture_id')}
    
    # Also map by team names for fallback
    rec_map_teams = {f"{r['match']}_{r['date']}": r for r in recommendations}

    updated_rows = []
    headers = []
    updates_count = 0

    try:
        with open(PREDICTIONS_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            data = list(reader)

        if 'is_recommended' not in headers:
            headers.append('is_recommended')
        if 'recommendation_score' not in headers:
            headers.append('recommendation_score')

        for row in data:
            # Reset by default to ensure clean state
            row['is_recommended'] = 'False'
            row['recommendation_score'] = '0.0'

            # Try to match
            fid = row.get('fixture_id')
            match_key = f"{row.get('home_team')} vs {row.get('away_team')}_{row.get('date')}"
            
            matched_rec = rec_map.get(fid) or rec_map_teams.get(match_key)

            if matched_rec:
                row['is_recommended'] = 'True'
                row['recommendation_score'] = str(matched_rec['score'])
                updates_count += 1
            
            updated_rows.append(row)

        with open(PREDICTIONS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(updated_rows)
            
        print(f"[ALGO] Updated predictions.csv: {updates_count} marked as recommended out of {len(data)} total rows.")

    except Exception as e:
        print(f"[Error] Failed to update predictions.csv: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get betting recommendations.")
    parser.add_argument("--date", help="Target date (DD.MM.YYYY)")
    parser.add_argument("--all", action="store_true", help="Show all upcoming matches")
    parser.add_argument("--save", action="store_true", help="Save recommendations to DB and update CSV")
    args = parser.parse_args()
    
    get_recommendations(target_date=args.date, show_all_upcoming=args.all, save_to_file=args.save)
