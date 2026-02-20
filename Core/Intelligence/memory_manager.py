# memory_manager.py: memory_manager.py: Module for Core — Intelligence (AI Engine).
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: MemoryManager
# Functions: load_memory(), save_memory()

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

MEMORY_FILE = Path("Config/memory.json")
memory_db: Dict[str, Any] = {}

def load_memory():
    """Loads the success memory from Config/memory.json."""
    global memory_db
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                memory_db = json.load(f)
        except Exception:
            memory_db = {}
    else:
        memory_db = {}

def save_memory():
    """Saves memory_db to Config/memory.json."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_db, f, indent=4)
    except Exception as e:
        print(f"Error saving memory base: {e}")

class MemoryManager:
    """Manages successful interaction patterns for reinforcement learning."""

    @staticmethod
    def get_memory(context: str, element_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent successful memory for a context/element."""
        return memory_db.get(context, {}).get(element_key)

    @staticmethod
    def store_memory(context: str, element_key: str, resolution_data: Dict[str, Any]):
        """
        Record a successful resolution.
        """
        if context not in memory_db:
            memory_db[context] = {}
        
        # Enhanced resolution data with timestamp and reset failure count
        resolution_data["timestamp"] = time.time()
        resolution_data["consecutive_failures"] = 0
        
        memory_db[context][element_key] = resolution_data
        save_memory()
        print(f"    [Memory] Success recorded for '{element_key}' in '{context}'. Reinforcement strengthened.")

    @staticmethod
    def record_failure(context: str, element_key: str):
        """
        Increment the failure counter for a memory entry.
        Purge if it fails 3 times consecutively.
        """
        context_mem = memory_db.get(context, {})
        entry = context_mem.get(element_key)
        
        if not entry:
            return

        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        failures = entry["consecutive_failures"]
        
        if failures >= 3:
            print(f"    [Memory Purge] Pattern for '{element_key}' in '{context}' failed 3 times. Removing stale memory.")
            del memory_db[context][element_key]
            if not memory_db[context]:
                del memory_db[context]
        else:
            print(f"    [Memory Decay] Failure {failures}/3 recorded for '{element_key}' in '{context}'.")
        
        save_memory()

# Initialize on import
load_memory()
