# selector_mapping.py: selector_mapping.py: AI-powered mapping of UI elements to CSS selectors.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: map_visuals_to_selectors()

"""
Selector Mapping Module
Handles AI-powered mapping of visual UI elements to CSS selectors.
"""

import json
import re
import asyncio
from typing import Dict, Optional

from .api_manager import leo_api_call_with_rotation as ai_api_call
from .utils import clean_json_response
from .prompts import get_keys_for_context, BASE_MAPPING_INSTRUCTIONS


async def map_visuals_to_selectors(
    ui_visual_context: str, html_content: str, context_key: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """Map visual UI elements to CSS selectors using AI with dynamic context-aware keys"""

    # 1. Determine Context and Keys
    ctx = context_key or "shared"
    target_keys = get_keys_for_context(ctx)
    keys_str = json.dumps(target_keys, indent=2)

    # 2. Build Prompt
    prompt = f"{BASE_MAPPING_INSTRUCTIONS}\n\n### MANDATORY KEYS FOR THIS CONTEXT:\n{keys_str}"
    
    prompt_tail = f"""
    ### INPUT DATA
    --- COMPONENT INVENTORY ---
    {ui_visual_context}
    --- DOCUMENT STRUCTURE ---
    {html_content}
    
    Provide the mapping in JSON format. No separate text or explanation.
    """

    full_prompt = prompt + prompt_tail

    try:
        # 3. AI API Call
        response = await ai_api_call(full_prompt, generation_config={"temperature": 0.1})

        if response and hasattr(response, 'text') and response.text:
            cleaned_json = clean_json_response(response.text)
            try:
                return json.loads(cleaned_json)
            except json.JSONDecodeError as json_error:
                print(f"    [MAPPING ERROR] JSON parsing failed: {json_error}")
                return None
        else:
            print(f"    [MAPPING ERROR] AI API returned no text response")
            return None

    except Exception as e:
        print(f"    [MAPPING ERROR] Failed to map visuals to selectors: {e}")
        return None
