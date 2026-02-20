# popup_detector.py: popup_detector.py: Heuristic-based detection of blocking overlays.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: PopupDetector

"""
Popup Detector Module
Analyzes HTML content to detect popup overlays, modals, and layered structures.
"""

import re
from typing import Dict, Any


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
            r'style="[^"]*pointer-events:\s*none[^"]*"',  # Blocking overlays
            r'class="[^"]*dialog-wrapper[^"]*"',  # Football.com specific
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
            r'tour[^"]*',
            r'guide[^"]*',
            r'intro[^"]*',
            r'step[^"]*',
            r'Next[^"]*',
            r'Got it[^"]*',
            r'Continue[^"]*',
            # Football.com specific patterns for guided tours
            r'm-popOver-wrapper',        # Football.com popup wrapper
            r'dialog-wrapper',           # Football.com dialog container
            r'pointer-events:\s*none',  # Blocking overlays
            r'overlay[^"]*',            # Overlay classes
            r'modal-backdrop',          # Modal backdrop
            r'backdrop',                # Backdrop classes
        ]

        self.layer_patterns = [
            r'z-index:\s*\d+',
            r'position:\s*(absolute|fixed|relative)',
        ]

    def analyze_html(self, html_content: str) -> Dict[str, Any]:
        """
        Analyze HTML content for popup structures

        Returns:
            dict: Analysis results with detection flags and metadata
        """
        analysis = {
            'has_popup': False,
            'has_overlay': False,
            'is_multi_step': False,
            'layer_count': 0,
            'blocking_elements': [],
            'popup_types': [],
            'confidence': 0.0,
            'recommendations': []
        }

        # Check for overlays
        overlay_matches = []
        for pattern in self.overlay_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            overlay_matches.extend(matches)

        analysis['has_overlay'] = len(overlay_matches) > 0
        if analysis['has_overlay']:
            analysis['popup_types'].append('overlay')
            analysis['confidence'] += 0.4

        # Check for popups
        popup_matches = []
        for pattern in self.popup_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            popup_matches.extend(matches)

        analysis['has_popup'] = len(popup_matches) > 0
        if analysis['has_popup']:
            analysis['popup_types'].append('modal')
            analysis['confidence'] += 0.3

        # Check for multi-step indicators
        multi_step_matches = []
        for pattern in self.multi_step_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            multi_step_matches.extend(matches)

        analysis['is_multi_step'] = len(multi_step_matches) > 0
        if analysis['is_multi_step']:
            analysis['popup_types'].append('guided_tour')
            analysis['confidence'] += 0.2

        # Analyze layering (z-index and positioning)
        layer_matches = []
        for pattern in self.layer_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            layer_matches.extend(matches)

        analysis['layer_count'] = len(set(layer_matches))  # Unique layers

        # Check for pointer-events blocking (common Football.com issue)
        if 'pointer-events: none' in html_content.lower():
            analysis['blocking_elements'].append('pointer_events_blocking')
            analysis['confidence'] += 0.3
            analysis['recommendations'].append('force_dismissal')

        # Determine overall confidence
        if analysis['confidence'] > 0.8:
            analysis['recommendations'].append('immediate_dismissal')
        elif analysis['confidence'] > 0.5:
            analysis['recommendations'].append('standard_dismissal')
        elif analysis['confidence'] > 0.2:
            analysis['recommendations'].append('ai_analysis')

        return analysis

    def detect_context(self, url: str) -> str:
        """
        Detect page context from URL

        Returns:
            str: Context identifier (fb_match_page, fb_general, etc.)
        """
        url_lower = url.lower()

        if 'football.com' in url_lower and ('match' in url_lower or 'game' in url_lower):
            return 'fb_match_page'
        elif 'football.com' in url_lower:
            return 'fb_general'
        else:
            return 'generic'
