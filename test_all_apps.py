import os, subprocess, time, json, csv
from pathlib import Path

# Import the catalogue service (needs repo root on sys.path)
import sys
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.app_catalogue import catalogue_service

# Helper to check if a process is running (Windows tasklist)
def is_process_running(exe_name: str) -> bool:
    try:
        result = subprocess.run(f'tasklist /FI "IMAGENAME eq {exe_name}"', capture_output=True, text=True, shell=True)
        return exe_name.lower() in result.stdout.lower()
    except Exception:
        return False

# Define a basic safe‑skip list for sensitive apps (settings pages etc.)
SKIP_IDS = {
    "settings", "settings_system", "settings_update", "settings_network", "settings_bluetooth",
    "control", "taskmgr",  # task manager is safe but we may skip to avoid interference
}

reports = []
apps = catalogue_service.get_all_apps()
for app in apps:
    app_id = app.get("app_id")
    name = app.get("app_name")
    launch_type = app.get("launch_type")
    target = app.get("launch_target")
    exe = app.get("executable") or ""
    status = "NOT_TESTED"
    details = ""

    # Skip unsupported or sensitive entries
    if launch_type not in ("built_in", "executable", "uri"):
        status = "UNSUPPORTED"
        details = f"Launch type '{launch_type}' not supported for automated test."
    elif app_id in SKIP_IDS:
        status = "UNSUPPORTED"
        details = "App excluded from automated testing for safety."
    else:
        try:
            # Attempt launch
            if launch_type in ("built_in", "executable"):
                proc = subprocess.Popen(target, shell=True)
            elif launch_type == "uri":
                os.startfile(target)
            else:
                os.startfile(target)
            # Wait for a short period (configurable)
            timeout_seconds = 8
            start = time.time()
            while time.time() - start < timeout_seconds:
                if exe and is_process_running(exe):
                    status = "SUCCESS"
                    details = "Process detected after launch."
                    break
                time.sleep(1)
            else:
                # Timeout reached without detecting process
                if exe:
                    status = "TIMEOUT"
                    details = f"Process '{exe}' not observed within {timeout_seconds}s."
                else:
                    # No executable name to verify, assume success if no error
                    status = "SUCCESS"
                    details = "Launched (no process verification needed)."
        except Exception as e:
            status = "FAILED"
            details = f"Exception: {e}"

    reports.append({
        "app_id": app_id,
        "name": name,
        "launch_type": launch_type,
        "status": status,
        "details": details,
    })

# Write JSON report to artifact directory
artifact_dir = Path(os.getenv("AGY_ARTIFACTS", ""))
if not artifact_dir:
    artifact_dir = Path(__file__).resolve().parent / "artifact_reports"
artifact_dir.mkdir(parents=True, exist_ok=True)
json_path = artifact_dir / "application_test_report.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(reports, f, indent=2)

# Write CSV report
csv_path = artifact_dir / "application_test_report.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["app_id", "name", "launch_type", "status", "details"])
    writer.writeheader()
    writer.writerows(reports)

print(f"JSON report written to {json_path}")
print(f"CSV report written to {csv_path}")