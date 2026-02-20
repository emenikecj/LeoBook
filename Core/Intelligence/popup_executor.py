# popup_executor.py: popup_executor.py: Low-level execution of popup dismissal actions.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: PopupExecutor

"""
Popup Executor Module
Handles the execution of popup dismissal operations with robust error handling.
Responsible for clicking selectors, force dismissal, and timeout management.
"""

import asyncio
from typing import Dict, Any, List, Optional


class PopupExecutor:
    """Executes popup dismissal operations with comprehensive error handling"""

    def __init__(self):
        self.default_timeout = 5000  # 5 seconds
        self.force_timeout = 10000   # 10 seconds for force operations

    async def execute_dismissal(self, page, selectors: List[str],
                              context: str = "generic",
                              timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute popup dismissal using provided selectors

        Args:
            page: Playwright page object
            selectors: List of CSS selectors to try in order
            context: Page context for logging
            timeout: Timeout per selector attempt

        Returns:
            dict: Execution results
        """
        result = {
            'success': False,
            'selector_used': None,
            'method': 'standard',
            'selectors_tried': [],
            'errors': [],
            'context': context
        }

        if not selectors:
            result['error'] = 'No selectors provided'
            return result

        timeout = timeout or self.default_timeout

        for selector in selectors:
            try:
                result['selectors_tried'].append(selector)

                # Wait for element to be present
                await page.wait_for_selector(selector, state='attached', timeout=timeout)

                # Get element and check visibility
                element = page.locator(selector).first

                if await element.count() == 0:
                    result['errors'].append(f"Selector not found: {selector}")
                    continue

                # Check if element is visible and enabled
                is_visible = await element.is_visible()
                is_enabled = await element.is_enabled()

                if not is_visible:
                    result['errors'].append(f"Selector not visible: {selector}")
                    continue

                if not is_enabled:
                    result['errors'].append(f"Selector not enabled: {selector}")
                    continue

                # Attempt click
                await element.click(timeout=timeout)

                print(f"[Popup Executor] ✓ Successfully clicked: {selector}")

                # Verify dismissal by waiting a bit and checking if element still exists
                await page.wait_for_timeout(500)

                # Check if element is still present (popup might still be there)
                still_present = await element.count() > 0 and await element.is_visible()

                if not still_present:
                    result['success'] = True
                    result['selector_used'] = selector
                    break
                else:
                    result['errors'].append(f"Element still present after click: {selector}")
                    # Continue to next selector since this one didn't work

            except Exception as e:
                error_msg = f"Failed to execute {selector}: {str(e)}"
                result['errors'].append(error_msg)
                print(f"[Popup Executor] Error: {error_msg}")
                continue

        if not result['success'] and result['selectors_tried']:
            result['error'] = f"All {len(result['selectors_tried'])} selectors failed"

        return result

    async def execute_force_dismissal(self, page, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute force dismissal for complex layered popups

        Args:
            page: Playwright page object
            analysis: Popup analysis from PopupDetector

        Returns:
            dict: Force dismissal results
        """
        result = {
            'success': False,
            'method': 'force_dismissal',
            'actions_taken': [],
            'errors': []
        }

        try:
            # Check for pointer-events blocking (Football.com issue)
            if 'pointer_events_blocking' in analysis.get('blocking_elements', []):
                print("[Force Dismissal] Detected pointer-events blocking, using JavaScript injection")

                # Inject JavaScript to force click through pointer-events: none
                js_force_click = """
                (function() {
                    // Find all elements with pointer-events: none that might be blocking
                    const blockers = document.querySelectorAll('[style*="pointer-events: none"], .dialog-mask, .modal-backdrop');

                    for (let blocker of blockers) {
                        // Temporarily remove pointer-events blocking
                        blocker.style.pointerEvents = 'auto';

                        // Try to find close buttons underneath
                        const closeButtons = blocker.querySelectorAll('button:has-text("Close"), button:has-text("OK"), button:has-text("Got it"), [aria-label="Close"]');

                        for (let btn of closeButtons) {
                            if (btn.offsetParent !== null) { // Visible
                                btn.click();
                                return {success: true, selector: 'force_js_close', element: btn.outerHTML};
                            }
                        }
                    }

                    // Try overlay click
                    const overlays = document.querySelectorAll('.overlay, .backdrop, .mask');
                    for (let overlay of overlays) {
                        if (overlay.offsetParent !== null) {
                            overlay.click();
                            return {success: true, selector: 'force_overlay_click', element: overlay.outerHTML};
                        }
                    }

                    return {success: false, error: 'No force dismissal targets found'};
                })();
                """

                force_result = await page.evaluate(js_force_click)

                if force_result and force_result.get('success'):
                    result['success'] = True
                    result['actions_taken'].append('javascript_force_click')
                    result['selector_used'] = force_result.get('selector', 'force_js')
                    print(f"[Force Dismissal] ✓ JavaScript force click successful: {force_result.get('selector')}")
                else:
                    result['errors'].append('JavaScript force dismissal failed')

            # Try layered modal dismissal
            if analysis.get('layer_count', 0) > 1:
                print(f"[Force Dismissal] Detected {analysis['layer_count']} layers, trying layered approach")

                # Get all potential modal elements
                modal_selectors = [
                    '.modal',
                    '.popup',
                    '.dialog',
                    '.overlay',
                    '[role="dialog"]',
                    '.m-popOver-wrapper'
                ]

                for modal_sel in modal_selectors:
                    try:
                        modals = page.locator(modal_sel)
                        count = await modals.count()

                        if count > 0:
                            # Try to dismiss each modal
                            for i in range(count):
                                modal = modals.nth(i)

                                if await modal.is_visible():
                                    # Try ESC key first
                                    await page.keyboard.press('Escape')
                                    await page.wait_for_timeout(500)

                                    if not await modal.is_visible():
                                        result['success'] = True
                                        result['actions_taken'].append('escape_key')
                                        result['selector_used'] = f'{modal_sel}[{i}]'
                                        print(f"[Force Dismissal] ✓ ESC key dismissed modal: {modal_sel}[{i}]")
                                        break

                                    # Try clicking outside modal
                                    await modal.click(position={'x': -10, 'y': -10})
                                    await page.wait_for_timeout(500)

                                    if not await modal.is_visible():
                                        result['success'] = True
                                        result['actions_taken'].append('outside_click')
                                        result['selector_used'] = f'{modal_sel}[{i}]_outside'
                                        print(f"[Force Dismissal] ✓ Outside click dismissed modal: {modal_sel}[{i}]")
                                        break

                            if result['success']:
                                break

                    except Exception as e:
                        result['errors'].append(f"Modal dismissal failed for {modal_sel}: {str(e)}")
                        continue

            # Final fallback: Try to click document body to dismiss overlays
            if not result['success']:
                print("[Force Dismissal] Trying document body click as final fallback")

                try:
                    await page.click('body', position={'x': 10, 'y': 10})
                    await page.wait_for_timeout(1000)

                    # Check if any overlays are gone
                    overlays_gone = await page.evaluate("""
                        !document.querySelector('.overlay, .backdrop, .mask, .modal-backdrop')
                    """)

                    if overlays_gone:
                        result['success'] = True
                        result['actions_taken'].append('body_click')
                        result['selector_used'] = 'body_fallback'
                        print("[Force Dismissal] ✓ Body click dismissed overlays")
                    else:
                        result['errors'].append('Body click did not dismiss overlays')

                except Exception as e:
                    result['errors'].append(f"Body click failed: {str(e)}")

        except Exception as e:
            result['errors'].append(f"Force dismissal execution error: {str(e)}")

        if not result['success']:
            result['error'] = f"Force dismissal failed after trying {len(result['actions_taken'])} methods"

        return result

    async def execute_multi_step_dismissal(self, page, selectors: List[str],
                                         steps: int = 0) -> Dict[str, Any]:
        """
        Execute multi-step popup dismissal (tutorials, guided tours)

        Args:
            page: Playwright page object
            selectors: List of selectors to click in sequence
            steps: Number of steps (0 = use all selectors)

        Returns:
            dict: Multi-step execution results
        """
        result = {
            'success': False,
            'method': 'multi_step',
            'steps_completed': 0,
            'selectors_used': [],
            'errors': []
        }

        if not selectors:
            result['error'] = 'No selectors provided for multi-step dismissal'
            return result

        steps = steps or len(selectors)
        selectors_to_use = selectors[:steps]

        try:
            for i, selector in enumerate(selectors_to_use):
                try:
                    # Wait for selector with increasing timeout
                    timeout = min(self.default_timeout + (i * 1000), 15000)  # Up to 15s
                    await page.wait_for_selector(selector, timeout=timeout)

                    element = page.locator(selector).first

                    if await element.count() > 0 and await element.is_visible():
                        await element.click(timeout=3000)
                        result['selectors_used'].append(selector)
                        result['steps_completed'] = i + 1

                        print(f"[Multi-Step] ✓ Step {i+1}/{steps}: {selector}")

                        # Wait between steps
                        if i < steps - 1:
                            await page.wait_for_timeout(1500)
                    else:
                        result['errors'].append(f"Step {i+1} selector not visible: {selector}")
                        break

                except Exception as e:
                    result['errors'].append(f"Step {i+1} failed ({selector}): {str(e)}")
                    break

            # Success if we completed all intended steps
            result['success'] = result['steps_completed'] == steps

        except Exception as e:
            result['errors'].append(f"Multi-step execution error: {str(e)}")

        if not result['success'] and result['steps_completed'] > 0:
            result['partial_success'] = True
            print(f"[Multi-Step] Partial success: {result['steps_completed']}/{steps} steps completed")

        return result

    async def verify_dismissal(self, page, original_html: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify that popup dismissal was successful

        Args:
            page: Playwright page object
            original_html: HTML before dismissal attempt

        Returns:
            dict: Verification results
        """
        result = {
            'dismissed': False,
            'confidence': 0.0,
            'checks': []
        }

        try:
            # Wait for potential animations/transitions
            await page.wait_for_timeout(1000)

            # Check 1: Are common popup selectors still present?
            popup_selectors = [
                '.modal',
                '.popup',
                '.overlay',
                '.dialog',
                '[role="dialog"]'
            ]

            popups_present = 0
            for selector in popup_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        popups_present += count
                except:
                    pass

            result['checks'].append({
                'type': 'popup_selectors',
                'present': popups_present,
                'passed': popups_present == 0
            })

            # Check 2: Is page interactive? (Can we click body?)
            try:
                await page.click('body', timeout=1000)
                body_clickable = True
            except:
                body_clickable = False

            result['checks'].append({
                'type': 'body_interactive',
                'clickable': body_clickable,
                'passed': body_clickable
            })

            # Check 3: Has HTML changed significantly?
            if original_html:
                current_html = await page.content()
                html_similarity = len(set(current_html.split()) & set(original_html.split())) / len(set(current_html.split()) | set(original_html.split()))

                result['checks'].append({
                    'type': 'html_similarity',
                    'similarity': html_similarity,
                    'passed': html_similarity < 0.95  # Significant change indicates dismissal
                })

            # Calculate overall confidence
            passed_checks = sum(1 for check in result['checks'] if check['passed'])
            result['confidence'] = passed_checks / len(result['checks'])

            # Determine if dismissed
            result['dismissed'] = result['confidence'] > 0.6  # Majority of checks pass

        except Exception as e:
            result['error'] = f"Verification error: {str(e)}"
            result['dismissed'] = False

        return result
