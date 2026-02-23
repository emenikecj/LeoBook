import sys
import os

sys.path.append(os.getcwd())

print("--- Step 1: Importing selector_db ---")
try:
    from Core.Intelligence.selector_db import log_selector_failure
    print("SUCCESS: selector_db imported.")
    log_selector_failure("test_context", "test_key", "Test error")
    print("SUCCESS: log_selector_failure executed.")
except Exception as e:
    print(f"FAILED: {e}")

print("\n--- Step 2: Importing outcome_reviewer ---")
try:
    import Data.Access.outcome_reviewer
    print("SUCCESS: outcome_reviewer imported.")
except Exception as e:
    print(f"FAILED: {e}")
