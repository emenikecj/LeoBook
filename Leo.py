# Leo.py: The central orchestrator for the LeoBook system.
# This script initializes the system and runs the primary data processing,
# and betting placement loops as defined in the README.md.
# It embodies the "observe, decide, act" loop.

import asyncio
import os
import sys
import subprocess
import requests
import time
import platform
import argparse
from pathlib import Path
from datetime import datetime as dt, timedelta
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

# --- STATE MANAGEMENT ---
state = {
    "cycle_start_time": None, # Will be set at start of cycle
    "cycle_count": 0,
    "current_phase": "Startup",
    "last_action": "Init",
    "next_expected": "Startup Checks",
    "why_this_step": "System initialization",
    "expected_outcome": "Ready to start",
    "ai_server_ready": False,
    "llm_needed_for_this_cycle": False, # Flag to trigger AI server start
    "pending_count": 0,
    "booked_this_cycle": 0,
    "failed_this_cycle": 0,
    "current_balance": 0.0,
    "error_log": []
}

def log_state(phase=None, action=None, next_step=None, why=None, expect=None):
    """Updates and prints the current system state."""
    global state
    if phase: state["current_phase"] = phase
    if action: state["last_action"] = action
    if next_step: state["next_expected"] = next_step
    if why: state["why_this_step"] = why
    if expect: state["expected_outcome"] = expect
    
    print(f"   [STATE] {state['current_phase']} | Done: {state['last_action']} | Next: {state['next_expected']} | Why: {state['why_this_step']}")



def is_server_running(base_url="http://127.0.0.1:8080"):
    """Check if the AI server is responsive and model is loaded."""
    for endpoint in ["/v1/models", "/health", "/"]:
        try:
            url = f"{base_url}{endpoint}"
            resp = requests.get(url, timeout=1)
            # 503 means server is up but model is still loading
            if resp.status_code == 200:
                return True
            if resp.status_code == 503:
                # Log that it's loading but not ready
                return False
        except:
            continue
    return False

def start_ai_server():
    """Attempt to auto-start the local AI server with automatic setup if needed."""
    global server_process

    if is_server_running():
        print("    [System] AI Server is already running. Attaching to existing instance.")
        return

    print("    [System] AI Server not detected. Attempting to auto-start...")
    mind_dir = Path("Mind")

    # Check if Mind directory exists
    if not mind_dir.exists():
        print(f"    [Error] 'Mind' directory not found at {mind_dir.absolute()}")
        return

    # Check for required files and auto-setup if needed
    setup_needed = False
    if os.name == 'nt':  # Windows
        executable = mind_dir / "llama-server.exe"
        script = mind_dir / "run_split_model.bat"
        setup_script = mind_dir / "setup_windows_env.ps1"
    else:  # Linux/Mac/Codespaces
        executable = mind_dir / "llama-server"
        script = mind_dir / "run_split_model.sh"
        # Use Codespaces-specific script if in Codespaces, otherwise use Linux script
        if os.environ.get('CODESPACES') == 'true':
            setup_script = mind_dir / "setup_codespaces_env.sh"
        else:
            setup_script = mind_dir / "setup_linux_env.sh"

    # Check if executable exists
    if not executable.exists():
        print(f"    [Warning] AI executable not found: {executable}")
        setup_needed = True
    else:
        # Check if executable can run (test library dependencies)
        try:
            if os.name == 'nt':
                # On Windows, just check if file exists (library check is harder)
                pass
            else:
                # On Linux, test with ldd to check for missing libraries
                result = subprocess.run(["ldd", str(executable)], capture_output=True, text=True, cwd=str(mind_dir))
                if "not found" in result.stdout or "not found" in result.stderr:
                    print("    [Warning] Missing shared libraries detected. Auto-setup required.")
                    setup_needed = True
        except:
            print("    [Warning] Could not verify executable dependencies. Auto-setup recommended.")
            setup_needed = True

    # Auto-setup if needed
    if setup_needed and setup_script.exists():
        print(f"    [System] Running auto-setup: {setup_script}")
        try:
            if os.name == 'nt':
                subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(setup_script)], check=True)
            else:
                os.chmod(setup_script, 0o755)
                subprocess.run([str(setup_script)], check=True)
            print("    [System] Auto-setup completed successfully.")
        except Exception as e:
            print(f"    [Error] Auto-setup failed: {e}")
            print("    [Info] Please run setup manually or check the Mind folder setup.")
            return
    elif setup_needed:
        print(f"    [Error] Setup required but setup script not found: {setup_script}")
        print("    [Info] Please ensure AI dependencies are properly installed.")
        return

    # Check if startup script exists
    if not script.exists():
        print(f"    [Error] Startup script missing: {script}")
        return

    try:
        if os.name == 'nt': # Windows
            print(f"    [System] Launching {script.name} in new console...")
            # CREATE_NEW_CONSOLE is 0x10. Only works on Windows.
            server_process = subprocess.Popen([str(script.absolute())], cwd=str(mind_dir.absolute()), creationflags=subprocess.CREATE_NEW_CONSOLE)

        else: # Linux/Mac/Codespaces
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
    Adheres to the "Observe, Decide, Act" algorithm with strict phases.
    """
    # 1. Initialize all database files (CSVs)
    log_state(phase="Init", action="Initializing Databases")
    init_csvs()

    async with async_playwright() as p:
        while True:
            try:
                state["cycle_count"] += 1
                state["cycle_start_time"] = dt.now()
                log_state(phase="Cycle Start", action=f"Starting Cycle #{state['cycle_count']}", next_step="Phase 0: Review")

                # NOTE: AI Server is NOT started here anymore. 
                # It is lazy-loaded in Phase 2 only if needed.

                # --- PHASE 0: REVIEW (Observe past actions) ---
                log_state(phase="Phase 0", action="Reviewing Outcomes", next_step="Accuracy Report")
                from Helpers.DB_Helpers.review_outcomes import run_review_process
                #await run_review_process(p)

                # Print prediction accuracy report
                log_state(phase="Phase 0", action="Generating Accuracy Report", next_step="Phase 1: Analysis")
                from Helpers.DB_Helpers.prediction_accuracy import print_accuracy_report
                print_accuracy_report()

                # --- PHASE 1: ANALYSIS (Observe and Decide) ---
                log_state(phase="Phase 1", action="Starting Flashscore Analysis", next_step="Phase 2: Booking")
                # This phase initiates the headless browser and extracts specific target data
                await run_flashscore_analysis(p)

                # --- PHASE 2: BOOKING (Act) ---
                log_state(phase="Phase 2", action="Starting Booking Process", next_step="Sleep")
                # This phase now strictly follows Harvest -> Execute flow
                await run_football_com_booking(p)

                # --- PHASE 3: SLEEP (The wait) ---
                log_state(phase="Phase 3", action="Cycle Complete", next_step=f"Sleeping {CYCLE_WAIT_HOURS}h")
                print(f"Sleeping for {CYCLE_WAIT_HOURS} hours until the next cycle...")
                await asyncio.sleep(CYCLE_WAIT_HOURS * 3600)

            except Exception as e:
                state["error_log"].append(f"{dt.now()}: {e}")
                print(f"[ERROR] An unexpected error occurred in the main loop: {e}")
                print("Restarting cycle after a short delay...")
                await asyncio.sleep(60) # Wait for 60 seconds before retrying


async def main_offline_repredict():
    """
    Offline reprediction mode: Use stored data to repredict future matches.
    """
    from Sites.flashscore import run_flashscore_offline_repredict

    print("    --- LEO: Offline Reprediction Mode ---      ")
    # 1. Initialize all database files (CSVs)
    init_csvs()

    async with async_playwright() as p:
        try:
            print(f"\n      --- LEO: Starting offline reprediction at {dt.now().strftime('%Y-%m-%d %H:%M:%S')} --- ")

            # 0. Ensure AI Server is Running
            start_ai_server()

            # --- PHASE 0: REVIEW (Observe past actions) ---
            print("\n   [Phase 0] Checking for past matches to review...")
            from Helpers.DB_Helpers.review_outcomes import run_review_process
            await run_review_process(p)

            # Print prediction accuracy report
            print("   [Phase 0] Analyzing prediction accuracy across all reviewed matches...")
            from Helpers.DB_Helpers.prediction_accuracy import print_accuracy_report
            print_accuracy_report()
            print("   [Phase 0] Accuracy analysis complete.")

            # --- PHASE 1: OFFLINE REPREDICTION ---
            print("\n   [Phase 1] Starting offline reprediction engine...")
            await run_flashscore_offline_repredict(p)

            print("\n   --- LEO: Offline Reprediction Complete. ---")

        except Exception as e:
            print(f"[ERROR] An unexpected error occurred in offline reprediction: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeoBook Prediction System")
    parser.add_argument('--offline-repredict', action='store_true',
                       help='Run offline reprediction using stored data instead of scraping')
    args = parser.parse_args()

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

    # Run the appropriate async function
    try:
        if args.offline_repredict:
            asyncio.run(main_offline_repredict())
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        print("\n   --- LEO: Shutting down gracefully. ---")
    finally:
        shutdown_server()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()
