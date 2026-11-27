import os, subprocess, time, json, csv, sys
from pathlib import Path

# Ensure repository root is on sys.path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.app_catalogue import catalogue_service

def is_process_running(name: str) -> bool:
    """Check if a Windows process with the given executable name is running."""
    try:
        result = subprocess.run(f'tasklist /FI "IMAGENAME eq {name}"', capture_output=True, text=True, shell=True)
        return name.lower() in result.stdout.lower()
    except Exception:
        return False

# Applications we deliberately skip for safety (settings, task manager, etc.)
SKIP_IDS = {
    "settings", "settings_system", "settings_update", "settings_network", "settings_bluetooth",
    "control", "taskmgr", "mssettings", "winsettings", "windowssecurity",
}

def run_application_tests() -> list:
    """Discover all apps, attempt to launch each safely, and return a list of report dicts.
    The function is deliberately side‑effect free except for launching apps that are deemed safe.
    """
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
        start_ts = time.time()
        # Safety checks
        if launch_type not in ("built_in", "executable", "uri"):
            status = "UNSUPPORTED"
            details = f"Launch type '{launch_type}' not supported for automated testing."
        elif app_id in SKIP_IDS:
            status = "UNSUPPORTED"
            details = "App excluded from automated testing for safety."
        else:
            try:
                # Launch ---------------------------------------------------
                if launch_type in ("built_in", "executable"):
                    # Prefer os.startfile for .lnk or absolute paths
                    if os.path.isfile(target) or target.lower().endswith('.lnk'):
                        os.startfile(target)
                    else:
                        subprocess.Popen(target, shell=True)
                elif launch_type == "uri":
                    os.startfile(target)
                else:
                    os.startfile(target)
                # Wait & verify -------------------------------------------
                timeout = 10
                while time.time() - start_ts < timeout:
                    if exe and is_process_running(exe):
                        status = "SUCCESS"
                        details = "Process detected after launch."
                        break
                    time.sleep(0.5)
                else:
                    if exe:
                        status = "TIMEOUT"
                        details = f"Process '{exe}' not observed within {timeout}s."
                    else:
                        status = "SUCCESS"
                        details = "Launched (no executable verification)."
            except Exception as e:
                status = "FAILED"
                details = f"Exception during launch: {e}"
        duration = round(time.time() - start_ts, 2)
        reports.append({
            "app_id": app_id,
            "name": name,
            "category": app.get("category"),
            "launch_type": launch_type,
            "status": status,
            "details": details,
            "duration_seconds": duration,
            "launch_target": target,
            "executable": exe,
        })
    # Write artifacts ---------------------------------------------------
    artifact_dir = Path(__file__).resolve().parent / "artifact_reports"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifact_dir / "application_test_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)
    csv_path = artifact_dir / "application_test_report.csv"
    fieldnames = ["app_id", "name", "category", "launch_type", "status", "details", "duration_seconds", "launch_target", "executable"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reports)
    return reports
