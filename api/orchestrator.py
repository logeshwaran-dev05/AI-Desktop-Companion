"""
Task Orchestrator, State Machine, and Permission Evaluator for Backend API.

Implements the core backend orchestration layer bridging:
1. AI Engine (TaskPlanner & Application Catalogue)
2. Windows Automation (WindowsAutomationAdapter, Policy, and Schemas)
3. API / Client Task Lifecycle State Machine
4. Common Execution Pipeline (Voice & Text)
"""

import sys
from pathlib import Path

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ai_engine.catalogue import get_installed_apps
from ai_engine.planner.task_planner import TaskPlanner
from ai_engine.schemas.command_schema import CommandRequest, PlanStep
from windows_automation.adapter import WindowsAutomationAdapter
from windows_automation.schemas import AuthorizationDecision, ExecutionResult


def current_iso_timestamp() -> str:
    """Return ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Custom Backend Exceptions
# ---------------------------------------------------------------------------

class BackendError(Exception):
    """Base backend exception with error code."""
    def __init__(self, message: str, error_code: str = "ERR_BACKEND"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class DuplicateRequestError(BackendError):
    def __init__(self, message: str = "Duplicate request detected."):
        super().__init__(message, error_code="ERR_DUPLICATE_REQUEST")


class VoiceServiceUnavailableError(BackendError):
    def __init__(self, message: str = "Voice service is currently unavailable."):
        super().__init__(message, error_code="ERR_VOICE_SERVICE_UNAVAILABLE")


class UnknownApplicationError(BackendError):
    def __init__(self, message: str = "Target application is not recognized."):
        super().__init__(message, error_code="ERR_UNKNOWN_APPLICATION")


class InvalidIntentError(BackendError):
    def __init__(self, message: str = "Planner could not extract an actionable intent."):
        super().__init__(message, error_code="ERR_INVALID_INTENT")


# ---------------------------------------------------------------------------
# Task State Machine
# ---------------------------------------------------------------------------

class TaskStateMachine:
    """
    Deterministic Task State Machine.
    
    States:
    - listening: Waiting for / receiving voice input audio.
    - processing: Transcribing audio or parsing intent via AI Engine.
    - matching: Resolving application identifiers against installed catalogue.
    - requires_approval: Action requires explicit human confirmation.
    - launching: Dispatched to Windows Automation and polling Win32 verification.
    - launched: Action executed and positively verified by Windows Automation verifier.
    - failed: Validation, policy check, launch, or verification failed.
    - cancelled: Execution aborted by user request or timeout.
    - pending / running / completed: Preserved legacy states for full backward compatibility.
    """

    VALID_TRANSITIONS = {
        # Structured task states (today's specification)
        "listening": {"processing", "failed", "cancelled"},
        "processing": {"matching", "failed", "cancelled"},
        "matching": {"launching", "requires_approval", "failed", "cancelled"},
        "requires_approval": {"launching", "running", "failed", "cancelled"},
        "launching": {"launched", "completed", "failed", "cancelled"},
        "launched": set(),  # Terminal state
        "failed": set(),     # Terminal state
        "cancelled": set(),  # Terminal state

        # Preserved states for backward compatibility with existing tests
        "pending": {"running", "requires_approval", "cancelled", "failed", "processing", "matching", "launching"},
        "running": {"completed", "launched", "failed", "cancelled"},
        "completed": set(),  # Terminal state
    }

    TERMINAL_STATES = {"completed", "launched", "failed", "cancelled"}

    PROGRESS_MAP = {
        "pending": 0,
        "listening": 10,
        "processing": 30,
        "matching": 50,
        "requires_approval": 50,
        "launching": 75,
        "running": 75,
        "launched": 100,
        "completed": 100,
        "failed": 100,
        "cancelled": 100,
    }

    STAGE_DESCRIPTIONS = {
        "listening": "Listening for voice input audio",
        "processing": "Processing input and extracting intent via AI Planner",
        "matching": "Matching and resolving application identifiers in catalogue",
        "requires_approval": "Awaiting user approval before launching",
        "launching": "Dispatching launch to Windows Automation",
        "running": "Automation in progress",
        "launched": "Application launched and verified on desktop",
        "completed": "Task completed and verified",
        "failed": "Task execution failed",
        "cancelled": "Task execution was cancelled",
        "pending": "Task pending evaluation",
    }

    @classmethod
    def can_transition(cls, current_status: str, next_status: str) -> bool:
        """Check whether a state transition is permitted."""
        allowed = cls.VALID_TRANSITIONS.get(current_status, set())
        return next_status in allowed

    @classmethod
    def transition(cls, task: Dict[str, Any], next_status: str, message: Optional[str] = None) -> None:
        """
        Transition task to next_status, appending a truthful progress timeline entry.
        Raises ValueError if the transition is invalid.
        """
        current_status = task.get("status", "pending")
        if current_status == next_status:
            return

        if not cls.can_transition(current_status, next_status):
            raise ValueError(
                f"Invalid task state transition from '{current_status}' to '{next_status}'. "
                f"Allowed target states: {sorted(list(cls.VALID_TRANSITIONS.get(current_status, set())))}"
            )

        task["status"] = next_status
        if message:
            task["message"] = message

        # Maintain progress timeline
        if "timeline" not in task:
            task["timeline"] = []
        task["timeline"].append({
            "timestamp": current_iso_timestamp(),
            "state": next_status,
            "message": message or f"Transitioned to {next_status}",
        })


# ---------------------------------------------------------------------------
# Application Resolver
# ---------------------------------------------------------------------------

class ApplicationResolver:
    """
    Resolves application identifiers and aliases against the installed application catalogue
    and the explicit allowlist.
    """

    ALIASES = {
        "notepad": "notepad",
        "calc": "calculator",
        "calculator": "calculator",
        "chrome": "chrome",
        "google chrome": "chrome",
        "code": "vscode",
        "vs code": "vscode",
        "visual studio code": "vscode",
        "edge": "edge",
        "microsoft edge": "edge",
        "paint": "paint",
    }

    def __init__(self, catalogue: Optional[List[Dict[str, Any]]] = None):
        self.catalogue = catalogue if catalogue is not None else get_installed_apps()

    def resolve(self, target: str) -> Optional[Dict[str, Any]]:
        """
        Resolve an application name or alias to its installed catalogue entry.
        Returns the application dict or None if unknown.
        """
        clean = (target or "").strip().lower()
        if not clean:
            return None

        # 1. Direct check against catalogue by app_name, app_id, or executable
        for app in self.catalogue:
            if clean in (
                app["app_name"].lower(),
                app["app_id"].lower(),
                app["executable"].lower(),
                app["app_name"].replace(" ", "").lower(),
            ):
                return app

        # 2. Check aliases
        if clean in self.ALIASES:
            aliased_id = self.ALIASES[clean]
            for app in self.catalogue:
                if app["app_id"] == aliased_id:
                    return app

        # 3. Known allowlisted fallback for Notepad
        if clean in ("notepad", "notepad.exe"):
            return {
                "app_name": "Notepad",
                "app_id": "notepad",
                "executable": "notepad.exe",
            }

        return None


# ---------------------------------------------------------------------------
# Permission Evaluator
# ---------------------------------------------------------------------------

class PermissionEvaluator:
    """
    Evaluates actions against security policies before dispatching to Windows Automation.
    Never invents approvals. Explicitly identifies allowlisted applications vs. actions
    requiring user authorization.
    """

    DIRECT_ALLOWLIST = {"notepad", "notepad.exe"}

    def evaluate(self, task_id: str, action_name: str, target: str) -> AuthorizationDecision:
        """
        Evaluate security permission for a specific plan step.
        Returns an AuthorizationDecision instance.
        """
        decision_id = f"dec_{uuid4()}"
        clean_action = (action_name or "").strip()
        clean_target = (target or "").strip().lower()

        # Milestone 1: Only "open_application" is supported
        if clean_action != "open_application":
            return AuthorizationDecision(
                decision_id=decision_id,
                permission_status="denied",
                requires_user_approval=False,
                reason=f"Action '{action_name}' is not permitted by policy.",
            )

        if not clean_target:
            return AuthorizationDecision(
                decision_id=decision_id,
                permission_status="denied",
                requires_user_approval=False,
                reason="Target cannot be empty.",
            )

        # 1. Milestone 1 Allowlist Check: Direct launch granted for Notepad
        if clean_target in self.DIRECT_ALLOWLIST:
            return AuthorizationDecision(
                decision_id=decision_id,
                permission_status="granted",
                requires_user_approval=False,
                approval_reference="user_auto_allowlist_v1",
                reason=f"Application '{target}' is explicitly allowlisted for direct launch.",
            )

        # 2. Installed Catalogue Check: Apps in catalogue require explicit approval for Milestone 1 launch
        installed = get_installed_apps()
        catalogue_matches = [
            app for app in installed
            if clean_target in (
                app["app_name"].lower(),
                app["app_id"].lower(),
                app["executable"].lower(),
            )
        ]

        if catalogue_matches:
            matched_app = catalogue_matches[0]["app_name"]
            return AuthorizationDecision(
                decision_id=decision_id,
                permission_status="requires_approval",
                requires_user_approval=True,
                approval_reference=None,
                reason=f"Application '{matched_app}' is installed in catalogue but requires explicit user approval before launching.",
            )

        # 3. Not in allowlist and not in catalogue -> Denied
        return AuthorizationDecision(
            decision_id=decision_id,
            permission_status="denied",
            requires_user_approval=False,
            reason=f"Target '{target}' is not in the explicit application allowlist or installed catalogue.",
        )


# ---------------------------------------------------------------------------
# Central Task Orchestrator & Common Execution Pipeline
# ---------------------------------------------------------------------------

class TaskOrchestrator:
    """
    Central orchestration service coordinating TaskPlanner, Application Catalogue,
    PermissionEvaluator, and WindowsAutomationAdapter through a common execution pipeline.
    """

    def __init__(
        self,
        planner: Optional[TaskPlanner] = None,
        adapter: Optional[WindowsAutomationAdapter] = None,
        tasks: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.planner = planner or TaskPlanner()
        self.adapter = adapter or WindowsAutomationAdapter()
        self.tasks: Dict[str, Dict[str, Any]] = tasks if tasks is not None else {}
        self.permission_evaluator = PermissionEvaluator()
        self.resolver = ApplicationResolver()
        self.state_machine = TaskStateMachine()
        # In-memory register mapping idempotency_key -> task_id
        self._idempotency_registry: Dict[str, str] = {}

    # -----------------------------------------------------------------------
    # Application Catalogue
    # -----------------------------------------------------------------------

    def get_catalogue(self) -> List[Dict[str, Any]]:
        """Return the installed application catalogue annotated with allowlist status."""
        apps = get_installed_apps()
        results = []
        for app in apps:
            app_id = app.get("app_id", "").lower()
            executable = app.get("executable", "").lower()
            is_allowlisted = (
                app_id in self.permission_evaluator.DIRECT_ALLOWLIST
                or executable in self.permission_evaluator.DIRECT_ALLOWLIST
            )
            results.append({
                "app_name": app.get("app_name"),
                "app_id": app.get("app_id"),
                "executable": app.get("executable"),
                "allowlisted": is_allowlisted,
            })
        return results

    def get_app_by_id(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Look up application details by app_id or app_name."""
        catalogue = self.get_catalogue()
        clean = (app_id or "").strip().lower()
        for item in catalogue:
            if clean in (item["app_id"].lower(), item["app_name"].lower()):
                return item
        return None

    # -----------------------------------------------------------------------
    # Progress & Status Inspection
    # -----------------------------------------------------------------------

    def get_progress(self, task_id: str) -> Dict[str, Any]:
        """Return granular task execution progress, timeline, and percentage."""
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        current_status = task.get("status", "pending")
        progress_pct = self.state_machine.PROGRESS_MAP.get(current_status, 0)
        current_stage = self.state_machine.STAGE_DESCRIPTIONS.get(current_status, current_status)

        return {
            "task_id": task_id,
            "status": current_status,
            "progress_percent": progress_pct,
            "current_stage": current_stage,
            "timeline": task.get("timeline", []),
            "message": task.get("message", ""),
        }

    # -----------------------------------------------------------------------
    # Common Execution Pipeline (Voice & Text)
    # -----------------------------------------------------------------------

    def run_pipeline(
        self,
        command: Optional[str] = None,
        input_type: str = "text",
        auto_execute: bool = True,
        idempotency_key: Optional[str] = None,
        timeout_seconds: float = 10.0,
        simulate_service_down: bool = False,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Common execution pipeline for all user requests (voice and text).
        
        Flow:
        User Input -> Voice/Text Processing -> AI Intent -> Application Matching ->
        Windows Automation -> Verification -> Task Status (launched / failed)
        """
        # Step 1: Idempotency Gate
        if idempotency_key:
            if idempotency_key in self._idempotency_registry:
                existing_id = self._idempotency_registry[idempotency_key]
                raise DuplicateRequestError(
                    f"Duplicate request detected for idempotency key '{idempotency_key}'. Task ID: '{existing_id}'."
                )

        # Step 2: Task Record Initialization
        task_id = task_id or f"task_{uuid4()}"
        initial_status = "listening" if (input_type == "voice" and not command) else "processing"

        task = {
            "task_id": task_id,
            "title": command or ("Voice Command" if input_type == "voice" else "Task"),
            "description": "",
            "command": command,
            "input_type": input_type,
            "idempotency_key": idempotency_key,
            "intent": None,
            "status": initial_status,
            "steps": [],
            "current_step_index": 0,
            "active_action_id": None,
            "authorization": None,
            "result": None,
            "error_code": None,
            "error_message": None,
            "verification": None,
            "audit": None,
            "duration_ms": 0,
            "message": f"Task initiated via {input_type}.",
            "timeline": [{
                "timestamp": current_iso_timestamp(),
                "state": initial_status,
                "message": f"Task initialized in {initial_status} state.",
            }],
            "created_at": current_iso_timestamp(),
            "started_at": current_iso_timestamp(),
            "completed_at": None,
        }

        self.tasks[task_id] = task
        if idempotency_key:
            self._idempotency_registry[idempotency_key] = task_id

        # Step 3: Handle Voice Service Availability Check
        if input_type == "voice" and simulate_service_down:
            self.state_machine.transition(task, "failed", "Voice service is currently unavailable.")
            task["error_code"] = "ERR_VOICE_SERVICE_UNAVAILABLE"
            task["error_message"] = "Voice service is offline or unreachable."
            task["completed_at"] = current_iso_timestamp()
            return task

        # If initially listening, advance to processing
        if task["status"] == "listening":
            self.state_machine.transition(task, "processing", "Voice input captured. Transcribing and extracting intent.")

        # Step 4: AI Intent Extraction
        if not command or not command.strip():
            self.state_machine.transition(task, "failed", "Command text cannot be empty.")
            task["error_code"] = "ERR_INVALID_INTENT"
            task["error_message"] = "Command text cannot be empty."
            task["completed_at"] = current_iso_timestamp()
            return task

        plan_response = self.planner.process_command(CommandRequest(text=command, input_type=input_type))
        task["intent"] = plan_response.intent

        # Handle unsupported, clarification, or missing steps
        if plan_response.status in ("clarification_required", "unsupported") or not plan_response.steps:
            # Check if an unknown application was referenced in an open/launch command
            clean_cmd = command.lower().strip()
            is_launch_command = any(
                clean_cmd.startswith(prefix)
                for prefix in ("open", "launch", "start", "please open", "can you open", "could you open", "would you open")
            )
            app_entity = getattr(plan_response.entities, "application", None)

            if is_launch_command:
                target_candidate = app_entity or (command.split()[-1] if len(command.split()) > 1 else "")
                resolved_app = self.resolver.resolve(target_candidate)
                if not resolved_app and target_candidate and target_candidate.lower() not in ("notepad", "notepad.exe"):
                    self.state_machine.transition(task, "failed", f"Unknown application: '{target_candidate}' is not recognized.")
                    task["error_code"] = "ERR_UNKNOWN_APPLICATION"
                    task["error_message"] = f"Application '{target_candidate}' not found in installed catalogue."
                    task["completed_at"] = current_iso_timestamp()
                    return task

            self.state_machine.transition(task, "failed", plan_response.message or "Invalid or unsupported command intent.")
            task["error_code"] = "ERR_INVALID_INTENT"
            task["error_message"] = plan_response.message or "Planner could not extract an actionable intent."
            task["completed_at"] = current_iso_timestamp()
            return task

        task["steps"] = [
            {
                "step_id": step.step_id,
                "action": step.action,
                "target": step.target,
                "depends_on": getattr(step, "depends_on", []),
                "expected_outcome": step.expected_outcome,
            }
            for step in plan_response.steps
        ]

        # Step 5: Application Identifier Resolution & Matching
        self.state_machine.transition(task, "matching", "Resolving target application against installed catalogue.")
        step_data = task["steps"][0]
        action_name = step_data.get("action", "")
        raw_target = step_data.get("target", "")

        resolved_app = self.resolver.resolve(raw_target)
        if not resolved_app and raw_target.lower() not in ("notepad", "notepad.exe"):
            self.state_machine.transition(task, "failed", f"Unknown application: '{raw_target}' is not recognized.")
            task["error_code"] = "ERR_UNKNOWN_APPLICATION"
            task["error_message"] = f"Application '{raw_target}' not found in installed catalogue."
            task["completed_at"] = current_iso_timestamp()
            return task

        canonical_target = resolved_app["app_name"] if resolved_app else raw_target
        step_data["target"] = canonical_target

        if not auto_execute:
            return task

        # Step 6: Security & Permission Check
        auth = self.permission_evaluator.evaluate(task_id, action_name, canonical_target)
        task["authorization"] = auth.to_dict()

        if auth.permission_status == "requires_approval":
            self.state_machine.transition(task, "requires_approval", auth.reason)
            return task

        if auth.permission_status == "denied":
            self.state_machine.transition(task, "failed", auth.reason)
            task["error_code"] = "ERR_PERMISSION_DENIED"
            task["error_message"] = auth.reason
            task["completed_at"] = current_iso_timestamp()
            return task

        # Step 7: Windows Automation Dispatch (launching)
        self.state_machine.transition(
            task, "launching", f"Dispatching '{action_name}' on '{canonical_target}' to Windows Automation."
        )

        plan_step = PlanStep(
            step_id=step_data.get("step_id", 1),
            action=action_name,
            target=canonical_target,
            depends_on=step_data.get("depends_on", []),
            expected_outcome=step_data.get("expected_outcome", ""),
        )

        exec_result: ExecutionResult = self.adapter.execute_plan_step(
            step=plan_step,
            task_id=task_id,
            authorization=auth,
            timeout_seconds=timeout_seconds,
        )

        task["active_action_id"] = exec_result.action_id
        task["duration_ms"] = exec_result.duration_ms
        task["completed_at"] = exec_result.completed_at
        task["result"] = exec_result.to_dict()
        task["verification"] = exec_result.verification.to_dict() if exec_result.verification else None
        task["audit"] = exec_result.audit.to_dict() if exec_result.audit else None

        # Step 8: Truthful Verification & False Success Prevention
        is_verified = bool(exec_result.verification and exec_result.verification.verified)

        if exec_result.status == "completed" and is_verified:
            # Confirmed success!
            self.state_machine.transition(
                task, "launched", f"Application '{canonical_target}' launched and verified successfully."
            )
            task["active_action_id"] = None
            task["message"] = f"Application '{canonical_target}' launched and verified successfully."

        elif exec_result.status == "cancelled":
            self.state_machine.transition(task, "cancelled", "Action was cancelled.")
            task["active_action_id"] = None
            task["error_code"] = exec_result.error_code or "ERR_CANCELLED"
            task["error_message"] = exec_result.error_message or "Action was cancelled."

        elif exec_result.error_code == "ERR_TIMEOUT":
            self.state_machine.transition(task, "failed", f"Timeout waiting for '{canonical_target}' window readiness.")
            task["active_action_id"] = None
            task["error_code"] = "ERR_TIMEOUT"
            task["error_message"] = exec_result.error_message or "Execution timed out."

        elif not is_verified:
            # False success prevention: Never report launched without verified Win32 window evidence
            self.state_machine.transition(
                task, "failed", f"Verification failed: '{canonical_target}' window was not verified on desktop."
            )
            task["active_action_id"] = None
            task["error_code"] = exec_result.error_code or "ERR_VERIFICATION_FAILED"
            task["error_message"] = exec_result.error_message or "Window readiness could not be verified."

        else:
            self.state_machine.transition(task, "failed", f"Automation execution failed: {exec_result.error_message}")
            task["active_action_id"] = None
            task["error_code"] = exec_result.error_code or "ERR_LAUNCH_FAILED"
            task["error_message"] = exec_result.error_message or "Process launch failed."

        return task

    # -----------------------------------------------------------------------
    # Task Lifecycle Management (Preserved for Backward Compatibility)
    # -----------------------------------------------------------------------

    def create_task(
        self,
        title: str,
        description: str = "",
        command: Optional[str] = None,
        auto_execute: bool = False,
        timeout_seconds: float = 10.0,
    ) -> Dict[str, Any]:
        """Create a new task record. Preserved for backward compatibility."""
        task_id = f"task_{uuid4()}"
        steps: List[Dict[str, Any]] = []
        intent = None
        message = "Task initialized."
        initial_status = "pending"

        command_text = command
        if command_text:
            plan_response = self.planner.process_command(CommandRequest(text=command_text))
            intent = plan_response.intent
            message = plan_response.message

            steps = [
                {
                    "step_id": step.step_id,
                    "action": step.action,
                    "target": step.target,
                    "depends_on": getattr(step, "depends_on", []),
                    "expected_outcome": step.expected_outcome,
                }
                for step in plan_response.steps
            ]

            if plan_response.status == "clarification_required":
                message = plan_response.clarification_question or plan_response.message
            elif plan_response.status == "unsupported":
                initial_status = "failed"
                message = plan_response.message

        task = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "command": command_text,
            "intent": intent,
            "status": initial_status,
            "steps": steps,
            "current_step_index": 0,
            "active_action_id": None,
            "authorization": None,
            "result": None,
            "error_code": None,
            "error_message": None,
            "verification": None,
            "audit": None,
            "duration_ms": 0,
            "message": message,
            "timeline": [{
                "timestamp": current_iso_timestamp(),
                "state": initial_status,
                "message": message,
            }],
            "created_at": current_iso_timestamp(),
            "started_at": None,
            "completed_at": None,
        }

        self.tasks[task_id] = task

        if auto_execute and steps and initial_status == "pending":
            return self.execute_task(task_id, timeout_seconds=timeout_seconds)

        return task

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task record by task_id."""
        return self.tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List tasks, optionally filtered by status."""
        all_tasks = list(self.tasks.values())
        if status:
            return [t for t in all_tasks if t.get("status") == status]
        return all_tasks

    def execute_task(self, task_id: str, timeout_seconds: float = 10.0) -> Dict[str, Any]:
        """Execute pending plan steps through policy evaluation, dispatch, and verification."""
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        current_status = task["status"]

        if current_status in self.state_machine.TERMINAL_STATES:
            return task

        steps = task.get("steps", [])
        if not steps:
            if current_status == "pending":
                task["message"] = "No executable plan steps found for this task."
            return task

        for step_data in steps:
            action_name = step_data.get("action", "")
            target = step_data.get("target", "")
            step_id = step_data.get("step_id", 1)

            auth_dict = task.get("authorization")
            if auth_dict and auth_dict.get("permission_status") == "granted":
                auth = AuthorizationDecision.from_dict(auth_dict)
            else:
                auth = self.permission_evaluator.evaluate(task_id, action_name, target)
                task["authorization"] = auth.to_dict()

            if auth.permission_status == "requires_approval":
                self.state_machine.transition(task, "requires_approval", auth.reason)
                return task

            if auth.permission_status == "denied":
                self.state_machine.transition(task, "failed", auth.reason)
                task["error_code"] = "ERR_PERMISSION_DENIED"
                task["error_message"] = auth.reason
                task["completed_at"] = current_iso_timestamp()
                return task

            self.state_machine.transition(task, "running", f"Executing '{action_name}' on '{target}'.")
            task["started_at"] = task["started_at"] or current_iso_timestamp()

            plan_step = PlanStep(
                step_id=step_id,
                action=action_name,
                target=target,
                depends_on=step_data.get("depends_on", []),
                expected_outcome=step_data.get("expected_outcome", ""),
            )

            exec_result: ExecutionResult = self.adapter.execute_plan_step(
                step=plan_step,
                task_id=task_id,
                authorization=auth,
                timeout_seconds=timeout_seconds,
            )

            task["active_action_id"] = exec_result.action_id

            if exec_result.status == "completed":
                self.state_machine.transition(task, "completed", f"Action '{action_name}' completed and verified.")
                task["active_action_id"] = None
                task["result"] = exec_result.to_dict()
                task["verification"] = exec_result.verification.to_dict() if exec_result.verification else None
                task["audit"] = exec_result.audit.to_dict() if exec_result.audit else None
                task["duration_ms"] = exec_result.duration_ms
                task["completed_at"] = exec_result.completed_at
                task["message"] = f"Action '{action_name}' completed and verified successfully."

            elif exec_result.status == "cancelled":
                self.state_machine.transition(task, "cancelled", "Action was cancelled.")
                task["active_action_id"] = None
                task["error_code"] = exec_result.error_code or "ERR_CANCELLED"
                task["error_message"] = exec_result.error_message or "Action was cancelled."
                task["completed_at"] = exec_result.completed_at
                return task

            else:
                self.state_machine.transition(task, "failed", exec_result.error_message or "Execution failed.")
                task["active_action_id"] = None
                task["error_code"] = exec_result.error_code or "ERR_EXECUTION_FAILED"
                task["error_message"] = exec_result.error_message or "Action execution failed."
                task["duration_ms"] = exec_result.duration_ms
                task["completed_at"] = exec_result.completed_at
                return task

        return task

    def approve_task(
        self,
        task_id: str,
        approval_reference: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> Dict[str, Any]:
        """Approve a task paused in 'requires_approval' and resume execution."""
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        if task["status"] != "requires_approval":
            raise ValueError(
                f"Task '{task_id}' is in status '{task['status']}', expected 'requires_approval'."
            )

        ref = approval_reference or f"user_approval_{uuid4().hex[:8]}"
        auth_data = task.get("authorization") or {}
        auth_data["permission_status"] = "granted"
        auth_data["requires_user_approval"] = True
        auth_data["approval_reference"] = ref
        auth_data["reason"] = f"User explicitly approved action via reference: {ref}"
        task["authorization"] = auth_data

        # Resume execution through execute_task or run_pipeline
        return self.execute_task(task_id, timeout_seconds=timeout_seconds)

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a pending or running task and terminate active subprocesses."""
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        current_status = task["status"]

        if current_status in self.state_machine.TERMINAL_STATES:
            raise ValueError(f"Cannot cancel task in terminal state '{current_status}'.")

        active_action = task.get("active_action_id")
        if active_action:
            self.adapter.cancel_action(active_action)
            task["active_action_id"] = None

        self.state_machine.transition(task, "cancelled", "Task cancelled by user request.")
        task["completed_at"] = current_iso_timestamp()
        task["error_code"] = "ERR_CANCELLED"
        task["error_message"] = "Task was cancelled by user request."
        return task

    def run_command(
        self,
        text: str,
        auto_approve: bool = False,
        timeout_seconds: float = 10.0,
    ) -> Dict[str, Any]:
        """One-shot command dispatch preserved for backward compatibility."""
        task = self.create_task(
            title=text,
            command=text,
            auto_execute=False,
            timeout_seconds=timeout_seconds,
        )

        if task["status"] != "pending":
            return task

        if not task.get("steps"):
            task["status"] = "failed"
            task["message"] = "Planner did not generate any actionable steps."
            return task

        if auto_approve:
            step = task["steps"][0]
            auth = self.permission_evaluator.evaluate(
                task["task_id"], step.get("action", ""), step.get("target", "")
            )
            if auth.permission_status == "requires_approval":
                auth.permission_status = "granted"
                auth.approval_reference = f"user_auto_approve_{uuid4().hex[:8]}"
            task["authorization"] = auth.to_dict()

        return self.execute_task(task["task_id"], timeout_seconds=timeout_seconds)
