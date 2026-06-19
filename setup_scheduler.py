import os
import sys
import subprocess
import ctypes

# Configure stdout and stderr for UTF-8 to prevent encoding issues on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(BASE_DIR, "run_pinterest_advertiser.py")

def main():
    print("==================================================")
    print("      PINTEREST AUTOMATION TASK SCHEDULER         ")
    print("==================================================")
        
    # Get python path
    python_exe = sys.executable
    print(f"Python path: {python_exe}")
    print(f"Script path: {SCRIPT_PATH}")
    
    # Verify script exists
    if not os.path.exists(SCRIPT_PATH):
        print(f"❌ Error: Script not found at {SCRIPT_PATH}")
        sys.exit(1)
        
    # Clean up old task names if they exist
    print("Cleaning up old task names if they exist...")
    for old_tn in ["PinterestAdvertiser_Morning", "PinterestAdvertiser_Night", "TestTask"]:
        subprocess.run(["schtasks", "/delete", "/tn", old_tn, "/f"], capture_output=True)

    tasks_to_create = [
        ("PinterestAdvertiser_Morning_1", "08:00"),
        ("PinterestAdvertiser_Morning_2", "09:30"),
        ("PinterestAdvertiser_Evening_1", "19:00"),
        ("PinterestAdvertiser_Evening_2", "20:30"),
    ]

    for tn, st in tasks_to_create:
        cmd = [
            "schtasks", "/create", 
            "/tn", tn, 
            "/tr", f'"{python_exe}" "{SCRIPT_PATH}"',
            "/sc", "daily", 
            "/st", st, 
            "/f"
        ]
        print(f"\nRegistering Task '{tn}' ({st})...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✅ Task '{tn}' registered successfully!")
        else:
            print(f"❌ Failed to register Task '{tn}': {res.stderr}")
        
    print("\n==================================================")
    print("Task scheduling complete. Both tasks will trigger daily.")
    print("You can verify them in Windows 'Task Scheduler'.")
    print("==================================================")

if __name__ == "__main__":
    main()
