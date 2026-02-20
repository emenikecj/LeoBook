# selector_db.py: selector_db.py: Database manager for AI-learned CSS selectors.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: load_knowledge(), save_knowledge()

"""
Database Manager for LeoBook
Handles persistent storage for AI-learned CSS selectors and knowledge base.
"""

import json
from pathlib import Path

# Knowledge base for selector storage
KNOWLEDGE_FILE = Path("Config/knowledge.json")
knowledge_db: dict = {}


def load_knowledge():
    """Loads the selector knowledge base into memory."""
    global knowledge_db
    if KNOWLEDGE_FILE.exists():
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                knowledge_db = json.load(f)
        except Exception:
            knowledge_db = {}


def save_knowledge():
    """Performs an UPSERT operation to save knowledge."""
    KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    disk_data = {}
    
    # 1. Load existing data from disk (to avoid wiping parallel updates)
    if KNOWLEDGE_FILE.exists():
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
        except Exception:
            disk_data = {}

    # 2. Update with current memory state (Upsert)
    for context_key, memory_selectors in knowledge_db.items():
        if context_key not in disk_data:
            disk_data[context_key] = {}
        
        if isinstance(disk_data[context_key], dict) and isinstance(memory_selectors, dict):
            disk_data[context_key].update(memory_selectors)
        else:
            disk_data[context_key] = memory_selectors

    # 3. Save back to disk
    try:
        with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
            json.dump(disk_data, f, indent=4)
        print(f"    [DB] Saved knowledge base ({len(disk_data)} contexts)")
    except Exception as e:
        print(f"Error saving knowledge: {e}")


# Initialize on import
load_knowledge()
