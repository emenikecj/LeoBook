# visual_analyzer.py: visual_analyzer.py: Advanced multimodal UI analysis engine.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: VisualAnalyzer
# Functions: get_visual_ui_analysis()

"""
Visual Analyzer Module
Handles screenshot analysis and visual UI processing using Local Leo AI.
Orchestrates sub-modules for visual analysis, selector mapping, and recovery.
"""

import os
import re
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from .selector_db import knowledge_db, save_knowledge
from ..Browser.page_logger import log_page_html
from ..Utils.utils import LOG_DIR


# Import sub-modules
from .html_utils import clean_html_content
from .selector_mapping import map_visuals_to_selectors
from .selector_utils import simplify_selectors

# --- Vision Integration ---

async def get_visual_ui_analysis(page: Any, context_key: str = "unknown") -> str:
    from .api_manager import grok_api_call
    import os

    print(f"    [VISION] Loading UI/UX analysis from logged screenshot for '{context_key}'...")

    # Look in Page subdirectory where screenshots are saved
    PAGE_LOG_DIR = LOG_DIR / "Page"
    files = list(PAGE_LOG_DIR.glob(f"*{context_key}.png"))

    if not files:
        print(f"    [VISION ERROR] No screenshot found for context: {context_key}")
        return ""

    # Get the most recent screenshot
    png_file = max(files, key=os.path.getmtime)
    print(f"    [VISION] Using logged screenshot: {png_file.name}")

    try:
        # Check if file is not empty (successful screenshot)
        if png_file.stat().st_size == 0:
            print(f"    [VISION ERROR] Screenshot file is empty: {png_file.name}")
            return ""

        image_data = {"mime_type": "image/png", "data": png_file.read_bytes()}

        prompt = """
        You are a senior front-end engineer and UI/UX analyst with 15+ years of experience in reverse-engineering complex web applications.
        Your task: Perform an exhaustive, pixel-perfect visual inventory of the provided screenshot.
        Analyze every visible element on the page — nothing is too small.
        Organize your response using ONLY this exact hierarchical structure (do not deviate):
        1. Layout & Structural Elements
           • Overall page layout (e.g., "fixed header + sticky secondary nav + main content + right sidebar")
           • Fixed, sticky, or absolute-positioned containers
           • Scroll containers and overflow boundaries
        2. Navigation Components
           • Primary and secondary navigation bars
           • Tab groups with current active state clearly marked
           • Icon buttons (hamburger, back, close, search, profile)
        3. Interactive Controls
           • Buttons: text, icon-only, outlined, filled, FABs — include visible text and state
           • Toggles, switches, checkboxes, radio groups
           • Text inputs, search fields, filters
        4. Content & Data Display
           • Cards, lists, tables, expandable rows
           • Match/event rows (critical — describe structure in detail)
           • Typography: headings, labels, timestamps, scores, team names
           • Badges, chips, tags, live indicators (LIVE, HT, FT)
        5. Advertising & Promotional
           • All ad containers and close buttons
        6. System & Feedback Elements
           • Cookie consent banners, privacy modals
           • Loading skeletons, spinners
        7. Other Notable Elements
           • Language selector, dark mode toggle

        For every element, use brief naming: "UI Element Name: Exact Text (or Function if no text)".
        Include: Position, Repetition, State.
        Be exhaustive. Do not summarize.
        """
        response = await grok_api_call(
            [prompt, image_data],
            generation_config={"temperature": 0.1}
        )

        if response and hasattr(response, 'text') and response.text:
            print("    [VISION] UI/UX Analysis complete.")
            return response.text
        else:
            print("    [VISION ERROR] No valid response from Grok API")
            return ""

    except Exception as e:
        print(f"    [VISION ERROR] Failed to analyze screenshot: {e}")
        return ""


class VisualAnalyzer:
    """Handles visual analysis of web pages by orchestrating sub-modules"""

    @staticmethod
    async def analyze_page_and_update_selectors(
        page,
        context_key: str,
        force_refresh: bool = False,
        info: Optional[str] = None,
        target_key: Optional[str] = None,
    ):
        """
        1. Checks if selectors exist. If they do and not force_refresh, skips.
        2. Captures Visual UI Inventory (The What).
        3. Captures HTML (The How).
        4. Maps Visuals to HTML Selectors.
        
        CONTEXTUAL DISCOVERY:
        - Many selectors for a page context live behind tabs/interactions
          (e.g. standings selectors are only visible on the Standings tab).
        - When target_key is provided: ONLY ask AI about that ONE selector.
          This is the fast path for on-demand healing.
        - When target_key is None: bulk mode, update whatever is visible.
          Never loops — accepts that some selectors won't be found in the
          current page state. They'll be healed when their tab is active.
        """
        Focus = info

        # --- Determine mode ---
        existing_selectors = knowledge_db.get(context_key, {})
        
        if target_key:
            # TARGETED MODE: Only heal this specific key
            keys_to_find = [target_key]
            print(f"    [AI INTEL] TARGETED Discovery for '{target_key}' in '{context_key}'...")
        else:
            # BULK MODE: Try all keys, accept partial results
            keys_to_find = list(existing_selectors.keys())
            print(f"    [AI INTEL] Bulk Discovery for context: '{context_key}' ({len(keys_to_find)} keys)...")

        print(f"    [AI INTEL] Taking Screenshot and HTML capture of: '{context_key}'...")
        await log_page_html(page, context_key)

        # Step 1: Get Visual Context
        ui_visual_context = await get_visual_ui_analysis(page, context_key)
        if not ui_visual_context:
            return

        PAGE_LOG_DIR = LOG_DIR / "Page"
        files = list(PAGE_LOG_DIR.glob(f"*{context_key}.html"))
        if not files:
            print(f"    [AI INTEL ERROR] No HTML file found for context: {context_key}")
            return

        html_file = max(files, key=os.path.getmtime)
        print(f"    [AI INTEL] Using logged HTML: {html_file.name}")

        try:
            with open(html_file, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            print(f"    [AI INTEL ERROR] Failed to load HTML: {e}")
            return

        # Optional: Minimal clean to save tokens
        html_content = re.sub(r"<script.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r"<style.*?</style>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = html_content[:100000]

        # --- Build prompt based on mode ---
        keys_list_str = ", ".join([f'"{k}"' for k in keys_to_find])

        if target_key:
            # TARGETED PROMPT: Focused, fast, cheap
            prompt = f"""
    You are an elite front-end reverse-engineer. Find the CSS selector for ONE specific element.
    
    ### GOAL
    Find the CSS selector for the key: "{target_key}" in the context "{context_key}".
    
    ### CRITICAL RULES
    1. Return ONLY a JSON object with this exact structure: {{"{target_key}": "<css_selector>"}}
    2. If the element is NOT visible in the current page state (e.g. behind a tab, collapsed section, or requires interaction to reveal), return an EMPTY JSON object: {{}}
    3. DO NOT guess. DO NOT return selectors for elements you cannot see.
    4. RETURN ONLY valid JSON. No markdown. No explanations.
    
    ### SELECTOR QUALITY
    - Prefer IDs > data-attributes > specific Classes.
    - Avoid unstable generated classes (e.g., 'css-1abc').
    - Ensure the selector uniquely identifies the element.

    ### CONTEXT
    {info or ""}
    """
        else:
            # BULK PROMPT: Tolerant of missing selectors
            prompt = f"""
    You are an elite front-end reverse-engineer. Your task is to perform a STRICT UPSERT of CSS selectors.
    
    ### GOAL
    For the given list of EXISTING KEYS, find the most accurate CSS selector in the provided HTML source.
    
    ### CRITICAL RULES
    1. ONLY return keys from this list: [{keys_list_str}]
    2. DO NOT create new keys.
    3. DO NOT modify the structure of the keys.
    4. If you cannot find a selector for a key (e.g. the element is behind a tab, collapsed, or not visible), OMIT it from the response. This is EXPECTED — not all selectors are visible at once.
    5. RETURN ONLY a valid JSON object. No markdown. No explanations.
    
    ### SELECTOR QUALITY
    - Prefer IDs > data-attributes > specific Classes.
    - Avoid unstable generated classes (e.g., 'css-1abc').
    - Ensure selectors are uniquely identifiable within the context.
    """

        prompt_tail = f"""
        ### INPUT
        --- VISUAL INVENTORY ---
        {ui_visual_context}
        --- CLEANED HTML SOURCE ---
        {html_content}
        Return ONLY the JSON mapping. No explanations. No markdown.
        """

        full_prompt = prompt + prompt_tail

        try:
            from .api_manager import gemini_api_call_with_rotation
            response = await gemini_api_call_with_rotation(
                full_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            # Fix for JSON Decode Errors
            from .utils import clean_json_response
            cleaned_json = clean_json_response(response.text)
            new_selectors = json.loads(cleaned_json)

            # Apply results
            updated_count = 0
            if context_key not in knowledge_db:
                knowledge_db[context_key] = {}
                
            for key, selector in new_selectors.items():
                if target_key:
                    # TARGETED: Accept the result for the target key (UPDATE or UPSERT)
                    if key == target_key:
                        knowledge_db[context_key][key] = selector
                        updated_count += 1
                elif key in existing_selectors:
                    # BULK: Strict upsert — only update existing keys
                    knowledge_db[context_key][key] = selector
                    updated_count += 1
                else:
                    print(f"    [AI INTEL WARNING] AI hallucinated new key '{key}'. Ignored (Strict Upsert Mode).")

            save_knowledge()
            
            if target_key:
                if updated_count:
                    print(f"    [AI INTEL] Successfully healed '{target_key}' in '{context_key}'.")
                else:
                    print(f"    [AI INTEL] '{target_key}' not found in current page state. Element may be behind a tab or require interaction.")
            else:
                print(f"    [AI INTEL] Successfully upserted {updated_count}/{len(keys_to_find)} elements in context '{context_key}'.")
        except Exception as e:
            print(f"    [AI INTEL ERROR] Failed to generate selectors map: {e}")
            return

    # Re-export key functions as static methods for backward compatibility if needed
    @staticmethod
    async def get_visual_ui_analysis(page, context_key: str) -> Optional[str]:
        return await get_visual_ui_analysis(page, context_key)

    @staticmethod
    def clean_html_content(html_content: str) -> str:
        return clean_html_content(html_content)

    @staticmethod
    async def map_visuals_to_selectors(
        ui_visual_context: str, html_content: str, focus: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        return await map_visuals_to_selectors(ui_visual_context, html_content, focus)

    @staticmethod
    def simplify_selectors(selectors: Dict[str, str], html_content: str) -> Dict[str, str]:
        return simplify_selectors(selectors, html_content)
