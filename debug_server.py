
import subprocess
import os
import sys

print("--- Starting Debug ---")
script_path = "Mind/setup_codespaces_env.sh"

if not os.path.exists(script_path):
    print(f"Error: {script_path} not found.")
    # Check current dir
    print(f"Current dir: {os.getcwd()}")
    print("Listing Mind:")
    try:
        print(os.listdir("Mind"))
    except Exception as e:
        print(e)
    sys.exit(1)

# Make executable just in case
subprocess.run(["chmod", "+x", script_path])

print(f"Running {script_path}...")
try:
    result = subprocess.run([f"./{script_path}"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    with open("debug_output.txt", "w") as f:
        f.write("--- STDOUT ---\n")
        f.write(result.stdout)
        f.write("\n--- STDERR ---\n")
        f.write(result.stderr)
        f.write(f"\n--- Exit Code: {result.returncode} ---\n")
except Exception as e:
    with open("debug_output.txt", "w") as f:
        f.write(f"Execution failed: {e}")
