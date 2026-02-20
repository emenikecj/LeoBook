# leo_popup_analyzer.py: leo_popup_analyzer.py: Local AI-driven overlay detection and dismissal.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: LeoPopupAnalyzer
# Functions: clean_json_response()

"""
Leo AI Popup Analyzer Module
Uses local AI to analyze popup screenshots and HTML for dismissal strategies.
"""

import base64
import json
from typing import Dict, Any, Optional

from .api_manager import grok_api_call
from .selector_db import knowledge_db


def clean_json_response(response_text: str) -> str:
    """Clean and extract JSON from Leo AI response"""
    import re
    import json

    # Remove markdown code blocks if present
    text = re.sub(r'```json\s*', '', response_text)
    text = re.sub(r'```\s*$', '', text)

    # Find JSON object
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            # Validate it's proper JSON
            json.loads(json_match.group())
            return json_match.group()
        except json.JSONDecodeError:
            pass

    # If no valid JSON found, return original cleaned text
    return text.strip()


class LeoPopupAnalyzer:
    """AI-powered popup analysis using local Leo AI model"""

    def __init__(self):
        self.analysis_timeout = 30000  # 30 seconds
        self.max_retries = 2

    async def analyze_popup(self, page, html_content: str,
                          screenshot_path: Optional[str] = None,
                          context: str = "generic") -> Dict[str, Any]:
        """
        Analyze popup using AI vision analysis

        Args:
            page: Playwright page object
            html_content: Page HTML content
            screenshot_path: Path to screenshot (optional)
            context: Page context for better analysis

        Returns:
            dict: Analysis results with dismissal strategies
        """
        try:
            # Capture screenshot if not provided
            if not screenshot_path:
                screenshot_bytes = await page.screenshot(full_page=True, type="png")
                img_data = base64.b64encode(screenshot_bytes).decode("utf-8")
            else:
                # Read existing screenshot
                with open(screenshot_path, "rb") as f:
                    screenshot_bytes = f.read()
                img_data = base64.b64encode(screenshot_bytes).decode("utf-8")

            # Create context-aware prompt
            prompt = self._create_analysis_prompt(html_content, context)

            # Call API (redirected to Leo AI)
            response = await grok_api_call(
                [prompt, {"inline_data": {"mime_type": "image/png", "data": img_data}}],
                generation_config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json"
                }
            )

            if response and hasattr(response, 'text') and response.text:
                cleaned_text = clean_json_response(response.text)
                analysis = json.loads(cleaned_text)

                # Validate and enhance analysis
                analysis = self._validate_and_enhance_analysis(analysis, context)

                print(f"[Leo AI Analysis] Found {len(analysis.get('selectors', []))} potential dismiss selectors")
                return analysis
            else:
                print("[Leo AI Analysis] No response from API")
                return self._get_fallback_analysis()

        except Exception as e:
            print(f"[Leo AI Analysis] Error: {e}")
            return self._get_fallback_analysis()

    def _create_analysis_prompt(self, html_content: str, context: str) -> str:
        """Create context-aware analysis prompt"""

        # Context-specific instructions
        if context == 'fb_match_page':
            context_instructions = """
            This is a Football.com match page. Look for:
            - Guided tour popups with "Next", "Got it", "OK" buttons
            - Cookie consent banners
            - Login prompts
            - Subscription overlays
            - Multi-step tutorial popups
            """
        elif context == 'fb_general':
            context_instructions = """
            This is a Football.com general page. Look for:
            - Cookie banners
            - Age verification popups
            - Newsletter signup forms
            - Ad overlays
            - Generic modal dialogs
            """
        else:
            context_instructions = """
            This is a general webpage. Look for:
            - Standard modal dialogs
            - Alert boxes
            - Cookie consent popups
            - Ad overlays
            - Generic popup elements
            """

        prompt = f"""
        Analyze this webpage screenshot + HTML for popup/modal dismissal.
        {context_instructions}

        IDENTIFY close/dismiss elements and return JSON:

        {{
        "has_popup": true/false,
        "selectors": ["primary_selector", "backup_selector"],
        "multi_click": true/false (for multi-step popups),
        "steps": number_of_clicks_needed,
        "type": "modal|tooltip|guide|tour|consent|ad|none",
        "confidence": 0.0-1.0,
        "reason": "brief explanation",
        "elements": [
            {{
            "selector": "css_selector",
            "type": "button|close_icon|overlay_click",
            "text": "button text if any",
            "position": "x,y coordinates"
            }}
        ]
        }}

        Rules:
        - Prioritize visible, accessible close buttons
        - For multi-step popups, list selectors in click order
        - Include overlay click areas as last resort
        - Set confidence based on clarity of close elements
        - Return {{"has_popup": false}} if no popup detected

        HTML: {html_content[:3000]}...
        """

        return prompt

    def _validate_and_enhance_analysis(self, analysis: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Validate and enhance Leo AI analysis results"""

        # Ensure required fields
        if 'has_popup' not in analysis:
            analysis['has_popup'] = bool(analysis.get('selectors', []))

        if 'selectors' not in analysis:
            analysis['selectors'] = []

        if 'confidence' not in analysis:
            analysis['confidence'] = 0.5 if analysis['selectors'] else 0.0

        if 'multi_click' not in analysis:
            analysis['multi_click'] = len(analysis.get('selectors', [])) > 1

        if 'steps' not in analysis:
            analysis['steps'] = len(analysis.get('selectors', []))

        if 'type' not in analysis:
            analysis['type'] = 'unknown'

        if 'reason' not in analysis:
            analysis['reason'] = 'AI analysis'

        # Context-specific enhancements
        if context == 'fb_match_page' and analysis['has_popup']:
            # For Football.com match pages, prioritize specific selectors
            priority_selectors = [
                'button:has-text("Next")',
                'button:has-text("Got it")',
                'button:has-text("OK")',
                'span:has-text("Next")',
            ]
            # Prepend priority selectors if not already present
            existing = set(analysis['selectors'])
            for selector in priority_selectors:
                if selector not in existing:
                    analysis['selectors'].insert(0, selector)

        # Validate selectors are reasonable
        valid_selectors = []
        for selector in analysis.get('selectors', []):
            if self._validate_selector(selector):
                valid_selectors.append(selector)

        analysis['selectors'] = valid_selectors[:5]  # Limit to 5 selectors

        return analysis

    def _validate_selector(self, selector: str) -> bool:
        """Basic validation of generated selectors"""
        if not selector or not isinstance(selector, str):
            return False

        # Check for obviously invalid patterns
        invalid_patterns = [
            'skeleton',
            'loading',
            'spinner',
            'progress',
        ]

        selector_lower = selector.lower()
        for pattern in invalid_patterns:
            if pattern in selector_lower:
                return False

        # Must contain some targeting mechanism
        if not any(char in selector for char in ['#', '.', '[', ':', 'button', 'div', 'span']):
            return False

        return True

    def _get_fallback_analysis(self) -> Dict[str, Any]:
        """Return fallback analysis when AI fails"""
        return {
            'has_popup': False,
            'selectors': [],
            'multi_click': False,
            'steps': 0,
            'type': 'none',
            'confidence': 0.0,
            'reason': 'Analysis failed, using fallback',
            'elements': []
        }

    async def execute_ai_dismissal(self, page, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute dismissal based on AI analysis

        Args:
            page: Playwright page object
            analysis: AI analysis results

        Returns:
            dict: Execution results
        """
        result = {
            'success': False,
            'method': 'ai_analysis',
            'selectors_tried': [],
            'errors': []
        }

        if not analysis.get('has_popup', False) or not analysis.get('selectors', []):
            result['error'] = 'No popup detected or no selectors provided'
            return result

        selectors = analysis['selectors']
        multi_click = analysis.get('multi_click', False)
        steps = analysis.get('steps', len(selectors))

        try:
            for i, selector in enumerate(selectors[:steps]):
                try:
                    # Wait for element to be visible
                    await page.wait_for_selector(selector, timeout=5000)

                    # Get element handle
                    element = page.locator(selector).first

                    # Check if clickable
                    if await element.count() > 0 and await element.is_visible():
                        await element.click(timeout=3000)
                        result['selectors_tried'].append(selector)

                        print(f"[AI Dismissal] ✓ Clicked selector {i+1}/{steps}: {selector}")

                        # Wait between clicks for multi-step popups
                        if multi_click and i < steps - 1:
                            await page.wait_for_timeout(1000)
                        else:
                            # Single popup - verify dismissal
                            await page.wait_for_timeout(500)
                            break

                    else:
                        result['errors'].append(f"Selector not visible: {selector}")

                except Exception as e:
                    result['errors'].append(f"Failed to click {selector}: {str(e)}")
                    continue

            # Check if dismissal was successful
            result['success'] = len(result['selectors_tried']) > 0 and len(result['errors']) == 0

        except Exception as e:
            result['errors'].append(f"Execution error: {str(e)}")

        return result
