"""
FastAPI application for AI Desktop Companion Backend.

Exposes endpoints for:
1. Health checks (/health)
2. Command planning via AI Engine (/plan)
3. Application catalogue inspection (/catalogue)
4. Task lifecycle management, orchestration, execution, approval, and cancellation (/tasks)
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
from api.orchestrator import TaskOrchestrator
from api.schemas import (
    AppCatalogueItem,
    CommandRunRequest,
    PlanRequest,
    PlanResponseModel,
    TaskApproveRequest,
    TaskCreate,
    TaskExecuteRequest,
    TaskResponse,
    TaskResultResponse,
    TaskStatusResponse,
)

app = FastAPI(
    title="AI Desktop Companion API",
    description="Backend orchestration service for AI Desktop Companion",
    version="1.0.0",
)

# Global in-memory storage for active tasks
tasks: Dict[str, Dict[str, Any]] = {}

planner = TaskPlanner()
orchestrator = TaskOrchestrator(planner=planner, tasks=tasks)


# ---------------------------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------------------------

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
            }
            for step in result.steps
        ],
    }


# ---------------------------------------------------------------------------
# Application Catalogue Endpoints
# ---------------------------------------------------------------------------

@app.get("/catalogue", response_model=List[AppCatalogueItem])
def list_catalogue():
    """
    Return all installed applications from the catalogue with their allowlist status.
    """
    return orchestrator.get_catalogue()


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
# Task Lifecycle Management Endpoints
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
    return created_task


@app.get("/tasks", response_model=List[TaskResponse])
def list_tasks(task_status: Optional[str] = Query(None, alias="status")):
    """
    List all tasks, optionally filtered by status (pending, running, completed, failed, cancelled).
    """
    return orchestrator.list_tasks(status=task_status)


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """
    Get current task status.
    """
    task = tasks.get(task_id)
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
    Get detailed execution result, verification evidence, and audit details for a task.
    """
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    task_status = task.get("status", "pending")
    result_data = task.get("result")
    message = task.get("message", "Task has not completed yet")

    return {
        "task_id": task_id,
        "status": task_status,
        "result": result_data,
        "message": message,
        "error_code": task.get("error_code"),
        "verification": task.get("verification"),
        "audit": task.get("audit"),
        "duration_ms": task.get("duration_ms"),
    }


@app.post("/tasks/{task_id}/execute", response_model=TaskResultResponse)
def execute_task(task_id: str, request: Optional[TaskExecuteRequest] = None):
    """
    Execute a pending task through policy evaluation, automation dispatch, and verification.
    """
    task = tasks.get(task_id)
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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "task_id": task_id,
        "status": updated_task.get("status", "pending"),
        "result": updated_task.get("result"),
        "message": updated_task.get("message", ""),
        "error_code": updated_task.get("error_code"),
        "verification": updated_task.get("verification"),
        "audit": updated_task.get("audit"),
        "duration_ms": updated_task.get("duration_ms"),
    }


@app.post("/tasks/{task_id}/approve", response_model=TaskResultResponse)
def approve_task(task_id: str, request: Optional[TaskApproveRequest] = None):
    """
    Approve a task paused in 'requires_approval' status and resume execution.
    """
    task = tasks.get(task_id)
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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "task_id": task_id,
        "status": updated_task.get("status", "pending"),
        "result": updated_task.get("result"),
        "message": updated_task.get("message", ""),
        "error_code": updated_task.get("error_code"),
        "verification": updated_task.get("verification"),
        "audit": updated_task.get("audit"),
        "duration_ms": updated_task.get("duration_ms"),
    }


@app.post("/tasks/{task_id}/cancel", response_model=TaskStatusResponse)
def cancel_task(task_id: str):
    """
    Cancel an ongoing or pending task, terminating running subprocesses safely.
    """
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    try:
        updated_task = orchestrator.cancel_task(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "task_id": task_id,
        "status": updated_task["status"],
        "requires_approval": False,
        "message": updated_task.get("message"),
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
        "message": task.get("message", ""),
        "error_code": task.get("error_code"),
        "verification": task.get("verification"),
        "audit": task.get("audit"),
        "duration_ms": task.get("duration_ms"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

