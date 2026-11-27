"""
FastAPI application for AI Desktop Companion Backend.

Exposes endpoints for:
1. Health checks (/health)
2. Command planning via AI Engine (/plan)
3. Application catalogue inspection (/catalogue)
4. Task lifecycle management, orchestration, execution, approval, and cancellation (/tasks)
5. Voice input & voice transcript processing (/voice/input, /voice/transcript)
6. Unified task submission (/tasks/submit)
7. Granular task progress updates (/tasks/{task_id}/progress)
"""

import sys
from pathlib import Path

# Add project root to sys.path so api/main.py can be run directly or imported from any working directory
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, status

from ai_engine.planner.task_planner import TaskPlanner
from ai_engine.schemas.command_schema import CommandRequest
from api.catalogue_routes import router as catalogue_router
from api.orchestrator import DuplicateRequestError, VoiceServiceUnavailableError
from api.orchestrator_instance import orchestrator

planner = TaskPlanner()
from api.schemas import (
    AppCatalogueItem,
    BrowserProfile,
    CommandRunRequest,
    PlanRequest,
    PlanResponseModel,
    TaskApproveRequest,
    TaskCreate,
    TaskExecuteRequest,
    TaskProgressResponse,
    TaskResponse,
    TaskResultResponse,
    TaskStatusResponse,
    TaskSubmitRequest,
    TaskSubmitResponse,
    VoiceInputRequest,
    VoiceInputResponse,
    VoiceTranscriptRequest,
    VoiceTranscriptResponse,
)


app = FastAPI(
    title="AI Desktop Companion API",
    description="Backend orchestration service for AI Desktop Companion",
    version="1.1.0",
)


# Global in-memory storage for active tasks
tasks: Dict[str, Dict[str, Any]] = {}

from api.orchestrator_instance import orchestrator  # Shared orchestrator instance


# Register additional routers
app.include_router(catalogue_router)


# ---------------------------------------------------------------------------
# Browser Profiles Endpoint
# ---------------------------------------------------------------------------

def get_browser_profiles(browser: str = "chrome") -> List[dict]:
    """Wrapper to fetch browser profiles; facilitates testing.
    Imports the actual implementation from windows_automation.browser_profiles.
    """
    from windows_automation.browser_profiles import get_browser_profiles as _g
    return _g(browser)

def get_browser_profiles_endpoint():
    """Return discovered Chrome browser profiles."""
    try:
        profiles = get_browser_profiles()
        return profiles
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))



@app.get("/health")
def health_check():
    """Health check endpoint confirming API service readiness."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# AI Planning Endpoint (Preserved and Enhanced)
# ---------------------------------------------------------------------------

@app.post("/plan", response_model=PlanResponseModel)
def create_plan(request: PlanRequest):
    """
    Process natural language command using TaskPlanner and return structured plan.
    """
    command = CommandRequest(text=request.text)
    result = planner.process_command(command)

    return {
        "intent": result.intent,
        "status": result.status,
        "requires_clarification": result.requires_clarification,
        "clarification_question": result.clarification_question,
        "message": result.message,
        "steps": [
            {
                "step_id": step.step_id,
                "action": step.action,
                "target": step.target,
                "expected_outcome": step.expected_outcome,
                "parameters": getattr(step, "parameters", {}),
            }
            for step in result.steps
        ],
    }


# ---------------------------------------------------------------------------
# Application Catalogue Endpoints
# ---------------------------------------------------------------------------

@app.get("/catalogue", response_model=List[AppCatalogueItem])
def list_catalogue(search: Optional[str] = None, category: Optional[str] = None):
    """Return all installed applications from the catalogue.
    Optional query parameters:
    - `search`: case‑insensitive match against application name or any alias.
    - `category`: filter by the application's `category` field (if populated).
    """
    apps = orchestrator.get_catalogue()
    # Apply search filter
    if search:
        term = search.lower()
        apps = [a for a in apps if term in (a.get("app_name") or "").lower() or any(term in alias.lower() for alias in a.get("aliases", []))]
    # Apply category filter
    if category:
        cat = category.lower()
        apps = [a for a in apps if (a.get("category") or "").lower() == cat]
    return apps


@app.get("/catalogue/{app_id}", response_model=AppCatalogueItem)
def get_catalogue_app(app_id: str):
    """
    Retrieve application catalogue details for a specific application id or name.
    """
    app_item = orchestrator.get_app_by_id(app_id)
    if not app_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{app_id}' not found in catalogue.",
        )
    return app_item


# ---------------------------------------------------------------------------
# Voice Input & Voice Transcript Endpoints
# ---------------------------------------------------------------------------

@app.post("/voice/input", status_code=status.HTTP_202_ACCEPTED, response_model=VoiceInputResponse)
def submit_voice_input(request: VoiceInputRequest):
    """
    Voice Input API: Accepts raw or simulated voice audio data, checks service
    availability, and initializes listening/processing in the shared pipeline.
    """
    if request.simulate_service_down:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice service is currently unavailable.",
        )

    try:
        task = orchestrator.run_pipeline(
            command=None,
            input_type="voice",
            auto_execute=request.auto_execute,
            idempotency_key=request.idempotency_key,
            timeout_seconds=request.timeout_seconds,
            simulate_service_down=request.simulate_service_down,
        )
    except DuplicateRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except VoiceServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "message": task["message"],
        "input_type": "voice",
    }


@app.post("/voice/transcript", status_code=status.HTTP_201_CREATED, response_model=VoiceTranscriptResponse)
def submit_voice_transcript(request: VoiceTranscriptRequest):
    """
    Voice Transcript API: Accepts transcribed voice commands and executes them
    through the shared task execution pipeline.
    """
    try:
        task = orchestrator.run_pipeline(
            command=request.transcript,
            input_type="voice",
            auto_execute=request.auto_execute,
            idempotency_key=request.idempotency_key,
            timeout_seconds=request.timeout_seconds,
        )
    except DuplicateRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except VoiceServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "transcript": request.transcript,
        "message": task["message"],
        "input_type": "voice",
    }


# ---------------------------------------------------------------------------
# Browser Profiles Endpoint
def get_browser_profiles(browser: str = "chrome") -> List[dict]:
    """Wrapper to fetch browser profiles; facilitates testing.
    Imports the actual implementation from windows_automation.browser_profiles.
    """
    from windows_automation.browser_profiles import get_browser_profiles as _g
    return _g(browser)

def get_browser_profiles_endpoint():
    """Return discovered Chrome browser profiles."""
    try:
        profiles = get_browser_profiles()
        return profiles
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# Unified Task Submission Endpoint
# ---------------------------------------------------------------------------

@app.post("/tasks/submit", status_code=status.HTTP_201_CREATED, response_model=TaskSubmitResponse)
def submit_task(request: TaskSubmitRequest):
    """
    Unified Task Submission API: Single entrypoint for both text and voice requests.
    Both input types travel through the identical shared pipeline.
    """
    try:
        task = orchestrator.run_pipeline(
            command=request.command,
            input_type=request.input_type,
            auto_execute=request.auto_execute,
            idempotency_key=request.idempotency_key,
            timeout_seconds=request.timeout_seconds,
        )
    except DuplicateRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except VoiceServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return {
        "task_id": task["task_id"],
        "input_type": request.input_type,
        "command": request.command,
        "status": task["status"],
        "message": task["message"],
        "intent": task.get("intent"),
        "selected_application": task.get("selected_application"),
        "application_id": task.get("application_id"),
        "structured_request": task.get("structured_request"),
    }


# ---------------------------------------------------------------------------
# Task Progress Update API
# ---------------------------------------------------------------------------

@app.get("/tasks/{task_id}/progress", response_model=TaskProgressResponse)
def get_task_progress(task_id: str):
    """
    Task Progress Update API: Returns real-time execution progress percentage,
    current stage, and chronological progress timeline.
    """
    try:
        progress_data = orchestrator.get_progress(task_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )
    return progress_data


# ---------------------------------------------------------------------------
# Task Lifecycle Management Endpoints (Preserved & Enhanced)
# ---------------------------------------------------------------------------

@app.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
def create_task(task: TaskCreate):
    """
    Create a new task record. Supports optional command text and auto_execute.
    """
    created_task = orchestrator.create_task(
        title=task.title,
        description=task.description,
        command=task.command,
        auto_execute=task.auto_execute,
    )
    tasks[created_task["task_id"]] = created_task
    return created_task


@app.get("/tasks", response_model=List[TaskResponse])
def list_tasks(task_status: Optional[str] = Query(None, alias="status")):
    """
    List all tasks, optionally filtered by status.
    """
    return orchestrator.list_tasks(status=task_status)


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """
    Get current task status.
    """
    task = orchestrator.tasks.get(task_id) or tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    requires_approval = task.get("status") == "requires_approval"

    return {
        "task_id": task_id,
        "status": task["status"],
        "requires_approval": requires_approval,
        "message": task.get("message"),
    }


@app.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
def get_task_result(task_id: str):
    """
    Final Task Result API: Get detailed execution result, verification evidence,
    and audit details for a task.
    """
    task = orchestrator.tasks.get(task_id) or tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    task_status = task.get("status", "pending")
    result_data = task.get("result")
    message = task.get("message") or "Task has not completed yet"

    return {
        "task_id": task_id,
        "status": task_status,
        "result": result_data,
        "message": message,
        "error_code": task.get("error_code"),
        "error_message": task.get("error_message"),
        "verification": task.get("verification"),
        "audit": task.get("audit"),
        "duration_ms": task.get("duration_ms"),
        "intent": task.get("intent"),
        "selected_application": task.get("selected_application"),
        "application_id": task.get("application_id"),
        "structured_request": task.get("structured_request"),
        "completed_at": task.get("completed_at"),
    }


@app.post("/tasks/{task_id}/execute", response_model=TaskResultResponse)
def execute_task(task_id: str, request: Optional[TaskExecuteRequest] = None):
    """
    Execute a pending task through policy evaluation, automation dispatch, and verification.
    """
    task = orchestrator.tasks.get(task_id) or tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    req = request or TaskExecuteRequest()
    try:
        updated_task = orchestrator.execute_task(
            task_id=task_id,
            timeout_seconds=req.timeout_seconds,
        )
        tasks[task_id] = updated_task
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "task_id": task_id,
        "status": updated_task.get("status", "pending"),
        "result": updated_task.get("result"),
        "message": updated_task.get("message") or "",
        "error_code": updated_task.get("error_code"),
        "error_message": updated_task.get("error_message"),
        "verification": updated_task.get("verification"),
        "audit": updated_task.get("audit"),
        "duration_ms": updated_task.get("duration_ms"),
        "intent": updated_task.get("intent"),
        "selected_application": updated_task.get("selected_application"),
        "application_id": updated_task.get("application_id"),
        "structured_request": updated_task.get("structured_request"),
        "completed_at": updated_task.get("completed_at"),
    }


@app.post("/tasks/{task_id}/approve", response_model=TaskResultResponse)
def approve_task(task_id: str, request: Optional[TaskApproveRequest] = None):
    """
    Approve a task paused in 'requires_approval' status and resume execution.
    """
    task = orchestrator.tasks.get(task_id) or tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    req = request or TaskApproveRequest()
    try:
        updated_task = orchestrator.approve_task(
            task_id=task_id,
            approval_reference=req.approval_reference,
            timeout_seconds=req.timeout_seconds,
        )
        tasks[task_id] = updated_task
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "task_id": task_id,
        "status": updated_task.get("status", "pending"),
        "result": updated_task.get("result"),
        "message": updated_task.get("message") or "",
        "error_code": updated_task.get("error_code"),
        "error_message": updated_task.get("error_message"),
        "verification": updated_task.get("verification"),
        "audit": updated_task.get("audit"),
        "duration_ms": updated_task.get("duration_ms"),
        "intent": updated_task.get("intent"),
        "selected_application": updated_task.get("selected_application"),
        "application_id": updated_task.get("application_id"),
        "structured_request": updated_task.get("structured_request"),
        "completed_at": updated_task.get("completed_at"),
    }


@app.post("/tasks/{task_id}/cancel", response_model=TaskStatusResponse)
def cancel_task(task_id: str):
    """
    Cancel an ongoing or pending task, terminating running subprocesses safely.
    """
    task = orchestrator.tasks.get(task_id) or tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    try:
        updated_task = orchestrator.cancel_task(task_id)
        tasks[task_id] = updated_task
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "task_id": task_id,
        "status": updated_task["status"],
        "requires_approval": False,
        "message": updated_task.get("message") or "",
    }


@app.post("/tasks/run", response_model=TaskResultResponse)
def run_command(request: CommandRunRequest):
    """
    One-shot command dispatch endpoint: parses command, generates plan,
    evaluates policy, executes automation, and returns verified result.
    """
    task = orchestrator.run_command(
        text=request.text,
        auto_approve=request.auto_approve,
        timeout_seconds=request.timeout_seconds,
    )

    return {
        "task_id": task.get("task_id", ""),
        "status": task.get("status", "pending"),
        "result": task.get("result"),
        "message": task.get("message") or "",
        "error_code": task.get("error_code"),
        "error_message": task.get("error_message"),
        "verification": task.get("verification"),
        "audit": task.get("audit"),
        "duration_ms": task.get("duration_ms"),
        "intent": task.get("intent"),
        "selected_application": task.get("selected_application"),
        "application_id": task.get("application_id"),
        "structured_request": task.get("structured_request"),
        "completed_at": task.get("completed_at"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
