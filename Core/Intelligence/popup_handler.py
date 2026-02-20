# popup_handler.py: popup_handler.py: Orchestration layer for the popup dismissal system.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: PopupHandler

"""
Popup Handler Module - MODULAR VERSION
Orchestrates modular popup dismissal components with layered fallback strategy.
Implements Phase 2 Football.com integration with intelligent popup resolution.
"""

import asyncio
from typing import Dict, Any, Optional

from .popup_detector import PopupDetector
from .selector_manager import SelectorManager
from .leo_popup_analyzer import LeoPopupAnalyzer
from .popup_executor import PopupExecutor


class PopupHandler:
    """
    Modular popup handler with layered fallback strategy.

    Implements 5-step dismissal process:
    1. Standard dismissal (context-aware selectors)
    2. AI analysis (Leo AI vision)
    3. Force dismissal (JavaScript injection, layered modal handling)
    4. Comprehensive fallback (all known selectors)
    5. Continuous monitoring (optional)
    """

    def __init__(self):
        self.detector = PopupDetector()
        self.selector_manager = SelectorManager()
        self.leo_analyzer = LeoPopupAnalyzer()  # Optional - requires API key
        self.executor = PopupExecutor()

    async def fb_universal_popup_dismissal(
        self,
        page,
        url: str = "",
        screenshot_path: Optional[str] = None,
        monitor_interval: int = 0,
    ) -> Dict[str, Any]:
        """
        Universal popup dismissal with modular layered fallback strategy.
        Implements Phase 2 Football.com integration with priority selectors.

        Args:
            page: Playwright page object
            url: Page URL for context detection
            screenshot_path: Path to screenshot (optional, auto-captured if needed)
            monitor_interval: Seconds between checks (0 = single run)

        Returns:
            dict: Dismissal result with method used and success status
        """

        # Initialize result structure
        result = {
            'success': False,
            'method': 'none',
            'selector_used': None,
            'error': None,
            'url': url,
            'context': self.detector.detect_context(url)
        }

        try:
            # Continuous monitoring mode
            if monitor_interval > 0:
                await self.continuous_monitoring(page, url, monitor_interval)
                result['method'] = 'continuous_monitoring'
                result['success'] = True
                return result

            # Single dismissal attempt with layered fallback
            dismissal_result = await self._execute_layered_dismissal(page, url, screenshot_path)
            result.update(dismissal_result)

            return result

        except Exception as e:
            result['error'] = f"Popup dismissal failed: {str(e)}"
            print(f"[AI Pop-up] Critical error: {e}")
            return result

    async def _execute_layered_dismissal(
        self,
        page,
        url: str,
        screenshot_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute 5-step layered dismissal strategy

        Returns:
            dict: Result of dismissal attempt
        """
        context = self.detector.detect_context(url)

        # Step 1: Analyze HTML content for popup structure
        html_content = await page.content()
        analysis = self.detector.analyze_html(html_content)

        # Step 2: Get context-aware selectors
        selectors = self.selector_manager.get_all_popup_selectors(context)

        # Step 3: Detect if this is a guided tour (Football.com specific)
        # For Football.com match pages, assume guided tour if we detect any popup
        is_guided_tour = (context == 'fb_match_page' and
                         (analysis.get('is_multi_step', False) or analysis.get('has_popup', False) or analysis.get('has_overlay', False)))

        print(f"[AI Pop-up] Context: {context}, Has popup: {analysis.get('has_popup')}, Has overlay: {analysis.get('has_overlay')}, Multi-step: {analysis.get('is_multi_step')}, Guided tour: {is_guided_tour}")

        if is_guided_tour:
            print("[AI Pop-up] 🎯 Detected Football.com guided tour - executing multi-step sequence")
            tour_result = await self._execute_guided_tour_sequence(page, url)
            if tour_result['success']:
                result = tour_result.copy()
                result['method'] = 'guided_tour'
                print("[AI Pop-up] ✓ Guided tour completed successfully")
                return result
            else:
                print(f"[AI Pop-up] ⚠ Guided tour failed: {tour_result.get('errors', [])}")

        # Step 3b: Try standard dismissal first (for non-guided-tour popups)
        dismissal_result = await self.executor.execute_dismissal(page, selectors, context)

        if dismissal_result['success']:
            result = dismissal_result.copy()
            result['method'] = 'standard'
            self._update_knowledge(url, dismissal_result['selector_used'], context)
            print(f"[AI Pop-up] ✓ Closed popup via standard method: {dismissal_result['selector_used']}")
            return result

        # Step 3: If standard fails and we have screenshot, try AI analysis
        if screenshot_path and self.leo_analyzer:
            print("[AI Pop-up] Standard dismissal failed, trying AI analysis...")
            ai_analysis = await self.leo_analyzer.analyze_popup(page, await page.content(), screenshot_path, context)
            if ai_analysis.get('has_popup', False) and ai_analysis.get('selectors', []):
                ai_result = await self.leo_analyzer.execute_ai_dismissal(page, ai_analysis)
                if ai_result['success']:
                    result = ai_result.copy()
                    result['method'] = 'ai_analysis'
                    return result

        # Step 4: Try force dismissal for layered popups
        print("[AI Pop-up] Trying force dismissal...")
        html_content = await page.content()
        analysis = self.detector.analyze_html(html_content)

        if analysis['layer_count'] > 1 or 'pointer_events_blocking' in analysis.get('blocking_elements', []):
            force_result = await self.executor.execute_force_dismissal(page, analysis)
            if force_result['success']:
                result = force_result.copy()
                result['method'] = 'force_dismissal'
                print("[AI Pop-up] ✓ Force dismissal successful")
                return result

        # Step 5: Final fallback - try all known selectors
        print("[AI Pop-up] Attempting comprehensive dismissal...")
        all_selectors = self.selector_manager.get_popup_selectors(context)
        comprehensive_result = await self.executor.execute_dismissal(page, all_selectors, context)

        result = comprehensive_result.copy()
        result['method'] = 'comprehensive'

        if comprehensive_result['success']:
            print(f"[AI Pop-up] ✓ Comprehensive dismissal successful: {comprehensive_result['selector_used']}")
            self._update_knowledge(url, comprehensive_result['selector_used'], context)
        else:
            print(f"[AI Pop-up] All dismissal methods failed: {comprehensive_result.get('error', 'Unknown error')}")

        return result

    async def continuous_monitoring(self, page, url: str = "",
                                   interval: int = 10) -> None:
        """
        Continuously monitor for popups and dismiss them

        Args:
            page: Playwright page object
            url: Page URL for context detection
            interval: Monitoring interval in seconds
        """
        monitoring_active = True
        print(f"[AI Pop-up] Continuous monitoring every {interval}s...")

        try:
            while monitoring_active:
                try:
                    # Quick check for popups
                    html_content = await page.content()
                    analysis = self.detector.analyze_html(html_content)

                    if analysis['has_popup'] or analysis['has_overlay']:
                        print(f"[AI Pop-up] Detected: Overlay={analysis['has_overlay']}, Popup={analysis['has_popup']}, Multi={analysis['is_multi_step']}")

                        # Take screenshot for AI analysis if needed
                        screenshot_path = await self._take_screenshot(page, "monitoring")

                        result = await self.fb_universal_popup_dismissal(page, url, screenshot_path)

                        if result['success']:
                            print(f"[AI Pop-up] ✓ Closed popup via {result.get('method', 'unknown')}: {result.get('selector_used', 'N/A')}")
                        else:
                            print(f"[AI Pop-up] Attempt failed: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    print(f"[AI Pop-up] Monitoring error: {e}")

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            print("[AI Pop-up] Monitoring cancelled")

    def _update_knowledge(self, url: str, selector: str, context: str) -> None:
        """Update knowledge base with successful dismissal"""
        if selector:
            self.selector_manager.learn_successful_selector(url, selector, context)

    async def _execute_guided_tour_sequence(self, page, url: str) -> Dict[str, Any]:
        """
        Execute Football.com guided tour sequence:
        1. Click "Next" button
        2. Click "Got it" or "Got it!" button
        3. Wait a few seconds
        4. Click "OK"/"Ok"/"ok" button

        Returns:
            dict: Tour execution results
        """
        result = {
            'success': False,
            'method': 'guided_tour',
            'steps_completed': 0,
            'selectors_used': [],
            'errors': []
        }

        try:
            # Step 1: Click "Next" button
            print("[Guided Tour] Step 1: Looking for 'Next' button...")
            next_selectors = [
                'button:has-text("Next")',
                'span:has-text("Next")',
                'button:has-text("Continue")',
                'span:has-text("Continue")'
            ]

            next_clicked = False
            for selector in next_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0 and await element.is_visible():
                        await element.click(timeout=3000)
                        result['selectors_used'].append(selector)
                        result['steps_completed'] = 1
                        next_clicked = True
                        print(f"[Guided Tour] ✓ Step 1 completed: clicked {selector}")
                        break
                except Exception as e:
                    continue

            if not next_clicked:
                result['errors'].append("Could not find 'Next' button")
                return result

            # Wait for transition
            await page.wait_for_timeout(1500)

            # Step 2: Click "Got it" button
            print("[Guided Tour] Step 2: Looking for 'Got it' button...")
            got_it_selectors = [
                'button:has-text("Got it")',
                'button:has-text("Got it!")',
                'span:has-text("Got it")',
                'span:has-text("Got it!")'
            ]

            got_it_clicked = False
            for selector in got_it_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0 and await element.is_visible():
                        await element.click(timeout=3000)
                        result['selectors_used'].append(selector)
                        result['steps_completed'] = 2
                        got_it_clicked = True
                        print(f"[Guided Tour] ✓ Step 2 completed: clicked {selector}")
                        break
                except Exception as e:
                    continue

            if not got_it_clicked:
                result['errors'].append("Could not find 'Got it' button")
                return result

            # Step 3: Wait for the final popup to appear (user mentioned "few seconds later")
            print("[Guided Tour] Step 3: Waiting for final OK popup...")
            await page.wait_for_timeout(5000)  # Wait 5 seconds for the OK popup to appear

            # Step 4: Click OK button
            print("[Guided Tour] Step 4: Looking for OK button...")
            ok_selectors = [
                'button:has-text("OK")',
                'button:has-text("Ok")',
                'button:has-text("ok")',
                'span:has-text("OK")',
                'span:has-text("Ok")',
                'span:has-text("ok")'
            ]

            ok_clicked = False
            for selector in ok_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0 and await element.is_visible():
                        await element.click(timeout=3000)
                        result['selectors_used'].append(selector)
                        result['steps_completed'] = 4
                        ok_clicked = True
                        print(f"[Guided Tour] ✓ Step 4 completed: clicked {selector}")
                        break
                except Exception as e:
                    continue

            if not ok_clicked:
                result['errors'].append("Could not find OK button")
                return result

            # Verify tour completion by checking if popups are gone
            await page.wait_for_timeout(1000)
            verification = await self.executor.verify_dismissal(page)

            if verification['dismissed']:
                result['success'] = True
                print("[Guided Tour] ✓ Tour completed and verified - all popups dismissed")
            else:
                result['errors'].append("Tour steps completed but popups still present")
                print("[Guided Tour] ⚠ Tour steps completed but verification failed")

        except Exception as e:
            result['errors'].append(f"Tour execution failed: {str(e)}")
            print(f"[Guided Tour] Error: {e}")

        return result

    async def _take_screenshot(self, page, prefix: str = "popup") -> str:
        """Take screenshot for analysis"""
        import time
        timestamp = int(time.time())
        screenshot_path = f"Logs/popup_{prefix}_{timestamp}.png"

        try:
            await page.screenshot(path=screenshot_path, full_page=True)
            return screenshot_path
        except Exception as e:
            print(f"[AI Pop-up] Screenshot failed: {e}")
            return ""

    # ===== LEGACY COMPATIBILITY METHODS =====

    @staticmethod
    def get_popup_patterns() -> dict:
        """Legacy method - use PopupDetector instead"""
        detector = PopupDetector()
        return {
            "overlay_classes": [
                "dialog-mask", "modal-backdrop", "overlay", "backdrop", "popup-overlay"
            ],
            "popup_wrappers": [
                "m-popOver-wrapper", "popup-hint", "modal-dialog", "tooltip", "popover"
            ],
            "close_selectors": [
                "button.close", '[data-dismiss="modal"]', 'button:has-text("Close")'
            ],
            "multi_step_indicators": [
                "Next", "Got it", "Step", "Continue"
            ],
        }
