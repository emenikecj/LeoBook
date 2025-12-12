import asyncio
import csv
import os
from datetime import datetime as dt, timedelta
from typing import List, Dict, Any
import json
import statistics

from playwright.async_api import async_playwright, Page, TimeoutError

from .db_helpers import PREDICTIONS_CSV, SCHEDULES_CSV, save_schedule_entry, REGION_LEAGUE_CSV, upsert_entry, files_and_headers
from Helpers.Site_Helpers.site_helpers import fs_universal_popup_dismissal
from playwright.async_api import Browser
from Helpers.utils import log_error_state
from Neo.intelligence import get_selector_auto, get_selector


class DataValidator:
    """Advanced data validation and quality assurance system"""

    VALIDATION_LOG = "DB/validation_report.json"

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
                        h, a = map(int, score.split("-"))
                        if h < 0 or a < 0 or h > 10 or a > 10:
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
        if os.path.exists(PREDICTIONS_CSV):
            with open(PREDICTIONS_CSV, 'r', encoding='utf-8') as f:
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
            "learning_weights_exist": os.path.exists("DB/learning_weights.json"),
            "ml_models_exist": os.path.exists("DB/models/random_forest.pkl"),
            "selectors_knowledge": os.path.exists("DB/knowledge.json")
        }

        # Save report
        os.makedirs("DB", exist_ok=True)
        with open(DataValidator.VALIDATION_LOG, 'w') as f:
            json.dump(report, f, indent=2)

        return report

    @staticmethod
    def run_comprehensive_validation():
        """Run all validation checks and return summary"""
        print("=== DATA QUALITY VALIDATION ===")

        report = DataValidator.generate_quality_report()

        print(f"Predictions: {report['predictions_quality'].get('total_predictions', 0)} total")
        print(".2%")
        print(".1%")
        print(f"System Health: {sum(report['system_health'].values())}/3 components healthy")

        return report

# --- CONFIGURATION ---
BATCH_SIZE = 5      # How many matches to review at the same time
LOOKBACK_LIMIT = 50 # Only check the last 50 eligible matches to prevent infinite backlogs
ENRICHMENT_CONCURRENCY = 4 # Concurrency for enriching past H2H matches

def _load_schedule_db() -> Dict[str, Dict]:
    """Loads the schedules.csv into a dictionary for quick lookups."""
    schedule_db = {}
    if not os.path.exists(SCHEDULES_CSV):
        return {}
    with open(SCHEDULES_CSV, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('fixture_id'):
                schedule_db[row['fixture_id']] = row
    return schedule_db

def get_predictions_to_review() -> List[Dict]:
    """
    Reads the predictions CSV and returns a list of matches that are in the past
    and have not yet been reviewed.
    """
    if not os.path.exists(PREDICTIONS_CSV):
        print(f"[Error] Predictions file not found at: {PREDICTIONS_CSV}")
        return []

    to_review = []
    today = dt.now().date()

    # Load the schedule DB once to avoid repeated file I/O
    schedule_db = _load_schedule_db()

    with open(PREDICTIONS_CSV, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
        
        for row in reversed(all_rows):
            if len(to_review) >= LOOKBACK_LIMIT:
                break

            try:
                match_date_str = row.get('Date') or row.get('date')
                if not match_date_str:
                    continue

                match_date = dt.strptime(match_date_str, "%d.%m.%Y").date()
                status = row.get('status')

                if match_date < today and status not in ['reviewed', 'review_failed']:
                    fixture_id = row.get('fixture_id')
                    # --- OPTIMIZATION: Check local DB first ---
                    if fixture_id and fixture_id in schedule_db:
                        db_entry = schedule_db[fixture_id]
                        if db_entry.get('match_status') == 'finished' and db_entry.get('home_score'):
                            row['actual_score'] = f"{db_entry['home_score']}-{db_entry['away_score']}"
                            row['source'] = 'db' # Mark as found in DB
                            to_review.append(row)
                            continue # Move to next prediction

                    # Fallback to web scraping if not in DB or not finished
                    match_link = row.get('match_link')
                    if match_link and "flashscore" in match_link:
                            to_review.append(row)
            except (ValueError, TypeError):
                continue 

    print(f"[Review] Found {len(to_review)} past predictions to review (Limit: {LOOKBACK_LIMIT}).")
    return to_review

async def get_league_url(page: Page) -> str:
    """
    Extracts the league URL from the match page. Returns empty string if not found.
    """
    try:
        # Look for breadcrumb links to league
        league_link_sel = "a[href*='/football/'][href$='/']"
        league_link = page.locator(league_link_sel).first
        href = await league_link.get_attribute('href', timeout=2000)
        if href:
            return href
    except:
        pass
    return ""

async def get_final_score(page: Page) -> str:
    """
    Extracts the final score. Returns 'Error' if not found.
    """
    try:
        # Check Status
        status_selector = await get_selector_auto(page, "match_page", "meta_match_status") or "div.fixedHeaderDuel__detailStatus"
        try:
            status_text = await page.locator(status_selector).inner_text(timeout=3000)
        except:
            status_text = "finished" 

        if "finished" not in status_text.lower() and "aet" not in status_text.lower() and "pen" not in status_text.lower():
            return "NOT_FINISHED"

        # Extract Score
        home_score_sel = get_selector("match_page", "header_score_home") or "div.detailScore__wrapper > span:nth-child(1)"
        away_score_sel = get_selector("match_page", "header_score_away") or "div.detailScore__wrapper > span:nth-child(3)"

        home_score = await page.locator(home_score_sel).first.inner_text(timeout=2000)
        away_score = await page.locator(away_score_sel).first.inner_text(timeout=2000)

        final_score = f"{home_score.strip() if home_score else ''}-{away_score.strip() if away_score else ''}"
        return final_score

    except Exception as e:
        return "Error"

def update_region_league_url(region_league: str, url: str):
    """
    Updates the url for a region_league in region_league.csv.
    Parses the region_league string to create proper region_league_id.
    """
    if not region_league or not url or " - " not in region_league:
        return

    # Parse region and league from "REGION - LEAGUE" format
    region, league_name = region_league.split(" - ", 1)

    # Create composite ID matching the save_region_league_entry format
    region_league_id = f"{region}_{league_name}".replace(' ', '_').replace('-', '_').upper()

    entry = {
        'region_league_id': region_league_id,
        'region': region.strip(),
        'league_name': league_name.strip(),
        'url': url
    }
    upsert_entry(REGION_LEAGUE_CSV, entry, files_and_headers[REGION_LEAGUE_CSV], 'region_league_id')

def save_single_outcome(match_data: Dict, new_status: str):
    """
    Atomic Upsert to save the review result.
    """
    temp_file = PREDICTIONS_CSV + '.tmp'
    updated = False
    row_id_key = 'ID' if 'ID' in match_data else 'fixture_id'
    target_id = match_data.get(row_id_key)

    try:
        with open(PREDICTIONS_CSV, 'r', encoding='utf-8', newline='') as infile, \
             open(temp_file, 'w', encoding='utf-8', newline='') as outfile:
            
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            if fieldnames is None: # Handle empty file case
                fieldnames = []
            # Ensure fieldnames is a list to use append
            # The original code had an undefined variable 'col'. This line is removed.
            # The fieldnames are implicitly handled by DictWriter based on the first row or provided fieldnames.
            # If new columns are needed, they should be explicitly added to fieldnames before writing the header.
                    
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in reader:
                current_id = row.get('ID') or row.get('fixture_id')
                
                if current_id == target_id:
                    row['status'] = new_status
                    row['actual_score'] = match_data.get('actual_score', 'N/A')
                    
                    if new_status == 'reviewed':
                        try:
                            act_h, act_a = map(int, row['actual_score'].split('-'))
                            act_res = "HOME" if act_h > act_a else "AWAY" if act_a > act_h else "DRAW"
                            
                            pred_str = row.get('Predicted Score') or row.get('predicted_score') or '0-0'
                            if '-' in str(pred_str):
                                pred_h, pred_a = map(int, pred_str.split('-'))
                                pred_res = "HOME" if pred_h > pred_a else "AWAY" if pred_a > pred_h else "DRAW"
                                row['outcome_correct'] = str(act_res == pred_res)
                            else:
                                row['outcome_correct'] = 'N/A'
                        except:
                            row['outcome_correct'] = 'Error'
                    
                    updated = True
                
                writer.writerow(row)

        if updated:
            os.replace(temp_file, PREDICTIONS_CSV)
        else:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
    except Exception as e:
        print(f"    [File Error] Failed to write CSV: {e}")

async def process_review_task(match, browser, semaphore):
    """
    Worker function for a single match review.
    """
    async with semaphore:
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda route: route.abort())
        page = await context.new_page()
        
        match_id = match.get('fixture_id')
        home_team = match.get('home_team', 'Unknown')
        away_team = match.get('away_team', 'Unknown')
        
        try:
            # --- OPTIMIZATION: Handle DB-sourced scores directly ---
            if match.get('source') == 'db':
                print(f"  [DB Check] {home_team} vs {away_team} -> Score: {match['actual_score']}")
                save_single_outcome(match, 'reviewed')
                return

            # --- Web Scraping Fallback ---
            url = match.get('match_link')
            if url and not url.startswith('http'):
                url = f"https://www.flashscore.com{url}"
                
            print(f"  [Web Check] {home_team} vs {away_team}")
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except TimeoutError:
                print(f"    [Timeout] Could not load {url}")
                save_single_outcome({'ID': match_id}, 'review_failed')
                return

            await fs_universal_popup_dismissal(page)

            # Extract league URL and update region_league.csv if applicable
            league_url = await get_league_url(page)
            region_league = match.get('region_league')
            if league_url and region_league:
                update_region_league_url(region_league, league_url)

            final_score = await get_final_score(page)
            
            if final_score == "NOT_FINISHED":
                print(f"    [Skip] Match not finished yet.")
            elif final_score == "Error":
                print(f"    [Fail] Could not extract score.")
                save_single_outcome({'ID': match_id}, 'review_failed')
            else:
                print(f"    [Success] Score: {final_score}")
                match['actual_score'] = final_score
                save_single_outcome(match, 'reviewed')

        except Exception as e:
            print(f"    [Error] {match_id}: {e}")
            save_single_outcome({'ID': match_id}, 'review_failed')
            
        finally:
            await context.close()

async def run_review_process(browser: Browser):
    print("--- LEO V2.5: Outcome Review Engine (Concurrent) ---")
    matches_to_review = get_predictions_to_review()

    if not matches_to_review:
        print("--- No new past matches to review. ---")
        return

    async with async_playwright() as p:
        
        sem = asyncio.Semaphore(BATCH_SIZE)
        tasks = []
        
        print(f"[Processing] Starting batch review for {len(matches_to_review)} matches...")
        
        for match in matches_to_review:
            # THIS WAS THE PROBLEM LINE IN YOUR PREVIOUS FILE
            # It must pass match, browser, and sem
            task = asyncio.create_task(process_review_task(match, browser, sem))
            tasks.append(task)
            
        await asyncio.gather(*tasks)

    # Update learning weights based on reviewed outcomes
    try:
        from Neo.model import LearningEngine, MLModel
        updated_weights = LearningEngine.update_weights()
        print(f"--- Learning Engine: Updated {len(updated_weights)-1} rule weights ---")

        # Train ML models if enough data
        if MLModel.train_models():
            print("--- ML Engine: Retrained models with new data ---")
        else:
            print("--- ML Engine: Insufficient data for retraining ---")

    except Exception as e:
        print(f"--- Learning Engine Error: {e} ---")

    # Efficient Enrichment: Only enrich predicted matches that need verification
    try:
        await selective_enrichment(browser)
    except Exception as e:
        print(f"--- Selective Enrichment Error: {e} ---")

    print("--- Review Process Complete ---")


async def selective_enrichment(browser: Browser):
    """
    Efficiently enrich only the matches that need it for outcome verification.
    Focuses on recent predictions that require final scores for accuracy tracking.
    """
    print("--- Selective Enrichment: Checking recent predictions ---")

    # Only enrich predictions from last 7 days that need verification
    recent_predictions = []
    cutoff_date = (dt.now() - timedelta(days=7)).strftime("%d.%m.%Y")

    with open(PREDICTIONS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('date', '') >= cutoff_date and row.get('outcome_correct') == '':
                recent_predictions.append(row)

    if not recent_predictions:
        print("--- Selective Enrichment: No recent predictions need verification ---")
        return

    print(f"--- Selective Enrichment: Processing {len(recent_predictions)} recent predictions ---")

    # Group by match to avoid duplicates
    matches_to_enrich = {}
    for pred in recent_predictions:
        fixture_id = pred.get('fixture_id')
        if fixture_id and fixture_id not in matches_to_enrich:
            matches_to_enrich[fixture_id] = {
                'fixture_id': fixture_id,
                'match_link': pred.get('match_link'),
                'date': pred.get('date')
            }

    matches_list = list(matches_to_enrich.values())
    print(f"--- Selective Enrichment: {len(matches_list)} unique matches to enrich ---")

    # Enrich with limited concurrency to avoid overwhelming the system
    semaphore = asyncio.Semaphore(2)  # Only 2 concurrent enrichments
    tasks = []

    for match_info in matches_list[:10]:  # Limit to 10 matches per run
        task = asyncio.create_task(enrich_single_match(match_info, browser, semaphore))
        tasks.append(task)

    if tasks:
        await asyncio.gather(*tasks)
        print("--- Selective Enrichment: Complete ---")


async def enrich_single_match(match_info: Dict, browser: Browser, semaphore: asyncio.Semaphore):
    """Enrich a single match with final score and time"""
    async with semaphore:
        url = match_info.get('match_link')
        if not url:
            return

        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda route: route.abort())
        page = await context.new_page()

        try:
            if not url.startswith('http'):
                url = f"https://www.flashscore.com{url}"

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await fs_universal_popup_dismissal(page)

            final_score = await get_final_score(page)
            if final_score not in ["Error", "NOT_FINISHED"]:
                home_score, away_score = final_score.split('-')

                match_info.update({
                    'home_score': home_score.strip(),
                    'away_score': away_score.strip(),
                    'match_status': 'finished'
                })
                save_schedule_entry(match_info)

        except Exception as e:
            pass  # Silently fail for enrichment - not critical
        finally:
            await context.close()

if __name__ == "__main__":
    async def main_test():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await run_review_process(browser)

    asyncio.run(main_test())


async def _enrich_single_match_task(match_info: Dict, browser: Browser, semaphore: asyncio.Semaphore):
    """
    Worker task to visit a single past match URL and extract its final score.
    """
    async with semaphore:
        url = match_info.get('match_link')
        if not url:
            return

        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda route: route.abort())
        page = await context.new_page()

        try:
            if not url.startswith('http'):
                url = f"https://www.flashscore.com{url}"

            await page.goto(url, wait_until="domcontentloaded", timeout=600000)
            await fs_universal_popup_dismissal(page)
            
            final_score = await get_final_score(page)
            match_time_sel = await get_selector_auto(page, "match_page", "meta_match_time")
            full_datetime_str = await page.locator(match_time_sel).inner_text(timeout=2000) if match_time_sel else 'N/A'

            if final_score not in ["Error", "NOT_FINISHED"]:
                home_score, away_score = final_score.split('-')
                
                # --- NEW: Parse both date and time from the full string ---
                date_part = match_info.get('date') # Keep original as fallback
                time_part = '' # Initialize as empty string
                if ' ' in full_datetime_str:
                    date_part, time_part = full_datetime_str.split(' ', 1)
                
                # Ensure date_part and time_part are strings before calling .strip()
                date_part_stripped = date_part.strip() if isinstance(date_part, str) else date_part
                time_part_stripped = time_part.strip() if isinstance(time_part, str) else time_part
                match_info.update({'home_score': home_score.strip(), 'away_score': away_score.strip(), 'date': date_part_stripped, 'match_time': time_part_stripped})
                match_info['match_status'] = 'finished'
                save_schedule_entry(match_info) # UPSERT the entry with the new score
                print(f"      [Enrichment] Updated {match_info['home_team']} vs {match_info['away_team']} with score {final_score}")
        except Exception as e:
            print(f"      [Enrichment Error] Failed to enrich {match_info.get('fixture_id')}: {e}")
        finally:
            await context.close()


async def enrich_past_schedule_entries(past_matches: List[Dict], browser: Browser):
    """
    Takes a list of newly discovered past matches and enriches them with final scores.
    """
    if not past_matches:
        return

    print(f"    [Enrichment] Starting to enrich {len(past_matches)} newly found past matches...")
    
    semaphore = asyncio.Semaphore(ENRICHMENT_CONCURRENCY)
    tasks = [
        _enrich_single_match_task(match, browser, semaphore)
        for match in past_matches if match.get('match_link')
    ]
    await asyncio.gather(*tasks)
    print("    [Enrichment] Past match enrichment complete.")
