# selector_manager.py: selector_manager.py: Multi-strategy selector retrieval and validation.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: SelectorManager

"""
Selector Manager Module
Handles CSS selector storage, retrieval, and management for web automation.

AUTO-HEALING PHILOSOPHY:
- Conservative approach: Only heal when selectors actually fail during use
- No proactive validation or healing to avoid unnecessary AI calls
- Healing happens on-demand via heal_selector_on_failure()
- Use get_selector_with_fallback() for robust selector access with automatic healing

USAGE PATTERNS:
1. get_selector_auto() - Simple DB lookup (no healing)
2. get_selector_with_fallback() - DB lookup + on-demand healing if selector fails
3. heal_selector_on_failure() - Direct healing when you know a selector failed
"""

import os
import re
import json
import asyncio
from typing import Dict, Any, Optional

from .selector_db import load_knowledge, save_knowledge, knowledge_db
from .api_manager import unified_api_call
from .utils import clean_json_response
from .prompts import get_keys_for_context, BASE_MAPPING_INSTRUCTIONS

# ==============================================================================
# 1. SELECTOR AI MAPPING & SIMPLIFICATION (Merged from mapping & utils)
# ==============================================================================

async def map_visuals_to_selectors(
    ui_visual_context: str, html_content: str, context_key: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """Map visual UI elements to CSS selectors using AI with dynamic context-aware keys"""
    ctx = context_key or "shared"
    target_keys = get_keys_for_context(ctx)
    keys_str = json.dumps(target_keys, indent=2)

    prompt = f"{BASE_MAPPING_INSTRUCTIONS}\n\n### MANDATORY KEYS FOR THIS CONTEXT:\n{keys_str}"
    prompt_tail = f"\n### INPUT DATA\n--- COMPONENT INVENTORY ---\n{ui_visual_context}\n--- DOCUMENT STRUCTURE ---\n{html_content}\n\nProvide the mapping in JSON format. No separate text or explanation."
    full_prompt = prompt + prompt_tail

    try:
        response = await unified_api_call(full_prompt, generation_config={"temperature": 0.1, "response_mime_type": "application/json"})
        if response and hasattr(response, 'text') and response.text:
            cleaned_json = clean_json_response(response.text)
            try: return json.loads(cleaned_json)
            except json.JSONDecodeError as e: print(f"    [MAPPING ERROR] JSON parsing failed: {e}"); return None
        else:
            print(f"    [MAPPING ERROR] AI API returned no text response")
            return None
    except Exception as e:
        print(f"    [MAPPING ERROR] Failed to map visuals to selectors: {e}")
        return None

def simplify_selectors(selectors: Dict[str, str], html_content: str) -> Dict[str, str]:
    """Post-process AI-generated selectors to simplify complex ones and make them more robust."""
    simplified = {}
    for key, selector in selectors.items():
        if _is_simple_selector(selector):
            simplified[key] = selector
            continue
        
        simplified_selector = _simplify_complex_selector(selector, html_content, key)
        if simplified_selector != selector:
            print(f"    [SELECTOR SIMPLIFIED] '{key}': '{selector}' -> '{simplified_selector}'")
        else:
            print(f"    [SELECTOR KEPT] '{key}': '{selector}' (could not simplify)")
        simplified[key] = simplified_selector
    return simplified

def _is_simple_selector(selector: str) -> bool:
    if not selector: return True
    parts = selector.split()
    if len(parts) > 3: return False
    if selector.count('.') > 2: return False
    if selector.count('>') > 1 or selector.count(' ') > 2: return False
    if len(selector) > 100: return False
    return True

def _simplify_complex_selector(selector: str, html_content: str, key: str) -> str:
    id_match = re.search(r'#[\w-]+', selector)
    if id_match and html_content.count(id_match.group(0)) == 1:
        return id_match.group(0)

    for class_match in re.findall(r'\.[\w-]+', selector):
        if html_content.count(class_match) == 1:
            return class_match

    k = key.lower()
    if 'button' in k or 'btn' in k:
        if 'schedule' in k: return "a[href*='schedule']"
        if 'login' in k: return "button:has-text('Login')"
        if 'search' in k: return ".search-button"

    if 'input' in k:
        if 'mobile' in k or 'phone' in k: return "input[type='tel']"
        if 'password' in k: return "input[type='password']"

    parts = selector.split()
    if len(parts) > 1:
        last_parts = []
        for part in reversed(parts):
            if part.strip() and not part in ['>', '+', '~', ':has-text', ':contains']:
                p = part.strip(')"\'')
                if p and not p.startswith('('):
                    last_parts.insert(0, p)
                    if len(last_parts) >= 2: break
        if last_parts:
            candidate = ' '.join(last_parts)
            if len(candidate) < len(selector) and _is_simple_selector(candidate):
                return candidate

    if 'full_schedule_button' in key: return "a[href*='schedule']"
    if 'league_header' in key: return ".league-title"
    if 'match_rows' in key: return ".match-card"
    if 'match_url' in key: return ".match-card a"

    if selector.endswith('")') or selector.endswith("')"):
        clean_parts = [p.strip(')"\'') for p in selector.split() if p.strip(')"\'') and not p.startswith('(') and not p.endswith('(')]
        if clean_parts: return ' '.join(clean_parts[-2:])

    return selector

# ==============================================================================
# 2. SELECTOR MANAGER
# ==============================================================================


class SelectorManager:
    """Manages CSS selectors for web automation with auto-healing capabilities"""

    @staticmethod
    def get_selector(context: str, element_key: str) -> str:
        """Legacy synchronous accessor (does not auto-heal)."""
        return knowledge_db.get(context, {}).get(element_key, "")

    @staticmethod
    def get_selector_strict(context: str, element_key: str) -> str:
        """
        Strict accessor that raises an error if selector is missing.
        """
        selector = knowledge_db.get(context, {}).get(element_key)
        if not selector:
            raise ValueError(f"CRITICAL: Missing strict selector for '{element_key}' in context '{context}'. check knowledge.json")
        return selector

    @staticmethod
    async def get_selector_auto(page, context_key: str, element_key: str) -> str:
        """
        SMART ACCESSOR:
        1. Checks if selector exists in DB.
        2. Validates if selector is present on the current page.
        3. If missing or invalid, AUTOMATICALLY triggers TARGETED AI healing for THIS KEY ONLY.
        
        IMPORTANT: Does NOT re-analyze all selectors for the context.
        Many selectors are behind tabs/interactions and won't be visible
        in the current page state. Only heals what we actually need now.
        """
        # 1. Quick Lookup
        selector = knowledge_db.get(context_key, {}).get(element_key)

        # 2. Validation
        is_valid = False
        if selector:
            try:
                await page.wait_for_selector(selector, state='visible', timeout=5000)
                is_valid = True
            except Exception:
                is_valid = False

        # 3. Targeted Auto-Healing (SINGLE KEY ONLY)
        if not is_valid:
            print(
                f"    [Auto-Heal] Selector '{element_key}' in '{context_key}' invalid/missing. Initiating TARGETED AI repair..."
            )
            from .visual_analyzer import VisualAnalyzer
            
            info = f"Selector '{element_key}' in '{context_key}' invalid/missing."
            # TARGETED: Only ask AI about THIS specific key, not all 155+ keys
            await VisualAnalyzer.analyze_page_and_update_selectors(
                page, context_key, force_refresh=True, info=info, target_key=element_key
            )

            # Re-fetch
            selector = knowledge_db.get(context_key, {}).get(element_key)

            if selector:
                print(f"    [Auto-Heal Success] New selector for '{element_key}': {selector}")
            else:
                print(f"    [Auto-Heal Skipped] '{element_key}' not visible in current page state. Will retry when tab/section is active.")

        return str(selector) if selector else ""

    @staticmethod
    async def heal_selector_on_failure(page, context_key: str, element_key: str, failure_reason: str = "") -> str:
        """
        ON-DEMAND HEALING:
        Called only when a selector actually fails during use.
        Attempts to find a new selector for the SPECIFIC failed element only.
        """
        from .visual_analyzer import VisualAnalyzer

        print(f"    [On-Demand Heal] Selector '{element_key}' failed in '{context_key}'. Attempting TARGETED repair...")

        try:
            from .page_analyzer import PageAnalyzer
            content_is_correct = await PageAnalyzer.verify_page_context(page, context_key)

            if not content_is_correct:
                curr_url = page.url
                print(f"    [Heal Aborted] Wrong page context for '{context_key}': {curr_url}")
                return ""

            info = f"Selector '{element_key}' failed during use in '{context_key}'. {failure_reason}"
            # TARGETED: Only heal THIS specific key
            await VisualAnalyzer.analyze_page_and_update_selectors(
                page, context_key, force_refresh=True, info=info, target_key=element_key
            )

            healed_selector = knowledge_db.get(context_key, {}).get(element_key, "")
            if healed_selector:
                print(f"    [Heal Success] New selector for '{element_key}': {healed_selector}")
                return str(healed_selector)
            else:
                print(f"    [Heal Skipped] '{element_key}' not visible in current page state. May require tab navigation first.")
                return ""

        except Exception as e:
            print(f"    [Heal Error] AI healing failed for '{element_key}': {e}")
            return ""

    @staticmethod
    def has_selectors_for_context(context: str) -> bool:
        """Check if selectors exist for a given context"""
        return context in knowledge_db and bool(knowledge_db[context])

    @staticmethod
    def get_all_selectors_for_context(context: str) -> Dict[str, str]:
        """Get all selectors for a specific context"""
        return knowledge_db.get(context, {})

    @staticmethod
    def update_selector(context: str, key: str, selector: str):
        """Update a specific selector in the knowledge base"""
        if context not in knowledge_db:
            knowledge_db[context] = {}
        knowledge_db[context][key] = selector
        save_knowledge()

    @staticmethod
    def remove_selector(context: str, key: str):
        """Remove a specific selector from the knowledge base"""
        if context in knowledge_db and key in knowledge_db[context]:
            del knowledge_db[context][key]
            save_knowledge()

    @staticmethod
    def clear_context_selectors(context: str):
        """Clear all selectors for a specific context"""
        if context in knowledge_db:
            knowledge_db[context] = {}
            save_knowledge()

    @staticmethod
    def get_contexts_list() -> list:
        """Get list of all available contexts"""
        return list(knowledge_db.keys())

    @staticmethod
    def validate_selector_format(selector: str) -> bool:
        """Basic validation of CSS selector format"""
        if not selector or not isinstance(selector, str):
            return False

        # Check for obviously invalid patterns
        invalid_patterns = [
            ':contains(',  # Non-standard jQuery selector
            'skeleton',    # Loading state selectors
            'ska__',       # Skeleton loading selectors
        ]

        for pattern in invalid_patterns:
            if pattern in selector.lower():
                return False

        return True

    # ===== POPUP-SPECIFIC SELECTOR MANAGEMENT =====

    @staticmethod
    def get_popup_selectors(context: str) -> list:
        """
        Get context-aware popup dismissal selectors with Chapter 1C/2A priority

        Args:
            context: Page context (fb_match_page, fb_general, generic)

        Returns:
            list: Ordered list of selectors (priority first)
        """
        # Chapter 1C/2A: Football.com match page priority selectors - GUIDED TOUR SEQUENCE
        if context == 'fb_match_page':
            return [
                # Step 1: Next button for guided tour
                'button:has-text("Next")',
                'span:has-text("Next")',
                'button:has-text("Continue")',
                'span:has-text("Continue")',

                # Step 2: Got it completion buttons
                'button:has-text("Got it")',
                'button:has-text("Got it!")',
                'span:has-text("Got it")',
                'span:has-text("Got it!")',

                # Step 3: OK dismissal buttons (appears after tour)
                'button:has-text("OK")',
                'button:has-text("Ok")',
                'button:has-text("ok")',
                'span:has-text("OK")',
                'span:has-text("Ok")',
                'span:has-text("ok")',

                # Fallback close buttons
                'button:has-text("Skip")',
                'button:has-text("End Tour")',
                'button:has-text("Dismiss")',
                'button:has-text("Close")',
                'svg.close-circle-icon',
                'button.close',
                '[data-dismiss="modal"]',
                'svg[aria-label="Close"]',
                'button[aria-label="Close"]',
            ]

        # Football.com general pages
        elif context == 'fb_general':
            return [
                'button:has-text("Got it")',
                'button:has-text("OK")',
                'button:has-text("ok")',
                'button:has-text("Skip")',
                'button:has-text("End Tour")',
                'button:has-text("Dismiss")',
                'button:has-text("Close")',
                'svg.close-circle-icon',
                'button.close',
                '[data-dismiss="modal"]',
                'svg[aria-label="Close"]',
                'button[aria-label="Close"]',
                'button:has-text("Next")',
                'span:has-text("Next")',
            ]

        # Generic fallback selectors
        else:
            return [
                'button:has-text("Close")',
                'button:has-text("OK")',
                'button:has-text("Dismiss")',
                'button:has-text("Skip")',
                'button:has-text("Got it")',
                '[data-dismiss="modal"]',
                'svg[aria-label="Close"]',
                'button[aria-label="Close"]',
                'button.close',
                'svg.close-circle-icon',
                '.close',
                '[aria-label="Close"]',
            ]

    @staticmethod
    def learn_successful_selector(url: str, selector: str, context: Optional[str] = None):
        """
        Learn from successful popup dismissals and update knowledge base

        Args:
            url: Page URL where dismissal succeeded
            selector: Successful selector
            context: Page context (auto-detected if None)
        """
        if not context:
            context = SelectorManager._detect_context_from_url(url)

        # Update context-specific knowledge
        if context not in knowledge_db:
            knowledge_db[context] = {}

        # Store successful selector with timestamp
        import time
        knowledge_db[context][f'popup_close_{int(time.time())}'] = selector

        # Keep only recent successful selectors (last 50)
        popup_keys = [k for k in knowledge_db[context].keys() if k.startswith('popup_close_')]
        if len(popup_keys) > 50:
            # Remove oldest entries
            sorted_keys = sorted(popup_keys, key=lambda x: int(x.split('_')[-1]))
            for old_key in sorted_keys[:-50]:
                del knowledge_db[context][old_key]

        save_knowledge()
        print(f"[Selector Learning] Learned successful selector: {selector} for {context}")

    @staticmethod
    def get_learned_selectors(context: str) -> list:
        """
        Get selectors learned from successful dismissals

        Args:
            context: Page context

        Returns:
            list: Learned selectors ordered by recency
        """
        if context not in knowledge_db:
            return []

        popup_selectors = {}
        for key, selector in knowledge_db[context].items():
            if key.startswith('popup_close_'):
                timestamp = int(key.split('_')[-1])
                popup_selectors[timestamp] = selector

        # Return most recent selectors first
        return [popup_selectors[ts] for ts in sorted(popup_selectors.keys(), reverse=True)]

    @staticmethod
    def _detect_context_from_url(url: str) -> str:
        """Detect context from URL"""
        url_lower = url.lower()
        if 'football.com' in url_lower:
            if 'match' in url_lower or 'game' in url_lower:
                return 'fb_match_page'
            else:
                return 'fb_general'
        return 'generic'

    @staticmethod
    def get_all_popup_selectors(context: str) -> list:
        """
        Get complete list of popup selectors: learned + predefined

        Args:
            context: Page context

        Returns:
            list: Combined selectors with learned ones prioritized
        """
        learned = SelectorManager.get_learned_selectors(context)
        predefined = SelectorManager.get_popup_selectors(context)

        # Remove duplicates while preserving order (learned first)
        combined = learned + predefined
        seen = set()
        result = []
        for selector in combined:
            if selector not in seen:
                seen.add(selector)
                result.append(selector)

        return result
