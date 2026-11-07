"""
Backend API Server for AI Desktop Companion.
Connects:
1. AI Engine (TaskPlanner)
2. Windows Automation (ApplicationCatalogue, WindowsAutomationAdapter, WindowsWindowVerifier)
3. Frontend Desktop UI (React / Chrome Browser mode)
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_engine.planner.task_planner import TaskPlanner
from ai_engine.schemas.command_schema import CommandRequest
from windows_automation.adapter import WindowsAutomationAdapter
from windows_automation.discovery import ApplicationDiscoverer
from windows_automation.catalogue import ApplicationCatalogue

app = FastAPI(
    title="AI Desktop Companion API",
    description="Bridge API connecting AI Planning, Windows Automation, and Web Frontend",
    version="1.0.0"
)

# Enable CORS for browser frontends (Vite on 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singletons
discoverer = ApplicationDiscoverer()
catalogue = ApplicationCatalogue()
adapter = WindowsAutomationAdapter(catalogue=catalogue, discoverer=discoverer, auto_discover=True)
planner = TaskPlanner()


class CommandInput(BaseModel):
    command: Optional[str] = None
    text: Optional[str] = None

    def get_query(self) -> str:
        return (self.command or self.text or "").strip()


class LaunchInput(BaseModel):
    target: str


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "AI Desktop Companion API",
        "catalogue_count": catalogue.count(),
        "mode": "browser_companion"
    }


@app.get("/api/apps")
def get_apps():
    """Return all discovered applications available for safe launching."""
    records = catalogue.get_all()
    return {
        "count": len(records),
        "apps": [
            {
                "app_id": r.app_id,
                "display_name": r.display_name,
                "source": r.source,
                "launch_method": r.launch_method,
                "status": r.status,
            }
            for r in records
        ]
    }


@app.post("/api/command")
def process_command(payload: CommandInput):
    """
    Process a natural language user instruction:
    1. Parse with Booviha's TaskPlanner.
    2. If intent is open_application, resolve target with Logeshwaran's Windows Automation catalogue.
    3. Execute safe launch and truthfully verify window/process via Win32.
    4. Return structured response for UI and companion avatar state.
    """
    user_query = payload.get_query()
    if not user_query:
        return {
            "status": "clarification_required",
            "avatar_state": "Thinking",
            "reply": "Please enter a command or application name.",
            "intent": "unknown",
        }

    # 1. AI Planning
    req = CommandRequest(text=user_query)
    plan_resp = planner.process_command(req)

    # If general question or clarification
    if plan_resp.requires_clarification:
        return {
            "status": "clarification_required",
            "avatar_state": "Thinking",
            "reply": plan_resp.clarification_question,
            "intent": plan_resp.intent,
        }

    if plan_resp.intent == "general_question":
        return {
            "status": "completed",
            "avatar_state": "Idle",
            "reply": f"I heard your question: '{user_query}'. In this demo version, I specialize in planning and executing Windows desktop workflows and app launches.",
            "intent": plan_resp.intent,
        }

    # If open_application or action command
    target_app = None
    if plan_resp.entities and plan_resp.entities.application:
        target_app = plan_resp.entities.application
    else:
        # Fallback: extract target if planner marked unsupported or if user said 'launch/open X'
        lowered = user_query.lower()
        for prefix in ("open ", "launch ", "start "):
            if lowered.startswith(prefix):
                target_app = user_query[len(prefix):].strip()
                break

    if not target_app:
        target_app = user_query

    # Check if target resolves in our safe catalogue
    resolution = catalogue.resolve(target_app)
    if resolution.status == "ambiguous":
        return {
            "status": "ambiguous",
            "avatar_state": "Warning",
            "reply": f"Multiple applications matched '{target_app}': {', '.join(resolution.candidates)}. Please specify.",
            "intent": "open_application",
        }

    if resolution.status == "unresolved":
        return {
            "status": "unsupported",
            "avatar_state": "Warning",
            "reply": f"Application '{target_app}' was not found in installed applications or safe system catalogue.",
            "intent": "open_application",
        }

    # Execute launch via WindowsAutomationAdapter
    exec_result = adapter.execute_application_launch(target_app)

    if exec_result.status == "completed":
        details = (exec_result.verification.details if exec_result.verification else {}) or {}
        pid = details.get("window_pid") or details.get("process_id")
        win_title = details.get("window_title")
        pid_info = f" (PID: {pid})" if pid else ""
        window_info = f", Window: \"{win_title}\"" if win_title else ""
        verification_status = exec_result.verification_status or "launch_verified"

        reply_msg = f"Successfully launched and verified {resolution.matched_record.display_name}{pid_info}{window_info}."
        if verification_status == "inconclusive":
            reply_msg = f"Application {resolution.matched_record.display_name} launched; verification inconclusive."

        return {
            "status": "success",
            "avatar_state": "Success",
            "reply": reply_msg,
            "intent": "open_application",
            "app": resolution.matched_record.display_name,
            "verification_status": verification_status,
            "evidence": details,
        }
    else:
        return {
            "status": "failed",
            "avatar_state": "Error",
            "reply": f"Failed to launch '{target_app}': {exec_result.error_message or exec_result.error_code or 'Execution failed'}",
            "intent": "open_application",
            "error_code": exec_result.error_code,
            "error_message": exec_result.error_message,
        }


@app.get("/api/launch-app")
@app.post("/api/launch-app")
def launch_app_endpoint(appId: Optional[str] = None, target: Optional[str] = None):
    """
    Endpoint consumed by Doraemon UI in browser preview mode.
    Accepts appId query param or target and returns IpcLaunchResult format.
    """
    query_target = appId or target or ""
    if not query_target:
        return {
            "success": False,
            "verified": False,
            "displayName": "",
            "mode": "not-found",
            "error": "No application identifier provided.",
        }

    resolution = catalogue.resolve(query_target)
    if resolution.status == "ambiguous":
        cand_names = [c.display_name for c in resolution.candidates]
        return {
            "success": False,
            "verified": False,
            "displayName": query_target,
            "mode": "not-allowed",
            "error": f"Multiple applications matched '{query_target}': {', '.join(cand_names)}. Please specify.",
        }

    if resolution.status == "unresolved":
        return {
            "success": False,
            "verified": False,
            "displayName": query_target,
            "mode": "not-found",
            "error": f"No installed application found matching '{query_target}'.",
        }

    exec_result = adapter.execute_application_launch(query_target)
    if exec_result.status == "completed":
        details = (exec_result.verification.details if exec_result.verification else {}) or {}
        pid = details.get("window_pid") or details.get("process_id")
        win_title = details.get("window_title")
        pid_info = f" (PID: {pid})" if pid else ""
        return {
            "success": True,
            "verified": exec_result.verification_status == "launch_verified",
            "displayName": resolution.matched_record.display_name,
            "mode": "real",
            "message": f"Successfully launched and verified {resolution.matched_record.display_name}{pid_info}.",
            "error": None,
        }
    else:
        return {
            "success": False,
            "verified": False,
            "displayName": resolution.matched_record.display_name if resolution.matched_record else query_target,
            "mode": "real",
            "error": exec_result.error_message or exec_result.error_code or "Application launch failed.",
        }


@app.post("/api/launch")
def direct_launch(payload: LaunchInput):
    """Direct application launch endpoint."""
    exec_result = adapter.execute_application_launch(payload.target)
    return exec_result.to_dict()


# Serve static build from desktop/dist if present
dist_path = REPO_ROOT / "desktop" / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static_dist")
