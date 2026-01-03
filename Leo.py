# Leo.py: The central orchestrator for the LeoBook system.
# This script initializes the system and runs the primary data processing,
# and betting placement loops as defined in the Leo Handbook.
# It embodies the "observe, decide, act" loop.

import asyncio
import os
import sys
import subprocess
import requests
import time
import platform
from pathlib import Path
from datetime import datetime as dt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

#print(f"DEBUG: FB_PHONE is {'Set' if os.getenv('FB_PHONE') else 'NOT SET'}")
#print(f"DEBUG: .env location: {Path('.env').absolute()}")
#print(f"DEBUG: .env exists: {Path('.env').exists()}")

from playwright.async_api import async_playwright

from Sites.flashscore import run_flashscore_analysis
from Sites.football_com import run_football_com_booking
from Helpers.DB_Helpers.db_helpers import init_csvs
from Helpers.utils import Tee, LOG_DIR

# --- CONFIGURATION ---
CYCLE_WAIT_HOURS = 6
PLAYWRIGHT_DEFAULT_TIMEOUT = 3600000 

# Global process handle for cleanup
server_process = None

def is_server_running(base_url="http://127.0.0.1:8080"):
    """Check if the AI server is responsive."""
    for endpoint in ["/health", "/v1/models", "/"]:
        try:
            url = f"{base_url}{endpoint}"
            requests.get(url, timeout=1)
            return True
        except:
            continue
    return False

def start_ai_server():
    """Attempt to auto-start the local AI server."""
    global server_process
    
    if is_server_running():
        print("    [System] AI Server is already running. Attaching to existing instance.")
        return

    print("    [System] AI Server not detected. Attempting to auto-start...")
    mind_dir = Path("Mind")
    
    # Check if files exist
    if not mind_dir.exists():
        print(f"    [Error] 'Mind' directory not found at {mind_dir.absolute()}")
        return

    try:
        if os.name == 'nt': # Windows
            script = mind_dir / "run_split_model.bat"
            if not script.exists():
                print(f"    [Error] Startup script missing: {script}")
                return
                
            print(f"    [System] Launching {script.name} in new console...")
            # CREATE_NEW_CONSOLE is 0x10. Only works on Windows.
            server_process = subprocess.Popen([str(script.absolute())], cwd=str(mind_dir.absolute()), creationflags=subprocess.CREATE_NEW_CONSOLE)
            
        else: # Linux/Mac/Codespaces
            script = mind_dir / "run_split_model.sh"
            if not script.exists():
                print(f"    [Error] Startup script missing: {script}")
                print("    [Info] For Linux, ensure 'run_split_model.sh' and 'llama-server' binary exist in 'Mind/'")
                return
            
            print(f"    [System] Launching {script.name}...")
            # Make sure it's executable
            os.chmod(script, 0o755)
            # Run in background (nohup equivalent via Popen)
            server_process = subprocess.Popen(["bash", str(script.absolute())], cwd=str(mind_dir.absolute()))

        # Wait for initialization
        print("    [System] Waiting for server to initialize (max 120s)...")
        for i in range(120):
            if is_server_running():
                print("    [System] AI Server is ONLINE.")
                return
            time.sleep(1)
            if i % 5 == 0: print(".", end="", flush=True)
        print("\n    [Warning] Server start timed out. Proceeding anyway (Manual check recommended).")
        
    except Exception as e:
        print(f"    [Error] Failed to start AI server: {e}")

def shutdown_server():
    """Cleanly shut down the AI server if we started it."""
    global server_process
    if server_process:
        print("\n    [System] Shutting down AI Server...")
        try:
            if os.name == 'nt':
                # Force kill the process tree on Windows to close the separate console window
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(server_process.pid)], capture_output=True)
            else:
                server_process.terminate()
                server_process.wait(timeout=5)
        except Exception as e:
            print(f"    [System] Error shutting down server: {e}")
            try:
                server_process.kill()
            except:
                pass
        server_process = None

async def main():
    """
    The main execution loop for Leo.
    It continuously observes (scrapes data), decides (analyzes), and acts (books bets).
    """
    # 1. Initialize all database files (CSVs)
    print("    --- LEO: Initializing Databases ---      ")
    init_csvs()

    async with async_playwright() as p:
        while True:
            try:
                print(f"\n      --- LEO: Starting new cycle at {dt.now().strftime('%Y-%m-%d %H:%M:%S')} --- ")

                # 0. Ensure AI Server is Running
                start_ai_server()

                # --- PHASE 0: REVIEW (Observe past actions) ---
                print("\n   [Phase 0] Checking for past matches to review...")
                from Helpers.DB_Helpers.review_outcomes import run_review_process
                #await run_review_process(p)

                # Print prediction accuracy report
                print("   [Phase 0] Analyzing prediction accuracy across all reviewed matches...")
                from Helpers.DB_Helpers.prediction_accuracy import print_accuracy_report
                print_accuracy_report()
                print("   [Phase 0] Accuracy analysis complete.")

                # --- PHASE 1: ANALYSIS (Observe and Decide) ---
                print("\n   [Phase 1] Starting analysis engine (Flashscore)...")
                #await run_flashscore_analysis(p)

                # --- PHASE 2: BOOKING (Act) ---
                print("\n   [Phase 2] Starting booking process (Football.com)...")
                await run_football_com_booking(p)

                # --- PHASE 3: SLEEP (The wait) ---
                print("\n   --- LEO: Cycle Complete. ---")
                print(f"Sleeping for {CYCLE_WAIT_HOURS} hours until the next cycle...")
                await asyncio.sleep(CYCLE_WAIT_HOURS * 3600)

            except Exception as e:
                print(f"[ERROR] An unexpected error occurred in the main loop: {e}")
                print("Restarting cycle after a short delay...")
                await asyncio.sleep(60) # Wait for 60 seconds before retrying


if __name__ == "__main__":
    # Set a higher default timeout for Playwright operations
    os.environ["PLAYWRIGHT_TIMEOUT"] = str(PLAYWRIGHT_DEFAULT_TIMEOUT)
    
    # --- Terminal Logging Setup ---
    TERMINAL_LOG_DIR = LOG_DIR / "Terminal"
    TERMINAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = TERMINAL_LOG_DIR / f"leo_session_{timestamp}.log"

    log_file = open(log_file_path, "w", encoding="utf-8")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = Tee(original_stdout, log_file)
    sys.stderr = Tee(original_stderr, log_file)

    # Run the main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n   --- LEO: Shutting down gracefully. ---")
    finally:
        shutdown_server()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()
