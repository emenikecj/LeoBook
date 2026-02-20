# interaction_engine.py: interaction_engine.py: Module for Core — Intelligence (AI Engine).
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: execute_smart_action()

import asyncio
import json
import time
from typing import Any, Callable, Dict, Optional

from .visual_analyzer import VisualAnalyzer
from .selector_db import knowledge_db
from .memory_manager import MemoryManager
from .aigo_engine import AIGOEngine
from .page_analyzer import PageAnalyzer  # For Phase 0

async def execute_smart_action(
    page: Any,
    context_key: Optional[str] = None,
    element_key: str = "",
    action_fn: Callable[[str], Any] = None,
    max_retries: int = 2,
    objective: str = "Standard Interaction",
    expected_format: Optional[str] = None
) -> Any:
    """
    Wraps browser actions with a Reinforcement Learning and AIGO Fallback loop.
    Phase 0: Context Discovery (Auto-detect page role if context_key is missing).
    Phase 1: Memory Reinforcement (Try learned patterns first).
    Phase 2: Standard Resiliency (1 Initial + 2 AI-Heals).
    Phase 3: AIGO Expert Fallback (Troubleshooting Expert).
    """
    last_error = None
    
    # --- PHASE 0: CONTEXT DISCOVERY ---
    is_uncertain = False
    if not context_key:
        print("    [Phase 0] No context provided. Probing page state...")
        context_key, is_uncertain = await PageAnalyzer.identify_context(page)
        print(f"    [Phase 0] Identified context: '{context_key}' (Uncertain: {is_uncertain})")

    # --- PHASE 1: REINFORCEMENT LEARNING ---
    # Skip memory if context is uncertain or urgency is triggered
    memory = MemoryManager.get_memory(context_key, element_key)
    if not is_uncertain and memory and memory.get("selector"):
        mem_sel = memory["selector"]
        print(f"    [Memory] Testing recent success pattern...")
        try:
            return await action_fn(mem_sel)
        except Exception:
            print(f"    [Memory Stale] Pattern failed.")
            MemoryManager.record_failure(context_key, element_key)

    # --- PHASE 2: STANDARD RETRIES (FAILURE HEATMAP TRACKING) ---
    failure_heatmap = []
    heal_failures = 0
    
    # If uncertain, force a deep discovery immediately
    if is_uncertain:
        print("    [Phase 2 URGENCY] Context uncertain. Triggering Full-Pixel discovery...")
        await VisualAnalyzer.analyze_page_and_update_selectors(page, context_key, info="Uncertain Context")

    for attempt in range(max_retries + 1):
        selector = knowledge_db.get(context_key, {}).get(element_key)
        
        if not selector:
            await VisualAnalyzer.analyze_page_and_update_selectors(page, context_key, info=f"Awaiting: {element_key}")
            selector = knowledge_db.get(context_key, {}).get(element_key)

        if selector:
            try:
                # Dynamic Probe (V4) - Check visibility/interactability before execution
                locator = page.locator(selector).first
                if await locator.count() > 0:
                    is_visible = await locator.is_visible()
                    if not is_visible:
                        raise Exception(f"Element '{selector}' is in DOM but NOT VISIBLE.")
                
                result = await action_fn(selector)
                MemoryManager.store_memory(context_key, element_key, {"action_type": "HEALED_SUCCESS", "selector": selector})
                return result
            except Exception as e:
                last_error = e
                failure_heatmap.append({"selector": selector, "error": str(e), "attempt": attempt + 1})
                print(f"    [Failure {attempt+1}/3] {e}")
        
        if attempt < max_retries:
            heal_failures += 1
            await VisualAnalyzer.analyze_page_and_update_selectors(page, context_key, info=f"Retry: {str(last_error)}")
            await asyncio.sleep(1.0)

    # --- PHASE 3: AIGO EXPERT FALLBACK (PRIMARY + BACKUP PATH) ---
    for aigo_cycle in range(2):
        print(f"    [AIGO Cycle {aigo_cycle+1}/2] Requesting Redundant Resolution...")
        aigo_res = await AIGOEngine.invoke_aigo(
            page, context_key, element_key,
            failure_msg=str(last_error),
            objective=objective,
            expected_format=expected_format,
            heal_failure_count=heal_failures,
            failure_heatmap=failure_heatmap
        )

        if aigo_res.get("is_resolution_complete"):
            # Execute logic for either Primary or Backup
            async def execute_path(path_data: Dict[str, Any]) -> Any:
                p_type = path_data.get("type", "A")
                
                # Path B: Actions
                if p_type == "B" and path_data.get("recovery_steps"):
                    for step in path_data.get("recovery_steps"):
                        if step.startswith(('.', '#', '[')):
                            await page.click(step, timeout=5000)
                
                # Path A or B: Selector Interaction
                h_sel = path_data.get("healed_selector")
                if (p_type in ["A", "B"]) and h_sel:
                    # DYNAMIC PROBE (V4): Quick check before commitment
                    if await page.locator(h_sel).first.is_visible():
                        return await action_fn(h_sel)
                    raise Exception(f"Expert path '{h_sel}' failed dynamic visibility check.")
                
                # Path C: Direct Extraction
                if p_type == "C" and path_data.get("direct_extraction"):
                    return path_data["direct_extraction"]
                
                return None

            try:
                # Try PRIMARY PATH first
                print("    [AIGO] Attempting Primary Path...")
                return await execute_path(aigo_res.get("primary_path", {}))
            except Exception as primary_e:
                print(f"    [AIGO PRIMARY FAIL] {primary_e}. Falling back to BACKUP PATH in same cycle...")
                try:
                    # Try BACKUP PATH immediately (Intra-cycle fallback)
                    return await execute_path(aigo_res.get("backup_path", {}))
                except Exception as backup_e:
                    print(f"    [AIGO BACKUP FAIL] {backup_e}.")
                    last_error = backup_e
                    continue

    # --- FATAL ESCALATION ---
    print(f"\n    [FATAL ERROR] MISSION FAILURE at '{element_key}' in '{context_key}'. Escalating to human.")
    with open("Config/fatal_blockers.log", "a") as f:
        f.write(f"[{time.ctime()}] FATAL: {element_key} in {context_key}. Heatmap: {failure_heatmap}\n")
    if last_error: raise last_error
    raise RuntimeError(f"Unrecoverable interaction failure for '{element_key}'")
