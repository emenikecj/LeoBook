# Sites/flashscore.py

import re
import asyncio
from datetime import datetime as dt, timedelta
from zoneinfo import ZoneInfo

from playwright.async_api import Browser, Page, Playwright

from Helpers.DB_Helpers.db_helpers import get_last_processed_info, save_schedule_entry, save_team_entry, save_standings, save_region_league_entry
from Helpers.Site_Helpers.site_helpers import fs_universal_popup_dismissal, click_next_day
from Helpers.utils import BatchProcessor, log_error_state
from Neo.intelligence import analyze_page_and_update_selectors, get_selector_auto
from Neo.selector_manager import SelectorManager
from Helpers.Site_Helpers.Extractors.h2h_extractor import extract_h2h_data, save_extracted_h2h_to_schedules
from Helpers.Site_Helpers.Extractors.standings_extractor import extract_standings_data
from Neo.model import RuleEngine
from Helpers.DB_Helpers.db_helpers import save_prediction
from Helpers.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT
from Helpers.monitor import PageMonitor

# --- CONFIGURATION ---
NIGERIA_TZ = ZoneInfo("Africa/Lagos")

# --- RETRY CONFIGURATION ---
MAX_EXTRACTION_RETRIES = 3
EXTRACTION_RETRY_DELAYS = [5, 10, 15]  # Progressive delays in seconds


async def retry_extraction(extraction_func, *args, **kwargs):
    """
    Retry wrapper for extraction functions with progressive delays.
    Similar to retry mechanism in outcome_reviewer.py
    """
    for attempt in range(MAX_EXTRACTION_RETRIES):
        try:
            return await extraction_func(*args, **kwargs)
        except Exception as e:
            if attempt < MAX_EXTRACTION_RETRIES - 1:
                delay = EXTRACTION_RETRY_DELAYS[attempt]
                print(f"      [Retry] Extraction failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                print(f"      [Retry] Extraction failed after {MAX_EXTRACTION_RETRIES} attempts: {e}")
                raise


async def process_match_task(match_data: dict, browser: Browser):
    """
    Worker function to process a single match in a new page/context.
    """
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Mobile Safari/537.36"
        ),
        timezone_id="Africa/Lagos"
    )
    page = await context.new_page()
    PageMonitor.attach_listeners(page)
    match_label = f"{match_data.get('home_team', 'unknown')}_vs_{match_data.get('away_team', 'unknown')}"


    try:
        print(f"    [Batch Start] {match_data['home_team']} vs {match_data['away_team']}: {match_data['date']} - {match_data['time']}")

        full_match_url = f"{match_data['match_link']}"
        await page.goto(full_match_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
        await asyncio.sleep(2.0) # Optimized from 10.0

        await fs_universal_popup_dismissal(page, "match_page")
        await page.wait_for_load_state("domcontentloaded", timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
        await analyze_page_and_update_selectors(page, "match_page")
        await fs_universal_popup_dismissal(page, "match_page")

        # --- H2H Tab & Expansion ---
        await analyze_page_and_update_selectors(page, "match_page")
        h2h_tab_selector = SelectorManager.get_selector("match_page", "h2h_tab")

        h2h_data = {}
        if h2h_tab_selector and await page.locator(h2h_tab_selector).is_visible(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT):
            try:
                await page.click(h2h_tab_selector, timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                await page.wait_for_load_state("domcontentloaded", timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                await asyncio.sleep(5.0)
                await fs_universal_popup_dismissal(page, "h2h_tab")
                await asyncio.sleep(3.0)  # Shorter wait time

                 # More robust H2H expansion with better error handling
                show_more_selector = "button:has-text('Show more matches'), a:has-text('Show more matches')"
                try:
                    # Wait shorter time and handle case where buttons don't exist
                    await page.wait_for_selector(show_more_selector, timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                    show_more_buttons = page.locator(show_more_selector).first  # Try first one
                    if await show_more_buttons.count() > 0:
                        print("    [H2H Expansion] Expanding available match history...")
                        try:
                            await show_more_buttons.click(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                            await asyncio.sleep(2.0) # Optimized from 5.0

                            # Check if clicking reveals more buttons
                            second_button = page.locator(show_more_selector).nth(1)
                            if await second_button.count() > 0:
                                await second_button.click(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                                await asyncio.sleep(1.0)
                        except Exception:
                            print("    [H2H Expansion] Some expansion buttons failed, but continuing...")
                except Exception:
                    print("    [H2H Expansion] No expansion buttons found or failed to load.")


                await asyncio.sleep(3.0)  # Shorter wait time
                await analyze_page_and_update_selectors(page, "h2h_tab")
                h2h_data = await retry_extraction(extract_h2h_data, page, match_data['home_team'], match_data['away_team'], "h2h_tab")

                h2h_count = len(h2h_data.get("home_last_10_matches", [])) + len(h2h_data.get("away_last_10_matches", [])) + len(h2h_data.get("head_to_head", []))
                print(f"      [OK H2H] H2H tab data extracted for {match_label} ({h2h_count} matches found)")

                # Save the initially extracted (incomplete) H2H matches
                newly_found_past_matches = await save_extracted_h2h_to_schedules(h2h_data)

                # Enrichment DISABLED: Too resource-intensive for prediction workflow
                # Past matches are enriched on-demand during outcome review only
                # if newly_found_past_matches:
                #     await enrich_past_schedule_entries(newly_found_past_matches, browser)

            except Exception as e:
                print(f"      [Warning] Failed to fully load/expand H2H tab for {match_label}: {e}")
        else:
            print(f"      [Warning] H2H tab inaccessible for {match_label}")

        # --- Data Quality Validation ---
        home_form_count = len(h2h_data.get("home_last_10_matches", []))
        away_form_count = len(h2h_data.get("away_last_10_matches", []))
        
        # Require at least 3 matches of history for BOTH teams to consider prediction valid
        if home_form_count < 3 or away_form_count < 3:
            print(f"      [Data Quality] Skipped {match_label}: Insufficient form data (Home: {home_form_count}, Away: {away_form_count})")
            return False

        # --- Standings Tab ---
        standings_tab_selector = SelectorManager.get_selector("match_page", "standings_tab")
        standings_data = []
        standings_league = "Unknown"
        if standings_tab_selector and await page.locator(standings_tab_selector).is_visible(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT):
            try:
                await page.click(standings_tab_selector, timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                await page.wait_for_load_state("domcontentloaded", timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                await analyze_page_and_update_selectors(page, "standings_tab")
                await asyncio.sleep(2.0) # Optimized from 5.0

                await fs_universal_popup_dismissal(page, "standings_tab")
                await asyncio.sleep(3.0)
                standings_result = await retry_extraction(extract_standings_data, page)
                standings_data = standings_result.get("standings", [])
                standings_league = standings_result.get("region_league", "Unknown")
                if standings_league == "Unknown":
                    standings_league = h2h_data.get("region_league", "Unknown")
                standings_league_url = standings_result.get("league_url", "")
                if standings_result.get("has_draw_table"):
                    print(f"      [Skip] Match has draw table, skipping.")
                    return False
                if standings_data and standings_league != "Unknown":
                    # Save standings with URL
                    for row in standings_data:
                        row['url'] = standings_league_url
                    save_standings(standings_data, standings_league)
                    print(f"      [OK Standing] Standings tab data extracted for {standings_league}")
            except Exception as e:
                print(f"      [Warning] Failed to load Standings tab for {match_label}: {e}")

        # --- Process Data & Predict ---
        h2h_league = h2h_data.get("region_league", "Unknown")
        final_league = standings_league if standings_league != "Unknown" else h2h_league

        if final_league != "Unknown":
            match_data["region_league"] = final_league
            print(f"      [Extractor Validation] Updated League to: {final_league}")

            # Parse region and league to save to region_league.csv
            if " - " in final_league:
                region, league = final_league.split(" - ", 1)
                save_region_league_entry({
                    'region': region.strip(),
                    'league_name': league.strip()
                })

        # --- Standings Tab ---
        if standings_data:
            save_standings(standings_data, final_league)
            print(f"      [OK Standing] Standings tab data extracted for {final_league}")

        analysis_input = {"h2h_data": h2h_data, "standings": standings_data}
        prediction = RuleEngine.analyze(analysis_input)

        if prediction.get("type", "SKIP") != "SKIP":
            save_prediction(match_data, prediction)
            print(f"            [OK Signal] {match_label}")
            return True
        else:
            print(f"      [NO Signal] {match_label}")
            return False

    except Exception as e:
        print(f"      [Error] Match failed {match_label}: {e}")
        await log_error_state(page, f"process_match_task_{match_label}", e)
        return False
    finally:
        await asyncio.sleep(1.0) # Optimized from 5.0
        await context.close()



async def extract_matches_from_page(page: Page) -> list:
    """
    Executes JavaScript on the page to extract all match data for the visible day.
    """
    print("    [Extractor] Extracting match data from page...")
    selectors = {
        "match_rows": await get_selector_auto(page, "home_page", "match_rows"),  # type: ignore
        "match_row_home_team_name": await get_selector_auto(page, "home_page", "match_row_home_team_name"),  # type: ignore
        "match_row_away_team_name": await get_selector_auto(page, "home_page", "match_row_away_team_name"),  # type: ignore
        "league_header": await get_selector_auto(page, "home_page", "league_header"),  # type: ignore
        "league_category": await get_selector_auto(page, "home_page", "league_category"),  # type: ignore
        "league_title": await get_selector_auto(page, "home_page", "league_title_link"),  # type: ignore
    }

    return await page.evaluate(
        r"""(selectors) => {
            const matches = [];
            const rows = document.querySelectorAll(selectors.match_rows);

            rows.forEach((row) => {
                const linkEl = row.querySelector('a.eventRowLink') || row.querySelector('a');
                const homeEl = selectors.match_row_home_team_name ? row.querySelector(selectors.match_row_home_team_name) : null;
                let skip_match = false;
                const awayEl = selectors.match_row_away_team_name ? row.querySelector(selectors.match_row_away_team_name) : null;
                const timeEl = row.querySelector('.event__time');
                const rowId = row.getAttribute('id');
                const cleanId = rowId ? rowId.replace('g_1_', '') : null;

                let regionLeague = 'Unknown';
                try {
                    let prev = row.previousElementSibling;
                    while (prev) {
                        if ((selectors.league_header && prev.matches(selectors.league_header)) || prev.classList.contains('event__header')) {
                            const regionEl = selectors.league_category ? prev.querySelector(selectors.league_category) : prev.querySelector('.event__title--type');
                            const leagueEl = selectors.league_title ? prev.querySelector(selectors.league_title) : prev.querySelector('.event__title--name');
                            if (regionEl && leagueEl) {
                                regionLeague = regionEl.innerText.trim() + ' - ' + leagueEl.innerText.trim();
                                const headerText = prev.innerText.toLowerCase();
                                if (headerText.includes('draw')) {
                                    skip_match = true;
                                }
                            } else {
                                regionLeague = prev.innerText.trim().replace(/[\\r\\n]+/g, ' - ');
                            }
                            break;
                        }
                        prev = prev.previousElementSibling;
                    }
                } catch (e) {
                    regionLeague = 'Error Extracting';
                }
                if (linkEl && homeEl && awayEl && cleanId && !skip_match) {
                    const matchLink = linkEl.getAttribute('href');

                    let homeTeamId = null;
                    let awayTeamId = null;
                    let homeTeamUrl = null;
                    let awayTeamUrl = null;

                    if (matchLink) {
                        // 1. Clean the link to handle both relative and absolute URLs
                        // This regex removes everything up to and including "/match/football/"
                        const cleanPath = matchLink.replace(/^(.*\/match\/football\/)/, '');

                        // 2. Now split only the remaining parts (Teams and IDs)
                        // cleanPath is now "gardnersville-ENOwpmY9/heaven-eleven-rZt0bocF/?mid=dzjg0ibm"
                        const parts = cleanPath.split('/').filter(p => p);

                        if (parts.length >= 2) {
                            const homeSegment = parts[0]; // Now this is correctly "gardnersville-ENOwpmY9"
                            const awaySegment = parts[1]; // Now this is correctly "heaven-eleven-rZt0bocF"

                            // Your extraction logic remains the same and is correct:
                            const homeSlug = homeSegment.substring(0, homeSegment.lastIndexOf('-'));
                            homeTeamId = homeSegment.substring(homeSegment.lastIndexOf('-') + 1);

                            const awaySlug = awaySegment.substring(0, awaySegment.lastIndexOf('-'));
                            awayTeamId = awaySegment.substring(awaySegment.lastIndexOf('-') + 1);

                            homeTeamUrl = `https://www.flashscore.com/team/${homeSlug}/${homeTeamId}/`;
                            awayTeamUrl = `https://www.flashscore.com/team/${awaySlug}/${awayTeamId}/`;
                        }
                    }


                    matches.push({
                        id: cleanId,
                        match_link: matchLink,
                        home_team_id: homeTeamId, away_team_id: awayTeamId,
                        home_team_url: homeTeamUrl, away_team_url: awayTeamUrl,
                        home_team: homeEl.innerText.trim(), away_team: awayEl.innerText.trim(),
                        time: timeEl ? timeEl.innerText.trim() : 'N/A',
                        region_league: regionLeague
                    });
                }
            });
            return matches;
        }""", selectors)


async def run_flashscore_analysis(playwright: Playwright):
    """
    Main function to handle Flashscore data extraction and analysis.
    """
    print("\n--- Running Flashscore Analysis ---")

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
    )

    context = None
    try:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            timezone_id="Africa/Lagos"
        )
        page = await context.new_page()
        PageMonitor.attach_listeners(page)
        processor = BatchProcessor(max_concurrent=4)

        total_cycle_predictions = 0

        # --- Navigation & Calibration ---
        print("  [Navigation] Going to Flashscore...")
        # Retry loop for initial navigation to handle network flakes and bot detection
        MAX_RETRIES = 5
        for attempt in range(MAX_RETRIES):
            try:
                await page.goto("https://www.flashscore.com/football/", wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
                print("  [Navigation] Flashscore loaded successfully.")
                break  # Exit loop on success
            except Exception as e:
                print(f"  [Navigation Error] Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    print("  Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    print(f"  [Critical] All navigation attempts failed. Exiting analysis.")
                    await context.close()
                    return
                    
        await analyze_page_and_update_selectors(page, "home_page")
        await fs_universal_popup_dismissal(page, "home_page")

        last_processed_info = get_last_processed_info()

        # --- Daily Loop ---
        for day_offset in range(14):
            target_date = dt.now(NIGERIA_TZ) + timedelta(days=day_offset)
            target_full = target_date.strftime("%d.%m.%Y")
            
            if day_offset > 0:
                match_row_sel = await SelectorManager.get_selector_auto(page, "home_page", "match_rows")
                if not await click_next_day(page, match_row_sel):
                    print("  [Critical] Daily navigation failed. Stopping session.")
                    break
                await asyncio.sleep(2)

            if last_processed_info.get('date_obj') and target_date.date() < last_processed_info['date_obj']:
                print(f"\n--- SKIPPING DAY: {target_full} (advancing to resume date) ---")
                continue

            print(f"\n--- ANALYZING DATE: {target_full} ---")
            await analyze_page_and_update_selectors(page, "home_page")
            await fs_universal_popup_dismissal(page, "home_page")

            try:
                scheduled_tab_sel = await SelectorManager.get_selector_auto(page, "home_page", "tab_scheduled")
                if scheduled_tab_sel and await page.locator(scheduled_tab_sel).is_visible(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT):
                    await page.click(scheduled_tab_sel)
                    print("    [Info] Clicked scheduled tab.")
                    await asyncio.sleep(2.0)
            except Exception:
                print("    [Info] Could not click Scheduled tab.")

            await fs_universal_popup_dismissal(page, "home_page")
            matches_data = await extract_matches_from_page(page)
            
            # --- TIME CLEANING, ADJUSTMENT & SORTING ---
            for m in matches_data:
                original_time_str = m.get('time')
                if original_time_str:
                    clean_time_str = original_time_str.split('\n')[0].strip()
                    m['time'] = clean_time_str if clean_time_str and clean_time_str != 'N/A' else 'N/A'

            matches_data.sort(key=lambda x: x.get('time', '23:59'))

            # --- Save to DB & Filter ---
            valid_matches = []
            now_time = dt.now(NIGERIA_TZ).time()
            is_today = target_date.date() == dt.now(NIGERIA_TZ).date()

            for m in matches_data:
                m['date'] = target_full
                save_schedule_entry({
                    'fixture_id': m.get('id'), 'date': m.get('date'), 'match_time': m.get('time'),
                    'region_league': m.get('region_league'), 'home_team': m.get('home_team'),
                    'away_team': m.get('away_team'), 'home_team_id': m.get('home_team_id'),
                    'away_team_id': m.get('away_team_id'), 'match_status': 'scheduled',
                    'match_link': m.get('match_link')
                })
                save_team_entry({'team_id': m.get('home_team_id'), 'team_name': m.get('home_team'), 'region_league': m.get('region_league'), 'team_url': m.get('home_team_url')})
                save_team_entry({'team_id': m.get('away_team_id'), 'team_name': m.get('away_team'), 'region_league': m.get('region_league'), 'team_url': m.get('away_team_url')})

                if is_today:
                    try:
                        if m.get('time') and m['time'] != 'N/A' and dt.strptime(m['time'], '%H:%M').time() > now_time:
                            valid_matches.append(m)
                    except ValueError:
                        pass # Ignore matches with invalid time format for today
                else:
                    valid_matches.append(m)

            if is_today:
                print(f"    [Time Filter] Removed {len(matches_data) - len(valid_matches)} past matches for today.")
            
            print(f"    [Matches Found] {len(valid_matches)} valid fixtures. (Sorted by Time)")

            # --- Resume Logic ---
            if last_processed_info.get('date') == target_full:
                last_id = last_processed_info.get('id')
                print(f"    [Resume] Checking for last processed ID: {last_id} on this date.")
                try:
                    found_index = [i for i, match in enumerate(valid_matches) if match.get('id') == last_id][0]
                    print(f"    [Resume] Match found at index {found_index}. Skipping {found_index + 1} previously processed matches.")
                    valid_matches = valid_matches[found_index + 1:]
                except IndexError:
                    print(f"    [Resume] Last processed ID {last_id} not found in current scan. Proceeding with all {len(valid_matches)} valid matches found (already time-filtered).")
                    # We do not slice here because valid_matches is already filtered by time (> now) for today.
                    # If we lost the ID (e.g. because of time gap), we simply pick up everything that is currently valid.
                     

            # --- Batch Processing ---
            if valid_matches:
                print(f"    [Batching] Processing {len(valid_matches)} matches concurrently...")
                results = await processor.run_batch(valid_matches, process_match_task, browser=browser)
                total_cycle_predictions += sum(1 for r in results if r)
            else:
                print("    [Info] No new matches to process for this day.")

    finally:
        if context is not None:
            await context.close()
        if 'browser' in locals():
             await browser.close()
             
    print(f"\n--- Flashscore Analysis Complete: {total_cycle_predictions} new predictions found. ---")
    return
