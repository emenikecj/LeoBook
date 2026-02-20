# aigo_engine.py: aigo_engine.py: AIGO Phase 3 Expert Consultation via Grok API.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: AIGOEngine
# Functions: _extract_json_with_salvage()

import os
import re
import json
import time
import base64
import asyncio
from typing import Dict, Any, Optional, List

from ..Utils.utils import LOG_DIR
from ..Browser.page_logger import log_page_html
from .selector_db import knowledge_db, save_knowledge
from .memory_manager import MemoryManager


def _extract_json_with_salvage(text: str) -> Optional[Dict]:
    """Robust JSON extraction with progressive salvage strategies."""
    if not text:
        return None

    # 1. Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. Strip markdown fences
    text = re.sub(r'^```json\s*|\s*```$', '', text.strip())

    # 3. Try to fix truncation
    if not text.endswith('}'):
        text += '}}' if text.count('{') > text.count('}') + 1 else '}'

    try:
        return json.loads(text)
    except Exception:
        pass

    # 4. Last resort: find largest JSON-like block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    return None


class AIGOEngine:
    """Advanced AI operator for resolving complex interaction/extraction failures via Grok."""

    @staticmethod
    async def invoke_aigo(
        page: Any,
        context_key: str,
        element_key: str,
        failure_msg: str,
        objective: str = "Standard Interaction",
        expected_format: Optional[str] = None,
        heal_failure_count: int = 0,
        failure_heatmap: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Phase 3 Expert Consultation.
        Captures artifacts, builds prompt, calls Grok, validates response.
        Returns parsed resolution dict with primary_path + backup_path.
        """
        print(f"    [AIGO] Invoking Expert for: {objective}")

        # ── 1. Capture Artifacts ──
        timestamp = int(time.time())
        tag = f"AIGO_{context_key}_{timestamp}"
        await log_page_html(page, tag)

        PAGE_LOG_DIR = LOG_DIR / "Page"
        screenshot_files = list(PAGE_LOG_DIR.glob(f"*{tag}.png"))
        html_files = list(PAGE_LOG_DIR.glob(f"*{tag}.html"))

        if not screenshot_files or not html_files:
            return {"status": "error", "message": "Failed to capture artifacts for AIGO."}

        png_path = max(screenshot_files, key=lambda p: p.stat().st_mtime)
        html_path = max(html_files, key=lambda p: p.stat().st_mtime)

        # Base64 encode screenshot for Grok vision
        screenshot_b64 = base64.b64encode(png_path.read_bytes()).decode("utf-8")

        # Read and sanitize HTML
        with open(html_path, "r", encoding="utf-8") as f:
            raw_html = f.read()

        cleaned_html = re.sub(r"<script.*?</script>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
        cleaned_html = re.sub(r"<style.*?</style>", "", cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        cleaned_html = cleaned_html[:8000]  # Truncate to fit token limits

        # ── 2. Build Heatmap String ──
        heatmap_str = "None"
        if failure_heatmap:
            heatmap_str = "Previous failed attempts (DO NOT REPEAT THESE):\n" + "\n".join(
                [f"- Attempt {i+1}: Selector='{f.get('selector','')}' → Failed: {f.get('error','unknown')}"
                 for i, f in enumerate(failure_heatmap)]
            )

        # ── 3. Build Prompt ──
        current_knowledge = json.dumps(knowledge_db.get(context_key, {}), indent=2)

        prompt = f"""You are AIGO: Elite Troubleshooting Expert for web automation (V5).
Mission: Resolve a critical interaction failure with REDUNDANT and DIVERSE paths.

### MISSION CONTEXT
- **Objective**: {objective}
- **Target Element**: {element_key}
- **Context**: {context_key}
- **Page URL**: {page.url}
- **Failure Traceback**: {failure_msg}
- **Phase 2 Failures**: {heal_failure_count} attempts failed.
- **Failure Heatmap**: {heatmap_str}

### KNOWLEDGE BASE
{current_knowledge}

### CRITICAL RULES
1. **HEATMAP ANALYSIS**: Do NOT suggest selectors from the heatmap unless you provide a CLEAR MODIFICATION (parent traversal, attribute-based, sibling navigation).
2. **PATH DIVERSITY MANDATE**: Primary and Backup paths MUST be DIFFERENT types:
   - Path A (Selector) → Backup must be B or C
   - Path B (Action Sequence) → Backup must be A or C
   - Path C (Direct Extraction) → Backup must be A or B
3. Output ONLY valid JSON — no explanations, no markdown.

### PATH DEFINITIONS
- **Path A (Selector)**: A single robust CSS selector for direct interaction.
- **Path B (Action Sequence)**: Preparatory steps (dismiss overlay, scroll) + selector.
- **Path C (Direct Extraction)**: Bypass UI; extract data directly from HTML/screenshot.

### OUTPUT FORMAT (MANDATORY JSON)
{{
    "diagnosis": "Heatmap analysis and failure explanation",
    "primary_path": {{
        "type": "A" | "B" | "C",
        "healed_selector": "CSS selector (if A or B)",
        "recovery_steps": ["Step 1", "Step 2"] (if B),
        "direct_extraction": "Extracted data" (if C)
    }},
    "backup_path": {{
        "type": "MUST BE DIFFERENT FROM PRIMARY",
        "healed_selector": "CSS selector (if A or B)",
        "recovery_steps": ["Step 1"] (if B),
        "direct_extraction": "Data" (if C)
    }},
    "is_resolution_complete": true
}}"""

        if expected_format:
            prompt += f"\n\nExpected output format for extraction: {expected_format}"

        # ── 4. Build Payload for Grok (multimodal) ──
        prompt_content = [
            prompt,
            {"inline_data": {"data": screenshot_b64, "mime_type": "image/png"}},
            f"Sanitized HTML excerpt:\n{cleaned_html}"
        ]

        # ── 5. Call Grok with Retry ──
        from .api_manager import grok_api_call

        for attempt in range(3):
            try:
                response = await grok_api_call(prompt_content)

                if response is None:
                    print(f"    [AIGO] Attempt {attempt+1}: Grok returned None")
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

                # Parse and salvage JSON
                parsed = _extract_json_with_salvage(response.text)

                if not parsed or not isinstance(parsed, dict):
                    print(f"    [AIGO] Attempt {attempt+1}: Invalid JSON response")
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

                # Validate required structure
                if "primary_path" not in parsed or "backup_path" not in parsed:
                    print(f"    [AIGO] Attempt {attempt+1}: Missing primary/backup paths")
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

                # ── 6. Path Diversity Enforcement ──
                p_path = parsed.get("primary_path", {})
                b_path = parsed.get("backup_path", {})
                p_type = p_path.get("type", "A")
                b_type = b_path.get("type", "A")

                if p_type == b_type:
                    print(f"    [AIGO WARNING] Path diversity violated (Primary={p_type}, Backup={b_type}). Forcing Backup to C.")
                    b_path["type"] = "C"
                    b_path["direct_extraction"] = f"FALLBACK: Extract '{element_key}' from HTML/screenshot"
                    parsed["backup_path"] = b_path

                # ── 7. Persist to Memory ──
                MemoryManager.store_memory(context_key, element_key, {
                    "action_type": f"AIGO_V5_{p_type}",
                    "selector": p_path.get("healed_selector"),
                    "diagnosis": parsed.get("diagnosis")
                })

                # Update knowledge DB if selector provided
                healed_sel = p_path.get("healed_selector")
                if p_type in ["A", "B"] and healed_sel:
                    if context_key not in knowledge_db:
                        knowledge_db[context_key] = {}
                    knowledge_db[context_key][element_key] = healed_sel
                    save_knowledge()

                print(f"    [AIGO SUCCESS] Paths: Primary={p_type}, Backup={b_type}. Diagnosis: {parsed.get('diagnosis', 'N/A')}")
                return parsed

            except Exception as e:
                print(f"    [AIGO] Attempt {attempt+1} failed: {e}")
                await asyncio.sleep(5 * (attempt + 1))

        print("    [AIGO FATAL] Failed to get valid response from Grok after 3 attempts")
        return {"status": "error", "message": "AIGO Expert consultation failed after 3 attempts."}
