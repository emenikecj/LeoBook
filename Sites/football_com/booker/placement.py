"""
Bet Placement Orchestration
Handles adding selections to the slip and finalizing accumulators with robust verification.
"""

import asyncio
from typing import List, Dict
from playwright.async_api import Page
from Helpers.Site_Helpers.site_helpers import get_main_frame
from Helpers.DB_Helpers.db_helpers import update_prediction_status
from Helpers.utils import log_error_state, capture_debug_snapshot
from Neo.selector_manager import SelectorManager
from Neo.intelligence import fb_universal_popup_dismissal as neo_popup_dismissal
from .ui import robust_click, wait_for_condition
from .mapping import find_market_and_outcome
from .slip import get_bet_slip_count, force_clear_slip

async def ensure_bet_insights_collapsed(page: Page):
    """Ensure the bet insights widget is collapsed."""
    try:
        arrow_sel = SelectorManager.get_selector_strict("fb_match_page", "match_smart_picks_arrow_expanded")
        if arrow_sel and await page.locator(arrow_sel).count() > 0 and await page.locator(arrow_sel).is_visible():
            print("    [UI] Collapsing Bet Insights widget...")
            await page.locator(arrow_sel).first.click()
            await asyncio.sleep(1)
    except Exception:
        pass

async def expand_collapsed_market(page: Page, market_name: str):
    """If a market is found but collapsed, expand it."""
    try:
        # Use knowledge.json key for generic market header or title
        # Then filter by text
        header_sel = SelectorManager.get_selector_strict("fb_match_page", "market_header")
        if header_sel:
             # Find header containing market name
             target_header = page.locator(header_sel).filter(has_text=market_name).first
             if await target_header.count() > 0:
                 # Check if it needs expansion (often indicated by an icon or state, but clicking usually toggles)
                 # We can just click it if we don't see outcomes.
                 # Heuristic: Validating visibility of outcomes is better done by the caller.
                 # This function explicitly toggles.
                 print(f"    [Market] Clicking market header for '{market_name}' to ensure expansion...")
                 await robust_click(target_header, page)
                 await asyncio.sleep(1)
    except Exception as e:
        print(f"    [Market] Expansion failed: {e}")

async def place_bets_for_matches(page: Page, matched_urls: Dict[str, str], day_predictions: List[Dict], target_date: str):
    """Visit matched URLs and place bets with strict verification."""
    MAX_BETS = 40
    processed_urls = set()

    for match_id, match_url in matched_urls.items():
        # Check betslip limit
        if await get_bet_slip_count(page) >= MAX_BETS:
            print(f"[Info] Slip full ({MAX_BETS}). Finalizing accumulator.")
            success = await finalize_accumulator(page, target_date)
            if success:
                # If finalized, we can continue filling a new slip?
                # User flow suggests one slip per day usually, but let's assume valid.
                pass
            else:
                 print("[Error] Failed to finalize accumulator. Aborting further bets.")
                 break

        if not match_url or match_url in processed_urls: continue
        
        pred = next((p for p in day_predictions if str(p.get('fixture_id', '')) == str(match_id)), None)
        if not pred or pred.get('prediction') == 'SKIP': continue

        processed_urls.add(match_url)
        print(f"[Match] Processing: {pred['home_team']} vs {pred['away_team']}")

        try:
            # 1. Navigation
            await page.goto(match_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)
            await neo_popup_dismissal(page, match_url)
            await ensure_bet_insights_collapsed(page)

            # 2. Market Mapping
            m_name, o_name = await find_market_and_outcome(pred)
            if not m_name:
                print(f"    [Info] No market mapping for {pred.get('prediction')}")
                continue

            # 3. Search for Market
            search_icon = SelectorManager.get_selector_strict("fb_match_page", "search_icon")
            search_input = SelectorManager.get_selector_strict("fb_match_page", "search_input")
            
            if search_icon and search_input:
                if await page.locator(search_icon).count() > 0:
                    await robust_click(page.locator(search_icon).first, page)
                    await asyncio.sleep(1)
                    
                    await page.locator(search_input).fill(m_name)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(2)
                    
                    # Handle Collapsed Market: Try to find header and click if outcomes not immediately obvious
                    # (Skipping complex check, just click header if name exists)
                    await expand_collapsed_market(page, m_name)

                    # 4. Select Outcome
                    # Try strategies: Exact Text Button -> Row contains text
                    outcome_added = False
                    initial_count = await get_bet_slip_count(page)
                    
                    # Strategy A: Button with precise text
                    outcome_btn = page.locator(f"button:text-is('{o_name}'), div[role='button']:text-is('{o_name}')").first
                    if await outcome_btn.count() > 0 and await outcome_btn.is_visible():
                         print(f"    [Selection] Found outcome button '{o_name}'")
                         await robust_click(outcome_btn, page)
                    else:
                         # Strategy B: Row based fallback
                         row_sel = SelectorManager.get_selector_strict("fb_match_page", "match_market_table_row")
                         if row_sel:
                             # Find row containing outcome text
                             target_row = page.locator(row_sel).filter(has_text=o_name).first
                             if await target_row.count() > 0:
                                  print(f"    [Selection] Found outcome row for '{o_name}'")
                                  await robust_click(target_row, page)
                    
                    # 5. Verification Loop
                    for _ in range(3):
                        await asyncio.sleep(1)
                        new_count = await get_bet_slip_count(page)
                        if new_count > initial_count:
                            print(f"    [Success] Outcome '{o_name}' added. Slip count: {new_count}")
                            outcome_added = True
                            update_prediction_status(match_id, target_date, 'added_to_slip')
                            break
                    
                    if not outcome_added:
                        print(f"    [Error] Failed to add outcome '{o_name}'. Slip count did not increase.")
                        update_prediction_status(match_id, target_date, 'failed_add')
                
                else:
                    print("    [Error] Search icon not found.")
            else:
                 print("    [Error] Search selectors missing configuration.")

        except Exception as e:
            print(f"    [Match Error] {e}")
            await capture_debug_snapshot(page, f"error_{match_id}", str(e))


async def place_multi_bet_from_codes(page: Page, harvested_codes: List[str], current_balance: float):
    """
    Phase 2b (Execute):
    1. Filter codes (Validation).
    2. Add max 12 selections to slip (via URL param).
    3. Calculate stake (min 1% or N1, max 50% balance).
    4. Place bet and Verify.
    """
    if not harvested_codes:
        print("    [Execute] No codes to place.")
        return

    # A. Validate & Limit
    # For now, just take first 12 valid codes
    final_codes = harvested_codes[:12]
    print(f"    [Execute] Building Multi with {len(final_codes)} selections: {final_codes}")

    # B. Add to Slip Loop
    # Strategy: Visit each ?shareCode=URL to add them.
    # Note: Football.com usually adds to slip when visiting shareCode link.
    # We must ensure we don't clear slip between these!
    
    # First one clears? No, rely on force_clear_slip having run BEFORE state 2b.
    # Actually, we should force clear once before starting the build.
    await clear_bet_slip(page) # Use simple clear, or force.
    
    added_count = 0
    for code in final_codes:
        if not code: continue
        
        # Construct Load URL
        load_url = f"https://www.football.com/ng/m?shareCode={code}"
        try:
            print(f"    [Execute] Loading selection {code}...")
            await page.goto(load_url, timeout=30000, wait_until='domcontentloaded')
            # Wait for "Betslip count increased" or generic wait
            await asyncio.sleep(2) 
            
            # Simple check: Does count increase?
            # Optimization: Just proceed, verify count at end.
            added_count += 1
        except Exception as e:
            print(f"    [Execute Error] Failed to load code {code}: {e}")

    # C. Verify Slip Count
    total_in_slip = await get_bet_slip_count(page)
    print(f"    [Execute] Slip Count: {total_in_slip} (Expected ~{len(final_codes)})")
    
    if total_in_slip < 1:
        print("    [Execute Failure] No bets in slip after loading codes.")
        return

    # D. Open Slip & Finalize
    # 1. Open Slip
    slip_trigger = SelectorManager.get_selector_strict("fb_match_page", "slip_trigger_button")
    if slip_trigger and await page.locator(slip_trigger).count() > 0:
            await robust_click(page.locator(slip_trigger).first, page)
            await asyncio.sleep(2)
    else:
        print("    [Execute Error] Could not open slip.")
        return

    # 2. Select Multiple Tab (if exists/needed)
    # usually defaults to accumulator if multiple items

    # 3. Calculate Stake
    # Rules: Min N1, Max 50% balance
    min_stake = 1 # N1
    max_stake = current_balance * 0.50
    # Proposed: 1% of balance or N100, clamped
    raw_stake = max(100, current_balance * 0.01) 
    final_stake = max(min_stake, min(raw_stake, max_stake))
    final_stake_str = str(int(final_stake)) # Integer N
    
    print(f"    [Execute] Stake Calculation: Bal={current_balance} -> Stake={final_stake_str}")

    # 4. Enter Stake
    stake_input = SelectorManager.get_selector("fb_match_page", "betslip_stake_input")
    if stake_input and await page.locator(stake_input).count() > 0:
            await page.locator(stake_input).first.fill(final_stake_str)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)
    else:
            print("    [Execute Error] Stake input not found!")
            return

    # 5. Place Bet
    place_btn = SelectorManager.get_selector("fb_match_page", "betslip_place_bet_button")
    if place_btn and await page.locator(place_btn).count() > 0:
            print("    [Execute] Clicking Place Bet...")
            await robust_click(page.locator(place_btn).first, page)
            await asyncio.sleep(3)
            
            # 6. Confirm (if dialog)
            confirm_btn = SelectorManager.get_selector("fb_match_page", "confirm_bet_button")
            if confirm_btn and await page.locator(confirm_btn).count() > 0:
                if await page.locator(confirm_btn).first.is_visible():
                    print("    [Execute] Confirming bet...")
                    await robust_click(page.locator(confirm_btn).first, page)
                    await asyncio.sleep(5)
            
            # 7. Verification (Balance Check)
            from ..navigator import extract_balance
            post_balance = await extract_balance(page)
            if post_balance < current_balance:
                print(f"    [Execute Success] Bet Placed! New Balance: {post_balance}")
                # Save Screenshot
                from Helpers.utils import take_screenshot
                await take_screenshot(page, "multi_success")
            else:
                 print("    [Execute Warning] Balance did not decrease. Bet might have failed.")
    else:
            print("    [Execute Error] Place button not found.")

