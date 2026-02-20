# selector_utils.py: selector_utils.py: Helper functions for CSS selector manipulation.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: simplify_selectors(), _is_simple_selector(), _simplify_complex_selector()

"""
Selector Utilities Module
Handles selector simplification and processing.
"""

import re
from typing import Dict


def simplify_selectors(selectors: Dict[str, str], html_content: str) -> Dict[str, str]:
    """
    Post-process AI-generated selectors to simplify complex ones and make them more robust.
    This function runs after AI selector generation to clean up overly complex selectors.
    """
    import re

    simplified = {}

    for key, selector in selectors.items():
        original_selector = selector

        # Skip if already simple
        if _is_simple_selector(selector):
            simplified[key] = selector
            continue

        # Try to simplify complex selectors
        simplified_selector = _simplify_complex_selector(selector, html_content, key)

        if simplified_selector != selector:
            print(f"    [SELECTOR SIMPLIFIED] '{key}': '{selector}' -> '{simplified_selector}'")
        else:
            print(f"    [SELECTOR KEPT] '{key}': '{selector}' (could not simplify)")

        simplified[key] = simplified_selector

    return simplified


def _is_simple_selector(selector: str) -> bool:
    """Check if a selector is already simple enough"""
    if not selector:
        return True

    # Count selector complexity
    parts = selector.split()
    if len(parts) > 3:  # More than 3 separate selectors
        return False

    # Check for overly long class chains
    if selector.count('.') > 2:  # More than 2 classes
        return False

    # Check for deep nesting
    if selector.count('>') > 1 or selector.count(' ') > 2:  # Deep nesting
        return False

    # Check for very long selectors
    if len(selector) > 100:  # Very long selector
        return False

    return True


def _simplify_complex_selector(selector: str, html_content: str, key: str) -> str:
    """
    Attempt to simplify a complex selector by finding simpler alternatives
    """
    # Strategy 1: Look for IDs in the selector chain
    id_match = re.search(r'#[\w-]+', selector)
    if id_match:
        candidate_id = id_match.group(0)
        # Verify this ID exists and is unique in HTML
        if html_content.count(candidate_id) == 1:
            return candidate_id

    # Strategy 2: Look for unique semantic classes (prefer single classes)
    class_matches = re.findall(r'\.[\w-]+', selector)
    for class_match in class_matches:
        # Check if this single class appears only once in the HTML (making it unique)
        if html_content.count(class_match) == 1:
            return class_match

    # Strategy 3: Try attribute selectors for common patterns
    if 'button' in key.lower() or 'btn' in key.lower():
        # For buttons, try simple attribute selectors
        if 'schedule' in key.lower():
            return "a[href*='schedule']"
        if 'login' in key.lower():
            return "button:has-text('Login')"
        if 'search' in key.lower():
            return ".search-button"

    if 'input' in key.lower():
        if 'mobile' in key.lower() or 'phone' in key.lower():
            return "input[type='tel']"
        if 'password' in key.lower():
            return "input[type='password']"

    # Strategy 4: Extract the last meaningful part of complex selectors
    # For example: "div.container section.matches div.view-more a.button" -> "a.button"
    parts = selector.split()
    if len(parts) > 1:
        # Take the last 1-2 parts that look like actual selectors
        last_parts = []
        for part in reversed(parts):
            if part.strip() and not part in ['>', '+', '~', ':has-text', ':contains']:
                # Clean up malformed parts
                part = part.strip(')"\'')
                if part and not part.startswith('('):
                    last_parts.insert(0, part)
                    if len(last_parts) >= 2:  # Don't take more than 2 parts
                        break

        if last_parts:
            candidate = ' '.join(last_parts)
            # Ensure it's a valid selector and simpler
            if len(candidate) < len(selector) and _is_simple_selector(candidate):
                return candidate

    # Strategy 5: For Football.com specific patterns, use known simple selectors
    if 'full_schedule_button' in key:
        return "a[href*='schedule']"
    if 'league_header' in key:
        return ".league-title"
    if 'match_rows' in key:
        return ".match-card"
    if 'match_url' in key:
        return ".match-card a"

    # Strategy 6: Clean up malformed selectors from AI
    # Remove incomplete parts that end with quotes or parentheses
    if selector.endswith('")') or selector.endswith("')"):
        # Try to extract a valid part
        clean_parts = []
        for part in selector.split():
            part = part.strip(')"\'')
            if part and not part.startswith('(') and not part.endswith('('):
                clean_parts.append(part)
        if clean_parts:
            return ' '.join(clean_parts[-2:])  # Take last 2 clean parts

    # If no simplification found, return original (better than nothing)
    return selector
