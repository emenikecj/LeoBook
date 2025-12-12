"""
Database Manager for LeoBook
Handles persistent storage for AI-learned CSS selectors and knowledge base.
"""

import json
from pathlib import Path

# Knowledge base for selector storage
KNOWLEDGE_FILE = Path("DB/knowledge.json")
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
    """Saves the selector knowledge base to disk."""
    KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
            json.dump(knowledge_db, f, indent=4)
    except Exception as e:
        print(f"Error saving knowledge: {e}")


# Initialize on import
load_knowledge()
