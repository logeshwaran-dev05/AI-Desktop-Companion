from api.orchestrator_instance import orchestrator as global_orchestrator
from typing import List
from fastapi import APIRouter, HTTPException, status
from api.schemas import RefreshResponse, AppCapability, LaunchTestResult, TaskResultResponse
from api.app_catalogue import catalogue_service as _catalogue_service
from api.orchestrator import TaskOrchestrator
from api.capability_registry import registry

router = APIRouter(prefix="/catalogue", tags=["Catalogue"])

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
