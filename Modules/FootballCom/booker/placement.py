# placement.py: placement.py: Final bet submission and stakeholder management.
# Part of LeoBook Modules — Football.com Booking
#
# Functions: ensure_bet_insights_collapsed(), expand_collapsed_market(), place_bets_for_matches(), calculate_kelly_stake(), place_multi_bet_from_codes()

"""
Bet Placement Orchestration
Handles adding selections to the slip and finalizing accumulators with robust verification.
"""

import asyncio
from typing import List, Dict
from playwright.async_api import Page
from Core.Browser.site_helpers import get_main_frame
from Data.Access.db_helpers import update_prediction_status
from Core.Utils.utils import log_error_state, capture_debug_snapshot
from Core.Intelligence.selector_manager import SelectorManager
from Core.Intelligence.intelligence import fb_universal_popup_dismissal as neo_popup_dismissal
from Core.Intelligence.aigo_suite import AIGOSuite
from .ui import wait_for_condition
from .mapping import find_market_and_outcome
from .slip import get_bet_slip_count, force_clear_slip
from Data.Access.db_helpers import log_audit_event

# Confidence → probability mapping (matches data_validator.py)
CONFIDENCE_TO_PROB = {
    "Very High": 0.80,
    "High": 0.65,
    "Medium": 0.50,
    "Low": 0.35,
}

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
                 await target_header.click()
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
                    await page.locator(search_icon).first.click()
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
                         await outcome_btn.click()
                    else:
                         # Strategy B: Row based fallback
                         row_sel = SelectorManager.get_selector_strict("fb_match_page", "match_market_table_row")
                         if row_sel:
                             # Find row containing outcome text
                             target_row = page.locator(row_sel).filter(has_text=o_name).first
                             if await target_row.count() > 0:
                                  print(f"    [Selection] Found outcome row for '{o_name}'")
                                  await target_row.click()
                    
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


def calculate_kelly_stake(balance: float, odds: float, probability: float = 0.60) -> int:
    """
    Calculates fractional Kelly stake (v2.7).
    Formula: 0.25 * ((probability * odds - 1) / (odds - 1))
    Where edge = probability - (1/odds)
    """
    if odds <= 1.0: return max(1, int(balance * 0.01))
    
    # edge = probability - (1.0 / odds)
    # full_kelly = edge / (1 - (1/odds)) # This is another way to write it
    # Simplified version matching user request:
    numerator = (probability * odds) - 1
    denominator = odds - 1
    
    if denominator <= 0: return max(1, int(balance * 0.01))
    
    full_kelly = numerator / denominator
    
    # Applied Fractional Kelly (0.25)
    applied_stake = 0.25 * full_kelly * balance
    
    # Clamp rules: Min = max(1% balance, 1), Max = 50% balance
    min_stake = int(max(1, balance * 0.01))
    max_stake = int(balance * 0.50)
    
    final_stake = int(max(min_stake, min(applied_stake, max_stake)))
    return final_stake


@AIGOSuite.aigo_retry(max_retries=2, delay=3.0, context_key="fb_match_page", element_key="betslip_place_bet_button")
async def place_multi_bet_from_codes(page: Page, harvested_matches: List[Dict], current_balance: float) -> bool:
    """
    Chapter 2A (Automated Booking) with AIGO protection.
    """
    if not harvested_matches:
        print("    [Execute] No harvested matches to place.")
        return False

    final_codes = harvested_matches[:12]
    print(f"\n   [Execute] Starting execution for {len(final_codes)} matches...")
    
    await force_clear_slip(page)

    # 2. Add via URL
    for m in final_codes:
        code = m.get('booking_code')
        if not code: continue
        url = f"https://www.football.com/ng/m?shareCode={code}"
        print(f"    [Execute] Injecting code {code}...")
        await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        await asyncio.sleep(1.5)

    # 3. Verify Count
    total_in_slip = await get_bet_slip_count(page)
    if total_in_slip < 1:
        raise ValueError("Slip is empty after injection.")

    # 4. Calculate Stake
    total_odds = 1.0
    total_prob = 1.0
    for m in final_codes:
        total_odds *= float(m.get('odds', 1.5))
        p = CONFIDENCE_TO_PROB.get(m.get('confidence', 'Medium'), 0.50)
        total_prob *= p
    
    final_stake = calculate_kelly_stake(current_balance, total_odds, probability=max(total_prob, 0.01))
    print(f"    [Execute] Final Stake: ₦{final_stake}")

    # 5. Open Slip Drawer
    slip_trigger = SelectorManager.get_selector_strict("fb_match_page", "slip_trigger_button")
    await page.locator(slip_trigger).first.click()
    slip_sel = SelectorManager.get_selector_strict("fb_match_page", "slip_drawer_container")
    await page.wait_for_selector(slip_sel, state="visible", timeout=15000)

    # 6. Fill Stake
    amount_input = SelectorManager.get_selector_strict("fb_match_page", "betslip_stake_input")
    await page.locator(amount_input).first.fill(str(final_stake))
    await asyncio.sleep(1)

    # 7. Place and Confirm
    place_btn = SelectorManager.get_selector_strict("fb_match_page", "betslip_place_bet_button")
    await page.locator(place_btn).first.click(force=True)
    await asyncio.sleep(3)
    
    # 8. Success Check
    from ..navigator import extract_balance
    new_balance = await extract_balance(page)
    if new_balance >= (current_balance - (final_stake * 0.5)):
        raise ValueError("Balance did not decrease sufficiently. Placement likely failed.")

    print(f"    [Execute Success] Multi-bet placed! New Balance: ₦{new_balance:.2f}")
    
    # Update Statuses
    from Data.Access.db_helpers import update_site_match_status, update_prediction_status, log_audit_event
    for m in final_codes:
        update_site_match_status(m['site_match_id'], status='booked')
        if m.get('fixture_id'):
            update_prediction_status(m['fixture_id'], m['date'], 'booked')
    
    log_audit_event("BET_PLACEMENT", f"Multi-bet ({len(final_codes)} matches) placed.", current_balance, new_balance, float(final_stake))
    return True

