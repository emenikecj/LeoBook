import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from Core.Intelligence.selector_db import log_selector_failure, knowledge_db
    import json

    print("--- Testing log_selector_failure ---")
    log_selector_failure("test_context", "test_key", "Test error message")
    
    if "_failures" in knowledge_db and "test_context" in knowledge_db["_failures"]:
        print("SUCCESS: Failure logged in memory.")
        
        # Check if saved to disk
        with open("Config/knowledge.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if "_failures" in data and "test_context" in data["_failures"]:
                print("SUCCESS: Failure saved to disk.")
            else:
                print("FAILED: Failure not found in Config/knowledge.json")
    else:
        print("FAILED: Failure not logged in memory.")

    print("\n--- Testing outcome_reviewer import ---")
    # This just checks if it imports without crashing
    import Data.Access.outcome_reviewer
    print("SUCCESS: outcome_reviewer imported without ImportError.")

except ImportError as e:
    print(f"IMPORT FAILED: {e}")
except Exception as e:
    print(f"ERROR: {e}")
