from api.orchestrator_instance import orchestrator as global_orchestrator
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Body
import subprocess, os, time
from api.schemas import RefreshResponse, AppCapability, LaunchTestResult, TaskResultResponse
from api.app_catalogue import catalogue_service as _catalogue_service
from api.orchestrator import TaskOrchestrator
from api.capability_registry import registry

router = APIRouter(prefix="/catalogue", tags=["Catalogue"])

# Settings navigation mapping
SETTINGS_URI_MAP = {
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network-wifi",
    "wireless": "ms-settings:network-wifi",
    "personalization": "ms-settings:personalization",
    "windows update": "ms-settings:windowsupdate",
    "update": "ms-settings:windowsupdate",
    "installed apps": "ms-settings:appsfeatures",
    "apps": "ms-settings:appsfeatures",
    "privacy": "ms-settings:privacy",
}

# Add imports for the new endpoint (if not already present)
import subprocess, os, time
from fastapi import Body

@router.get("/refresh", response_model=RefreshResponse)
def refresh_catalogue():
    """Force a re‑run of the Windows discovery logic and return a status.
    The underlying service caches the result; this clears and rebuilds it.
    """
    try:
        _catalogue_service.refresh()
        return {"status": "ok", "refreshed_at": _catalogue_service.last_refresh_iso()}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

@router.post("/launch", response_model=LaunchTestResult)
def launch_app(name: str = Body(..., embed=True)):
    """Launch an application by name or alias.
    - Resolves dynamically against the live catalogue.
    - Returns 409 if multiple matches (with choices).
    - Executes appropriate launch method and verifies the process.
    """
    term = name.lower()
    apps = _catalogue_service.get_all_apps()
    matches = [a for a in apps if term == a.get("app_name", "").lower() or term in [al.lower() for al in a.get("aliases", [])]]
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No application matches '{name}'.")
    if len(matches) > 1:
        choices = [m.get("app_name") for m in matches]
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": f"Multiple applications match '{name}'.", "choices": choices})
    app = matches[0]
    launch_type = app.get("launch_type")
    target = app.get("launch_target")
    try:
        if launch_type in ("built_in", "executable"):
            proc = subprocess.Popen(target, shell=True)
        elif launch_type == "uri":
            os.startfile(target)
        else:
            os.startfile(target)
        time.sleep(2)
        exe_name = app.get("executable")
        if exe_name:
            verify_cmd = f'tasklist /FI "IMAGENAME eq {exe_name}"'
            result = subprocess.run(verify_cmd, capture_output=True, text=True, shell=True)
            if exe_name.lower() in result.stdout.lower():
                return {"app_id": app.get("app_id"), "status": "SUCCESS", "details": f"Launched {app.get('app_name')} and process found."}
        return {"app_id": app.get("app_id"), "status": "FAILED", "details": f"Launched {app.get('app_name')} but process not detected."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{app_id}/capabilities", response_model=AppCapability)
def get_capabilities(app_id: str):
    """Return the list of action names the backend knows how to perform for *app_id*.
    The capability registry is the single source of truth.
    """
    caps = registry.list_capabilities(app_id)
    if not caps:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No capabilities registered for '{app_id}'.")
    return {"app_id": app_id, "capabilities": caps}

@router.get("/{app_id}/test", response_model=LaunchTestResult)
def test_launch(app_id: str):
    """Perform a safe launch‑test for the given application.
    The orchestrator knows how to invoke an adapter in a dry‑run mode.
    """
    orchestrator = TaskOrchestrator()
    try:
        result = global_orchestrator.test_launch(app_id)
        return result
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
