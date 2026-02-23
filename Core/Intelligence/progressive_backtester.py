# progressive_backtester.py: Day-by-day chronological backtesting engine.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: run_progressive_backtest()
# Called by: Leo.py (--rule-engine --backtest)

"""
Progressive Backtester
Simulates reality: predicts matches day-by-day using only historically available data,
checks outcomes, updates learning weights, and tracks accuracy evolution.
"""

import csv
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from collections import defaultdict
from Core.Intelligence.aigo_suite import AIGOSuite

from Core.Intelligence.rule_engine_manager import RuleEngineManager
from Core.Intelligence.learning_engine import LearningEngine
from Data.Access.db_helpers import get_all_schedules, get_standings
from Data.Access.db_helpers import evaluate_market_outcome as evaluate_prediction

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "Data" / "Store"


def _build_vision_data(
    match: Dict,
    historical: List[Dict],
    standings_cache: Dict[str, List[Dict]],
) -> Dict[str, Any]:
    """Build the vision_data dict for RuleEngine.analyze() from historical data."""
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    region_league = match.get("region_league", "Unknown")

    home_last_10, away_last_10, h2h_list = [], [], []

    for hist in historical:
        h_home = hist.get("home_team", "")
        h_away = hist.get("away_team", "")
        hs = hist.get("home_score", "0")
        ascore = hist.get("away_score", "0")
        try:
            hsi, asi = int(hs), int(ascore)
            winner = "Home" if hsi > asi else "Away" if asi > hsi else "Draw"
        except (ValueError, TypeError):
            winner = "Draw"

        mapped = {
            "date": hist.get("date"),
            "home": h_home,
            "away": h_away,
            "score": f"{hs}-{ascore}",
            "winner": winner,
        }

        if (h_home == home_team or h_away == home_team) and len(home_last_10) < 10:
            home_last_10.append(mapped)
        if (h_home == away_team or h_away == away_team) and len(away_last_10) < 10:
            away_last_10.append(mapped)
        if (h_home == home_team and h_away == away_team) or (
            h_home == away_team and h_away == home_team
        ):
            h2h_list.append(mapped)

    # Standings
    if region_league not in standings_cache:
        raw = get_standings(region_league)
        parsed = []
        for s in raw:
            try:
                parsed.append({
                    "team_name": s.get("team_name"),
                    "position": int(s.get("position", 0)),
                    "goal_difference": int(s.get("goal_difference", 0)),
                    "goals_for": int(s.get("goals_for", 0)),
                    "goals_against": int(s.get("goals_against", 0)),
                })
            except (ValueError, TypeError):
                continue
        standings_cache[region_league] = parsed

    return {
        "h2h_data": {
            "home_team": home_team,
            "away_team": away_team,
            "home_last_10_matches": home_last_10,
            "away_last_10_matches": away_last_10,
            "head_to_head": h2h_list,
            "region_league": region_league,
        },
        "standings": standings_cache[region_league],
    }


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse a date string in DD.MM.YYYY or YYYY-MM-DD format."""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_progressive_backtest(
    engine_id: str,
    start_date: str,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backtest a rule engine chronologically, day-by-day:

    1. Start at start_date
    2. For each day, predict all matches using ONLY data available before that day
    3. After predicting, check actual outcomes
    4. Update engine's learning weights based on results
    5. Move to next day and repeat

    Returns summary dict with accuracy stats.
    """
    from Core.Intelligence.rule_engine_manager import RuleEngineManager
    from Core.Intelligence.rule_engine import RuleEngine

    engine = RuleEngineManager.get_engine(engine_id)
    if not engine:
        print(f"   [Backtest] Engine '{engine_id}' not found.")
        return {}

    config = RuleEngineManager.to_rule_config(engine)
    print(f"\n   ═══ PROGRESSIVE BACKTEST: {engine['name']} ═══")
    print(f"   Engine: {engine_id}")
    print(f"   Risk: {config.risk_preference}")

    # Parse date range
    start_dt = _parse_date(start_date)
    if not start_dt:
        print(f"   [Error] Invalid start date: {start_date}")
        return {}
    end_dt = _parse_date(end_date) if end_date else datetime.now()
    print(f"   Period: {start_dt.strftime('%Y-%m-%d')} → {end_dt.strftime('%Y-%m-%d')}")

    # Load all schedules
    all_schedules = get_all_schedules()
    if not all_schedules:
        print("   [Error] No schedules found.")
        return {}

    # Split into: matches with results (for training/validation)
    finished = []
    for m in all_schedules:
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs not in ("", "N/A", None) and as_ not in ("", "N/A", None):
            dt = _parse_date(m.get("date", ""))
            if dt:
                m["_parsed_date"] = dt
                finished.append(m)

    finished.sort(key=lambda x: x["_parsed_date"])
    print(f"   Total finished matches: {len(finished)}")

    # Set up output CSV
    backtest_csv = DATA_DIR / f"backtest_{engine_id}.csv"
    csv_headers = [
        "date", "home_team", "away_team", "region_league",
        "prediction", "confidence", "actual_score", "outcome_correct",
        "xg_home", "xg_away",
    ]

    total, correct, skipped = 0, 0, 0
    daily_stats = defaultdict(lambda: {"total": 0, "correct": 0})

    # Open CSV for writing
    with open(backtest_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()

        # Iterate day-by-day
        current_day = start_dt
        total_days = (end_dt - start_dt).days
        day_count = 0

        while current_day <= end_dt:
            day_count += 1
            day_str = current_day.strftime("%Y-%m-%d")

            # Matches ON this day (with results)
            today_matches = [m for m in finished if m["_parsed_date"].date() == current_day.date()]

            # Historical matches BEFORE this day (available for prediction)
            historical = [m for m in finished if m["_parsed_date"] < current_day]
            historical.sort(key=lambda x: x["_parsed_date"], reverse=True)

            standings_cache: Dict[str, List[Dict]] = {}

            for match in today_matches:
                home, away = match.get("home_team", ""), match.get("away_team", "")

                # Data quality check
                home_form_count = sum(
                    1 for h in historical
                    if h.get("home_team") == home or h.get("away_team") == home
                )
                away_form_count = sum(
                    1 for h in historical
                    if h.get("home_team") == away or h.get("away_team") == away
                )
                if home_form_count < config.min_form_matches or away_form_count < config.min_form_matches:
                    skipped += 1
                    continue

                # Build vision data and predict
                vision = _build_vision_data(match, historical[:500], standings_cache)
                try:
                    prediction = RuleEngine.analyze(vision, config=config)
                except Exception:
                    skipped += 1
                    continue

                if prediction.get("type") == "SKIP":
                    skipped += 1
                    continue

                # Evaluate outcome
                actual_score = f"{match.get('home_score', '0')}-{match.get('away_score', '0')}"
                pred_text = prediction.get("market_prediction", "")

                is_correct = evaluate_prediction(pred_text, actual_score, home_team=home, away_team=away)

                total += 1
                if is_correct:
                    correct += 1

                daily_stats[day_str]["total"] += 1
                if is_correct:
                    daily_stats[day_str]["correct"] += 1

                # Write to CSV
                writer.writerow({
                    "date": day_str,
                    "home_team": home,
                    "away_team": away,
                    "region_league": match.get("region_league", ""),
                    "prediction": pred_text,
                    "confidence": prediction.get("confidence", ""),
                    "actual_score": actual_score,
                    "outcome_correct": str(is_correct),
                    "xg_home": prediction.get("xg_home", ""),
                    "xg_away": prediction.get("xg_away", ""),
                })

            # End-of-day learning update (weights evolve)
            if today_matches:
                LearningEngine.update_weights(engine_id=engine_id)

            # Progress output every 7 days
            if day_count % 7 == 0 or current_day.date() == end_dt.date():
                win_rate = (correct / total * 100) if total > 0 else 0
                print(
                    f"   [Backtest] Day {day_count}/{total_days} | {day_str} | "
                    f"Accuracy: {win_rate:.1f}% ({correct}/{total}) | Skipped: {skipped}"
                )

            current_day += timedelta(days=1)

    # Final summary
    win_rate = (correct / total * 100) if total > 0 else 0
    period_str = f"{start_dt.strftime('%Y-%m-%d')} → {end_dt.strftime('%Y-%m-%d')}"

    print(f"\n   ═══ BACKTEST COMPLETE ═══")
    print(f"   Engine: {engine['name']}")
    print(f"   Period: {period_str}")
    print(f"   Predictions: {total} | Correct: {correct} | Skipped: {skipped}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Results: {backtest_csv}\n")

    # Update engine accuracy
    RuleEngineManager.update_engine(engine_id, {
        "accuracy": {
            "total_predictions": total,
            "correct": correct,
            "win_rate": round(win_rate, 1),
            "last_backtested": datetime.utcnow().isoformat(),
            "backtest_period": period_str,
        }
    })

    return {
        "engine_id": engine_id,
        "total": total,
        "correct": correct,
        "win_rate": win_rate,
        "skipped": skipped,
        "period": period_str,
        "csv_path": str(backtest_csv),
    }
