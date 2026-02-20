# backtest_monitor.py: backtest_monitor.py: Module for Scripts — Pipeline.
# Part of LeoBook Scripts — Pipeline
#
# Functions: run_backtest(), monitor()

import os
import sys
import time
import json
import traceback

# Add project root to path
# Assuming this script is in Scripts/ and project root is one level up
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

from Modules.Flashscore.fs_offline import run_flashscore_offline_repredict
from Core.Intelligence.rule_config import RuleConfig

import asyncio

STORE_PATH = os.path.join(PROJECT_ROOT, "Data", "Store")
TRIGGER_FILE = os.path.join(STORE_PATH, "trigger_backtest.json")
CONFIG_FILE = os.path.join(STORE_PATH, "rule_config.json")

async def run_backtest(config):
    # Pass None for playwright as it appears unused in offline mode
    await run_flashscore_offline_repredict(playwright=None, custom_config=config)

def monitor():
    print(f"--- LeoBook Backtest Monitor Started ---")
    print(f"Watching {TRIGGER_FILE}...")
    
    while True:
        if os.path.exists(TRIGGER_FILE):
            print("\n[Trigger Detected] Starting Backtest...")
            try:
                # Read trigger info
                try:
                     with open(TRIGGER_FILE, 'r') as f:
                        trigger_data = json.load(f)
                        print(f"Requested by: {trigger_data.get('config_name', 'Unknown')}")
                except Exception as e:
                    print(f"Error reading trigger file: {e}")

                # Load Config
                if os.path.exists(CONFIG_FILE):
                     with open(CONFIG_FILE, 'r') as f:
                        config_data = json.load(f)
                        
                        # Filter config_data
                        valid_keys = RuleConfig.__annotations__.keys()
                        filtered_data = {k: v for k, v in config_data.items() if k in valid_keys}
                        
                        config = RuleConfig(**filtered_data)
                        
                        print(f"Loaded Config: {config.name}")
                        print("Running Repredict...")
                        
                        # Run Async
                        asyncio.run(run_backtest(config))
                        print("Backtest Complete.")
                else:
                    print("Error: Config file not found at " + CONFIG_FILE)

            except Exception as e:
                print(f"Error during backtest: {e}")
                traceback.print_exc()
            finally:
                # Remove trigger
                if os.path.exists(TRIGGER_FILE):
                    try:
                        os.remove(TRIGGER_FILE)
                        print("Trigger file removed.")
                    except OSError as e:
                        print(f"Error removing trigger file: {e}")
                    
        time.sleep(2)

if __name__ == "__main__":
    monitor()
