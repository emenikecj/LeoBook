# popup_handler.py: popup_handler.py: Orchestration layer for the popup dismissal system.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: PopupDetector, PopupExecutor, LeoPopupAnalyzer, PopupHandler

"""
Popup Handler Module - CONSOLIDATED VERSION
Orchestrates modular popup dismissal components with layered fallback strategy.
Implements Phase 2 Football.com integration with intelligent popup resolution.

This file contains the consolidated AI popup analysis, heuristic detection,
execution logic, and high-level orchestration previously split across 4 files.
"""

import asyncio
import re
import json
import base64
from typing import Dict, Any, List, Optional

from .selector_manager import SelectorManager
from .api_manager import grok_api_call
from .utils import clean_json_response

# ==============================================================================
# 1. POPUP DETECTOR (Heuristics)
# ==============================================================================

class PopupDetector:
    """Detects and analyzes popup structures in HTML content"""

    def __init__(self):
        self.overlay_patterns = [
            r'class="[^"]*dialog-mask[^"]*"',
            r'class="[^"]*modal-backdrop[^"]*"',
            r'class="[^"]*overlay[^"]*"',
            r'class="[^"]*backdrop[^"]*"',
            r'class="[^"]*popup-overlay[^"]*"',
            r'class="[^"]*un-op-70%[^"]*"',
            r'class="[^"]*un-h-100vh[^"]*"',
            r'style="[^"]*pointer-events:\s*none[^"]*"',
            r'class="[^"]*dialog-wrapper[^"]*"',
        ]

        self.popup_patterns = [
            r'class="[^"]*m-popOver-wrapper[^"]*"',
            r'class="[^"]*popup-hint[^"]*"',
            r'class="[^"]*modal-dialog[^"]*"',
            r'class="[^"]*tooltip[^"]*"',
            r'class="[^"]*popover[^"]*"',
            r'class="[^"]*dialog-container[^"]*"',
            r'id="[^"]*modal[^"]*"',
            r'id="[^"]*popup[^"]*"',
        ]

        self.multi_step_patterns = [
            r'tour[^"]*', r'guide[^"]*', r'intro[^"]*', r'step[^"]*',
            r'Next[^"]*', r'Got it[^"]*', r'Continue[^"]*',
            r'm-popOver-wrapper', r'dialog-wrapper',
            r'pointer-events:\s*none', r'overlay[^"]*',
            r'modal-backdrop', r'backdrop',
        ]

        self.layer_patterns = [
            r'z-index:\s*\d+',
            r'position:\s*(absolute|fixed|relative)',
        ]

    def analyze_html(self, html_content: str) -> Dict[str, Any]:
        """Analyze HTML content for popup structures"""
        analysis = {
            'has_popup': False, 'has_overlay': False, 'is_multi_step': False,
            'layer_count': 0, 'blocking_elements': [], 'popup_types': [],
            'confidence': 0.0, 'recommendations': []
        }

        # Check for overlays
        overlay_matches = sum(len(re.findall(p, html_content, re.IGNORECASE)) for p in self.overlay_patterns)
        if overlay_matches > 0:
            analysis['has_overlay'] = True
            analysis['popup_types'].append('overlay')
            analysis['confidence'] += 0.4

        # Check for popups
        popup_matches = sum(len(re.findall(p, html_content, re.IGNORECASE)) for p in self.popup_patterns)
        if popup_matches > 0:
            analysis['has_popup'] = True
            analysis['popup_types'].append('modal')
            analysis['confidence'] += 0.3

        # Check multi-step
        ms_matches = sum(len(re.findall(p, html_content, re.IGNORECASE)) for p in self.multi_step_patterns)
        if ms_matches > 0:
            analysis['is_multi_step'] = True
            analysis['popup_types'].append('guided_tour')
            analysis['confidence'] += 0.2

        # Layer analysis
        layers = []
        for p in self.layer_patterns: layers.extend(re.findall(p, html_content, re.IGNORECASE))
        analysis['layer_count'] = len(set(layers))

        if 'pointer-events: none' in html_content.lower():
            analysis['blocking_elements'].append('pointer_events_blocking')
            analysis['confidence'] += 0.3
            analysis['recommendations'].append('force_dismissal')

        if analysis['confidence'] > 0.8: analysis['recommendations'].append('immediate_dismissal')
        elif analysis['confidence'] > 0.5: analysis['recommendations'].append('standard_dismissal')
        elif analysis['confidence'] > 0.2: analysis['recommendations'].append('ai_analysis')

        return analysis

    def detect_context(self, url: str) -> str:
        """Detect page context from URL"""
        url_lower = url.lower()
        if 'football.com' in url_lower and ('match' in url_lower or 'game' in url_lower):
            return 'fb_match_page'
        elif 'football.com' in url_lower:
            return 'fb_general'
        return 'generic'


# ==============================================================================
# 2. POPUP EXECUTOR (Interactions)
# ==============================================================================

class PopupExecutor:
    """Executes popup dismissal operations with comprehensive error handling"""

    def __init__(self):
        self.default_timeout = 5000
        self.force_timeout = 10000

    async def execute_dismissal(self, page, selectors: List[str], context: str = "generic", timeout: Optional[int] = None) -> Dict[str, Any]:
        result = {'success': False, 'selector_used': None, 'method': 'standard', 'selectors_tried': [], 'errors': [], 'context': context}
        if not selectors:
            result['error'] = 'No selectors provided'
            return result
        timeout = timeout or self.default_timeout

        for selector in selectors:
            try:
                result['selectors_tried'].append(selector)
                await page.wait_for_selector(selector, state='attached', timeout=timeout)
                element = page.locator(selector).first
                if await element.count() == 0 or not await element.is_visible() or not await element.is_enabled():
                    continue

                await element.click(timeout=timeout)
                print(f"[Popup Executor] ✓ Successfully clicked: {selector}")
                await page.wait_for_timeout(500)

                if not (await element.count() > 0 and await element.is_visible()):
                    result['success'] = True
                    result['selector_used'] = selector
                    break
            except Exception as e:
                print(f"[Popup Executor] Error executing {selector}: {e}")
                result['errors'].append(f"Failed {selector}: {e}")

        if not result['success'] and result['selectors_tried']:
            result['error'] = f"All {len(result['selectors_tried'])} selectors failed"
        return result

    async def execute_force_dismissal(self, page, analysis: Dict[str, Any]) -> Dict[str, Any]:
        result = {'success': False, 'method': 'force_dismissal', 'actions_taken': [], 'errors': []}
        try:
            if 'pointer_events_blocking' in analysis.get('blocking_elements', []):
                print("[Force Dismissal] Using JavaScript injection")
                js_force_click = """
                (function() {
                    const blockers = document.querySelectorAll('[style*="pointer-events: none"], .dialog-mask, .modal-backdrop');
                    for (let blocker of blockers) {
                        blocker.style.pointerEvents = 'auto';
                        const btns = blocker.querySelectorAll('button:has-text("Close"), button:has-text("OK"), button:has-text("Got it"), [aria-label="Close"]');
                        for (let btn of btns) { if (btn.offsetParent) { btn.click(); return {success: true, selector: 'force_js_close'}; } }
                    }
                    const overlays = document.querySelectorAll('.overlay, .backdrop, .mask');
                    for (let overlay of overlays) { if (overlay.offsetParent) { overlay.click(); return {success: true, selector: 'force_overlay_click'}; } }
                    return {success: false, error: 'No targets'};
                })();
                """
                force_result = await page.evaluate(js_force_click)
                if force_result and force_result.get('success'):
                    result['success'] = True
                    result['actions_taken'].append('javascript_force_click')
                    result['selector_used'] = force_result.get('selector', 'force_js')
                    return result

            if analysis.get('layer_count', 0) > 1:
                modal_sels = ['.modal', '.popup', '.dialog', '.overlay', '[role="dialog"]', '.m-popOver-wrapper']
                for sel in modal_sels:
                    try:
                        modals = page.locator(sel)
                        if await modals.count() > 0:
                            for i in range(await modals.count()):
                                m = modals.nth(i)
                                if await m.is_visible():
                                    await page.keyboard.press('Escape')
                                    await page.wait_for_timeout(500)
                                    if not await m.is_visible():
                                        result['success'] = True; result['selector_used'] = f'{sel}[{i}]_esc'; return result
                                    await m.click(position={'x': -10, 'y': -10})
                                    await page.wait_for_timeout(500)
                                    if not await m.is_visible():
                                        result['success'] = True; result['selector_used'] = f'{sel}[{i}]_out'; return result
                    except: pass

            if not result['success']:
                print("[Force Dismissal] Trying body click fallback")
                await page.click('body', position={'x': 10, 'y': 10})
                await page.wait_for_timeout(1000)
                if await page.evaluate("!document.querySelector('.overlay, .backdrop, .mask, .modal-backdrop')"):
                    result['success'] = True; result['selector_used'] = 'body_fallback'
        except Exception as e:
            result['errors'].append(f"Force execution error: {str(e)}")
        return result

    async def verify_dismissal(self, page, original_html: Optional[str] = None) -> Dict[str, Any]:
        """Verify popup dismissal was successful"""
        result = {'dismissed': False, 'confidence': 0.0, 'checks': []}
        try:
            await page.wait_for_timeout(1000)
            popups = sum(await page.locator(s).count() for s in ['.modal', '.popup', '.overlay', '.dialog', '[role="dialog"]'])
            result['checks'].append({'type': 'popup_selectors', 'passed': popups == 0})
            
            try: await page.click('body', timeout=1000); clickable = True
            except: clickable = False
            result['checks'].append({'type': 'body_interactive', 'passed': clickable})

            if original_html:
                current = await page.content()
                sim = len(set(current.split()) & set(original_html.split())) / len(set(current.split()) | set(original_html.split()))
                result['checks'].append({'type': 'html_similarity', 'passed': sim < 0.95})

            pct = sum(1 for c in result['checks'] if c['passed']) / len(result['checks'])
            result['confidence'] = pct
            result['dismissed'] = pct > 0.6
        except:
            pass
        return result


# ==============================================================================
# 3. LEO POPUP ANALYZER (AI Vision)
# ==============================================================================

class LeoPopupAnalyzer:
    """AI-powered popup analysis using local Leo AI model (via Grok)"""

    async def analyze_popup(self, page, html_content: str, screenshot_path: Optional[str] = None, context: str = "generic") -> Dict[str, Any]:
        try:
            if not screenshot_path:
                img_data = base64.b64encode(await page.screenshot(full_page=True, type="png")).decode("utf-8")
            else:
                with open(screenshot_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")

            prompt = self._create_prompt(html_content, context)
            response = await grok_api_call([prompt, {"inline_data": {"mime_type": "image/png", "data": img_data}}], generation_config={"temperature": 0.1, "response_mime_type": "application/json"})
            
            if response and hasattr(response, 'text') and response.text:
                analysis = json.loads(clean_json_response(response.text))
                return self._validate(analysis, context)
            return self._fallback()
        except Exception as e:
            print(f"[Leo AI Analysis] Error: {e}")
            return self._fallback()

    def _create_prompt(self, html: str, ctx: str) -> str:
        return f"""
        Analyze this webpage screenshot + HTML for popup/modal dismissal. Context: {ctx}
        Return JSON: {{"has_popup": true/false, "selectors": ["css_sel1"], "steps": 1, "type": "modal"}}
        Prioritize visible close buttons. HTML: {html[:3000]}...
        """

    def _validate(self, a: Dict[str, Any], ctx: str) -> Dict[str, Any]:
        a.setdefault('has_popup', bool(a.get('selectors')))
        a.setdefault('selectors', [])
        if ctx == 'fb_match_page' and a['has_popup']:
            for s in reversed(['button:has-text("Next")', 'button:has-text("Got it")', 'button:has-text("OK")']):
                if s not in a['selectors']: a['selectors'].insert(0, s)
        a['selectors'] = [s for s in a['selectors'] if isinstance(s, str) and any(c in s for c in ['#', '.', '[', ':', 'button', 'div', 'span'])][:5]
        return a

    def _fallback(self) -> Dict[str, Any]:
        return {'has_popup': False, 'selectors': [], 'steps': 0, 'type': 'none'}

    async def execute_ai_dismissal(self, page, analysis: Dict[str, Any]) -> Dict[str, Any]:
        result = {'success': False, 'method': 'ai_analysis', 'selectors_tried': [], 'errors': []}
        if not analysis.get('selectors'): return result
        
        for i, sel in enumerate(analysis['selectors'][:analysis.get('steps', 1)]):
            try:
                await page.wait_for_selector(sel, timeout=5000)
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click(timeout=3000)
                    result['selectors_tried'].append(sel)
                    await page.wait_for_timeout(1000)
            except Exception as e:
                result['errors'].append(str(e))
        result['success'] = len(result['selectors_tried']) > 0
        return result


# ==============================================================================
# 4. MAIN ORCHESTRATOR
# ==============================================================================

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
        self.leo_analyzer = LeoPopupAnalyzer()
        self.executor = PopupExecutor()

    async def fb_universal_popup_dismissal(
        self, page, url: str = "", screenshot_path: Optional[str] = None, monitor_interval: int = 0
    ) -> Dict[str, Any]:
        result = {'success': False, 'method': 'none', 'selector_used': None, 'error': None, 'url': url, 'context': self.detector.detect_context(url)}
        try:
            if monitor_interval > 0:
                await self.continuous_monitoring(page, url, monitor_interval)
                result['method'] = 'continuous_monitoring'; result['success'] = True
                return result

            dismissal_result = await self._execute_layered_dismissal(page, url, screenshot_path)
            result.update(dismissal_result)
            return result
        except Exception as e:
            result['error'] = f"Popup dismissal failed: {e}"
            return result

    async def _execute_layered_dismissal(self, page, url: str, screenshot_path: Optional[str] = None) -> Dict[str, Any]:
        ctx = self.detector.detect_context(url)
        html = await page.content()
        analysis = self.detector.analyze_html(html)
        selectors = self.selector_manager.get_all_popup_selectors(ctx)
        
        is_tour = (ctx == 'fb_match_page' and (analysis.get('is_multi_step') or analysis.get('has_popup') or analysis.get('has_overlay')))
        
        # 1. Guided Tour Fallback
        if is_tour:
            tour = await self._execute_guided_tour_sequence(page, url)
            if tour['success']:
                tour['method'] = 'guided_tour'
                return tour

        # 2. Standard
        res = await self.executor.execute_dismissal(page, selectors, ctx)
        if res['success']:
            res['method'] = 'standard'
            self._update_knowledge(url, res['selector_used'], ctx)
            return res

        # 3. AI
        if screenshot_path:
            ai_ana = await self.leo_analyzer.analyze_popup(page, await page.content(), screenshot_path, ctx)
            if ai_ana.get('has_popup'):
                ai_res = await self.leo_analyzer.execute_ai_dismissal(page, ai_ana)
                if ai_res['success']:
                    ai_res['method'] = 'ai_analysis'
                    return ai_res

        # 4. Force
        html = await page.content()
        ana = self.detector.analyze_html(html)
        if ana['layer_count'] > 1 or 'pointer_events_blocking' in ana.get('blocking_elements', []):
            force = await self.executor.execute_force_dismissal(page, ana)
            if force['success']: return force

        # 5. Comprehensive fallback
        all_sels = self.selector_manager.get_popup_selectors(ctx)
        comp = await self.executor.execute_dismissal(page, all_sels, ctx)
        comp['method'] = 'comprehensive'
        if comp['success']:
            self._update_knowledge(url, comp['selector_used'], ctx)
        return comp

    async def _execute_guided_tour_sequence(self, page, url: str) -> Dict[str, Any]:
        result = {'success': False, 'method': 'guided_tour', 'steps_completed': 0, 'selectors_used': [], 'errors': []}
        steps = [
            ['button:has-text("Next")', 'span:has-text("Next")', 'button:has-text("Continue")'],
            ['button:has-text("Got it")', 'button:has-text("Got it!")', 'span:has-text("Got it")'],
            ['button:has-text("OK")', 'button:has-text("Ok")', 'span:has-text("OK")']
        ]
        
        for step_idx, sels in enumerate(steps):
            if step_idx == 2: await page.wait_for_timeout(3000) # Wait for OK popup
            clicked = False
            for s in sels:
                try:
                    el = page.locator(s).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click(timeout=3000)
                        result['selectors_used'].append(s); result['steps_completed'] += 1; clicked = True
                        break
                except: pass
            if not clicked and step_idx == 0:
                result['errors'].append("Failed Step 1")
                return result
            await page.wait_for_timeout(1000)

        verify = await self.executor.verify_dismissal(page)
        result['success'] = verify['dismissed']
        return result

    async def continuous_monitoring(self, page, url: str = "", interval: int = 10) -> None:
        try:
            while True:
                ana = self.detector.analyze_html(await page.content())
                if ana['has_popup'] or ana['has_overlay']:
                    try: path = f"popup_{interval}.png"; await page.screenshot(path=path)
                    except: path = None
                    await self.fb_universal_popup_dismissal(page, url, path)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    def _update_knowledge(self, url: str, selector: str, context: str) -> None:
        if selector: self.selector_manager.learn_successful_selector(url, selector, context)

    @staticmethod
    def get_popup_patterns() -> dict:
        """Legacy method"""
        return {
            "overlay_classes": ["dialog-mask", "modal-backdrop", "overlay", "backdrop", "popup-overlay"],
            "popup_wrappers": ["m-popOver-wrapper", "popup-hint", "modal-dialog", "tooltip", "popover"],
            "close_selectors": ["button.close", '[data-dismiss="modal"]', 'button:has-text("Close")'],
            "multi_step_indicators": ["Next", "Got it", "Step", "Continue"],
        }


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
