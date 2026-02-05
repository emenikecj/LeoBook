# booking_code.py: Bet code generation and betslip preparation.
# Refactored for Clean Architecture (v2.7)
# This script searches for outcomes and retrieves the shareable booking codes.

"""
Booking Code Extractor
Handles the specific logic for Phase 2a: Harvest.
Visits a match, books a single bet, extracts the code, and saves it.
"""

import asyncio
import re
from typing import Dict, Optional, Tuple
from playwright.async_api import Page
from Core.Intelligence.selector_manager import SelectorManager
from .ui import robust_click
from .slip import force_clear_slip
from Data.Access.db_helpers import update_site_match_status, update_prediction_status


async def get_outcome_odds(loc):
    try:
        odds_text = await loc.evaluate('el => el.nextElementSibling?.innerText || ""')
        return float(odds_text.replace(",", ".").strip()) if odds_text else 0.0
    except:
        return 0.0


async def harvest_single_match_code(page: Page, match: Dict, prediction: Dict) -> bool:
    """
    Robust Phase 2a Harvest with extended timeouts, animation delays, fallbacks, and retries.
    """
    fixture_id = prediction.get('fixture_id')
    url = match.get('url')
    outcome = prediction.get('prediction')

    print(f"\n   [Harvest] Starting for fixture {fixture_id} - {url}")

    for attempt in range(1, 4):  # Full retry loop
        try:
            # Pre-clear
            await force_clear_slip(page)
            await asyncio.sleep(3)

            # Navigate & stabilize
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(
                SelectorManager.get_selector_strict("fb_match_page", "match_header"),
                timeout=30000
            )
            await page.screenshot(path=f"Logs/Debug/harvest_pre_{fixture_id}_attempt{attempt}.png")

            # Click search icon
            search_icon = SelectorManager.get_selector_strict("fb_match_page", "search_icon")
            await robust_click(page.locator(search_icon).first, page, timeout=15000)
            await asyncio.sleep(3)  # Critical animation delay

            # Wait for input with fallbacks
            input_selectors = [
                SelectorManager.get_selector_strict("fb_match_page", "search_input"),
                'input[type="search"]',
                'input[placeholder*="search" i]',
                'input[aria-label*="search" i]'
            ]
            search_input = None
            for sel in input_selectors:
                loc = page.locator(sel).first
                try:
                    await loc.wait_for(state="visible", timeout=15000)
                    search_input = loc
                    break
                except:
                    continue

            if not search_input:
                raise TimeoutError("Search input not visible after fallbacks")

            from .mapping import find_market_and_outcome
            market_name, _ = await find_market_and_outcome(prediction)
            if not market_name: market_name = outcome

            await search_input.fill(market_name)
            await search_input.press("Enter")
            await asyncio.sleep(2)

            # Wait for market results
            market_container = SelectorManager.get_selector_strict("fb_match_page", "market_container") or ".markets-container"
            await page.wait_for_selector(market_container, timeout=15000)

            # Expand market if collapsed
            header_sel = SelectorManager.get_selector_strict("fb_match_page", "market_header")
            if await page.locator(header_sel).is_visible(timeout=5000):
                await robust_click(page.locator(header_sel).first, page)
                await asyncio.sleep(2)

            # Select outcome with fallbacks
            outcome_selectors = [
                f'button:has-text("{outcome}")',
                f'.match-market-row:has-text("{outcome}")',
                f'div:has-text("{outcome}")'
            ]
            outcome_loc = None
            for sel in outcome_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    outcome_loc = loc
                    break

            if not outcome_loc:
                raise ValueError(f"Outcome '{outcome}' not found")

            # Odds check (parse adjacent odds)
            odds_text = await outcome_loc.evaluate(
                "el => el.parentElement.querySelector('.odds, .coefficient')?.innerText || '0'"
            )
            odds = float(re.sub(r"[^\d.]", "", odds_text)) if odds_text else 0.0
            if odds < 1.20:
                print(f"    [Harvest Skip] Low odds: {odds}")
                update_prediction_status(fixture_id, prediction.get('date'), "skipped_low_odds")
                return False

            await outcome_loc.scroll_into_view_if_needed()
            await outcome_loc.click(timeout=10000)
            await asyncio.sleep(3)
            await page.wait_for_selector("fb_match_page.bet_slip_container", timeout=15000)

            # Book Bet & Extract
            book_btn_sel = SelectorManager.get_selector_strict("fb_match_page", "book_bet_button")
            await robust_click(page.locator(book_btn_sel).first, page)
            await page.wait_for_selector("fb_match_page.booking_modal", timeout=20000)
            code = await page.inner_text("fb_booking_share_page.booking_code_text", timeout=10000)
            booking_url = await page.get_attribute("fb_booking_share_page.booking_share_link", "href") or f"https://www.football.com/ng/m?shareCode={code}"

            # Save
            from Data.Access.db_helpers import append_or_update
            append_or_update("football_com_matches.csv", fixture_id, {
                "booking_code": code,
                "booking_url": booking_url,
                "status": "harvested"
            })

            # Dismiss & post-clear
            dismiss_sel = SelectorManager.get_selector("fb_match_page", "modal_dismiss") or "fb_match_page.modal_dismiss"
            await robust_click(page.locator(dismiss_sel).first, page)
            await force_clear_slip(page)

            print(f"    [Harvest Success] Code: {code}")
            await page.screenshot(path=f"Logs/Debug/harvest_success_{fixture_id}.png")
            log_state("Harvest", f"Success {fixture_id}", f"Code: {code}")
            return True

        except Exception as e:
            print(f"    [Harvest Retry] Attempt {attempt} failed: {str(e)}")
            await page.screenshot(path=f"Logs/Debug/harvest_fail_attempt{attempt}_{fixture_id}.png")
            await asyncio.sleep(10)

    print(f"    [Harvest Failed] {fixture_id} after 3 attempts")
    update_prediction_status(fixture_id, prediction.get('date'), "failed_harvest")
    log_state("Harvest", f"Failed {fixture_id}", "All attempts failed")
    return False

    
from .mapping import find_market_and_outcome

async def expand_collapsed_market(page: Page, market_name: str):
    """If a market is found but collapsed, expand it."""
    try:
        header_sel = SelectorManager.get_selector("fb_match_page", "market_header")
        if header_sel:
             target_header = page.locator(header_sel).filter(has_text=market_name).first
             if await target_header.count() > 0:
                 print(f"    [Market] Clicking market header for '{market_name}' to ensure expansion...")
                 await robust_click(target_header, page)
                 await asyncio.sleep(1)
    except Exception as e:
        print(f"    [Market] Expansion failed: {e}")

async def select_outcome(page: Page, prediction: Dict) -> bool:
    """
    Safe outcome selection with odds check (v2.7).
    1. Maps prediction -> generic names.
    2. Searches/Locates market (expands if collapsed).
    3. Finds outcome button.
    4. Extracts odds -> skips if < 1.20.
    5. Clicks and verifies.
    """
    from .mapping import find_market_and_outcome
    
    # 1. Map Prediction
    m_name, o_name = await find_market_and_outcome(prediction)
    if not m_name:
        print(f"    [Selection Error] No mapping for pred: {prediction.get('prediction')}")
        return False

    try:
        # 2. Expand Market if needed
        # We look for the market header and click if it's not 'open'
        header_sel = SelectorManager.get_selector_strict("fb_match_page", "market_group_header")
        market_container = page.locator(header_sel).filter(has_text=m_name).first
        
        if await market_container.count() > 0:
            # Scroll it into view
            await market_container.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)

            # Check if collapsed (often has a specific class or child icon)
            is_collapsed = await market_container.locator(".collapsed").count() > 0 or \
                           await market_container.locator(".icon-arrow-down").count() > 0
            
            if is_collapsed:
                print(f"    [Selection] Market '{m_name}' is collapsed. Expanding...")
                await robust_click(market_container, page)
                await asyncio.sleep(1.5)
        else:
            # Proactive Search: Use the Site's Search Functionality (User Request)
            print(f"    [Selection] Market '{m_name}' not found. Attempting search-based discovery...")
            
            search_btn_sel = SelectorManager.get_selector_strict("fb_match_page", "match_market_search_icon_button") or \
                             SelectorManager.get_selector_strict("fb_match_page", "search_icon")
            search_input_sel = SelectorManager.get_selector_strict("fb_match_page", "match_market_search_input") or \
                               SelectorManager.get_selector_strict("fb_match_page", "search_input")
            
            if search_btn_sel and await page.locator(search_btn_sel).count() > 0:
                 try:
                     # Force click to bypass transparent overlays
                     await page.locator(search_btn_sel).first.click(force=True)
                     await asyncio.sleep(1)
                     
                     # Wait for input to be truly interactable
                     await page.wait_for_selector(search_input_sel, state="visible", timeout=3000)
                     
                     if await page.locator(search_input_sel).count() > 0:
                         print(f"    [Search] Searching for '{m_name}'...")
                         await page.locator(search_input_sel).click() # Focus
                         await page.locator(search_input_sel).fill(m_name)
                         await page.keyboard.press("Enter")
                         # Give time for results to render
                         await asyncio.sleep(2.5) 
                         
                         # Re-verify market container after search
                         market_container = page.locator(header_sel).filter(has_text=m_name).first
                         if await market_container.count() > 0:
                             await market_container.scroll_into_view_if_needed()
                             print(f"    [Search] Found market '{m_name}' via search.")
                         else:
                             print(f"    [Search] Market '{m_name}' still not found after search.")
                 except Exception as e:
                     print(f"    [Search Error] Failed during search flow: {e}")

            # Fallback Proactive Scroll if Search failed or wasn't available
            if await market_container.count() == 0:
                print(f"    [Selection] Attempting proactive scroll search as final fallback...")
                potential_headers = page.locator(header_sel)
                for i in range(await potential_headers.count()):
                    h = potential_headers.nth(i)
                    txt = await h.inner_text()
                    if m_name.upper() in txt.upper():
                        await h.scroll_into_view_if_needed()
                        await robust_click(h, page)
                        await asyncio.sleep(1.5)
                        market_container = h
                        break
            
            if await market_container.count() == 0:
                print(f"    [Selection Error] Market '{m_name}' not found after all discovery attempts.")
                return False

        # 3. Locate Outcome Button & Check Odds
        # We look for ANY clickable element containing the outcome name precisely or as a word
        # Priority: Exact match in a child span/div, then has-text
        outcome_btn = page.locator(f"//div[contains(@class, 'm-outcome-item')]//*[normalize-space()='{o_name}']").first
        
        # Fallback 1: button or div with role button
        if await outcome_btn.count() == 0:
            btn_sel = f"button:has-text('{o_name}'), div[role='button']:has-text('{o_name}'), .m-outcome-item:has-text('{o_name}')"
            outcome_btn = page.locator(btn_sel).filter(has_text=re.compile(f"^{o_name}$|^{o_name}\\s|\\s{o_name}$")).first

        if await outcome_btn.count() == 0:
            print(f"    [Selection Error] Outcome button '{o_name}' not found.")
            return False

        # Extract Odds
        odds_text = await outcome_btn.inner_text()
        # regex for float numbers
        odds_match = re.search(r'(\d+\.\d+)', odds_text)
        if odds_match:
            odds_val = float(odds_match.group(1))
            if odds_val < 1.20:
                print(f"    [Selection Skip] Odds {odds_val} for '{o_name}' are < 1.20 limit.")
                return False
            print(f"    [Selection] Found odds: {odds_val} for '{o_name}'.")
        else:
             print(f"    [Selection Warning] Could not parse odds from '{odds_text}'. Proceeding with caution.")

        # 4. Click
        await robust_click(outcome_btn, page)
        await asyncio.sleep(0.5)
        
        # Simple verification: button usually changes color or gets a specific class when selected
        # But we'll rely on the slip counter verification in the main harvester
        return True

    except Exception as e:
        print(f"    [Selection Error] Logic failed: {e}")
        return False


async def extract_booking_info(page: Page) -> Tuple[str, str]:
    """
    Pulls code & URL from the Book Bet modal (v2.7).
    Returns (code, url) or ("", "") if failed.
    """
    modal_sel = SelectorManager.get_selector_strict("fb_match_page", "booking_code_modal")
    code_sel = SelectorManager.get_selector_strict("fb_match_page", "booking_code_text")
    
    try:
        # Wait for modal
        await page.wait_for_selector(modal_sel, state="visible", timeout=15000)
        
        # Extract code with retries
        code_text = ""
        for _ in range(5):
             code_text = (await page.locator(code_sel).first.inner_text(timeout=2000)).strip()
             if code_text and len(code_text) >= 5:
                 break
             await asyncio.sleep(1)
        
        if not code_text:
            return "", ""
            
        booking_url = f"https://www.football.com/ng/m?shareCode={code_text}"
        return code_text, booking_url

    except Exception as e:
        print(f"    [Extraction Error] Modal extraction failed: {e}")
        return "", ""


    return False
