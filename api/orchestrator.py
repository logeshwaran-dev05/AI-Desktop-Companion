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

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from ai_engine.catalogue import get_installed_apps
from ai_engine.planner.task_planner import TaskPlanner
from ai_engine.schemas.command_schema import CommandRequest, PlanStep, InputType
from api.app_catalogue import catalogue_service as _windows_catalogue
from api.schemas import StructuredActionRequest
from windows_automation.adapter import WindowsAutomationAdapter
from windows_automation.schemas import AuthorizationDecision, ExecutionResult
from api.task_repository import TaskRepository


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


class InvalidApplicationIdError(BackendError):
    def __init__(self, message: str = "Invalid application identifier."):
        super().__init__(message, error_code="ERR_INVALID_APPLICATION_ID")


class MissingParametersError(BackendError):
    def __init__(self, message: str = "Missing required parameters in request."):
        super().__init__(message, error_code="ERR_MISSING_PARAMETERS")


class AutomationUnavailableError(BackendError):
    def __init__(self, message: str = "Windows Automation service is unavailable."):
        super().__init__(message, error_code="ERR_AUTOMATION_UNAVAILABLE")


class AmbiguousCommandError(BackendError):
    def __init__(self, message: str = "Command is ambiguous and requires user clarification."):
        super().__init__(message, error_code="ERR_AMBIGUOUS_COMMAND")


class AutomationFailureError(BackendError):
    def __init__(self, message: str = "Windows Automation execution failed unexpectedly."):
        super().__init__(message, error_code="ERR_AUTOMATION_FAILURE")


# ---------------------------------------------------------------------------
# Task State Machine
# ---------------------------------------------------------------------------

class TaskStateMachine:
    """
    Deterministic Task State Machine.

    The project historically uses a legacy subset of states (pending/running/completed),
    while the broader Windows automation specification also expects aliases such as
    understanding, awaiting_approval, executing, verifying, and timed_out. These are
    normalized so the backend accepts both forms without changing the existing behavior.
    """

    STATUS_ALIASES: Dict[str, str] = {
        "understanding": "processing",
        "awaiting_approval": "requires_approval",
        "executing": "launching",
        "verifying": "launched",
        "timed_out": "failed",
        "waiting_approval": "requires_approval",
    }

    VALID_TRANSITIONS: Dict[str, Set[str]] = {
        # Structured task states (today's specification)
        "listening": {"processing", "failed", "cancelled"},
        "processing": {"matching", "failed", "cancelled"},
        "matching": {"launching", "requires_approval", "failed", "cancelled"},
        "requires_approval": {"launching", "running", "failed", "cancelled"},
        "launching": {"launched", "completed", "failed", "cancelled"},
        "launched": set(),  # Terminal state
        "failed": set(),     # Terminal state
        "cancelled": set(),  # Terminal state

        # Spec aliases that normalize to the canonical state names above
        "understanding": {"matching", "failed", "cancelled"},
        "awaiting_approval": {"launching", "running", "failed", "cancelled"},
        "executing": {"launched", "completed", "failed", "cancelled"},
        "verifying": {"completed", "failed", "cancelled"},
        "timed_out": set(),

        # Preserved states for backward compatibility with existing tests
        "pending": {"running", "requires_approval", "cancelled", "failed", "processing", "matching", "launching"},
        "running": {"completed", "launched", "failed", "cancelled"},
        "completed": set(),  # Terminal state
    }

    TERMINAL_STATES: Set[str] = {"completed", "launched", "failed", "cancelled", "timed_out"}

    PROGRESS_MAP = {
        "pending": 0,
        "listening": 10,
        "processing": 30,
        "understanding": 30,
        "matching": 50,
        "requires_approval": 50,
        "awaiting_approval": 50,
        "launching": 75,
        "executing": 75,
        "running": 75,
        "launched": 100,
        "verifying": 100,
        "completed": 100,
        "failed": 100,
        "timed_out": 100,
        "cancelled": 100,
    }

    STAGE_DESCRIPTIONS = {
        "listening": "Listening for voice input audio",
        "processing": "Processing input and extracting intent via AI Planner",
        "understanding": "Understanding the user's intent and target action",
        "matching": "Matching and resolving application identifiers in catalogue",
        "requires_approval": "Awaiting user approval before launching",
        "awaiting_approval": "Awaiting explicit user approval before launching",
        "launching": "Dispatching launch to Windows Automation",
        "executing": "Executing the user-approved automation step",
        "running": "Automation in progress",
        "launched": "Application launched and verified on desktop",
        "verifying": "Verifying the task result against desktop evidence",
        "completed": "Task completed and verified",
        "failed": "Task execution failed",
        "timed_out": "Task execution timed out",
        "cancelled": "Task execution was cancelled",
        "pending": "Task pending evaluation",
    }

    @classmethod
    def normalize_status(cls, status: Optional[str]) -> Optional[str]:
        """Normalize spec aliases back to the canonical internal state names."""
        if not status:
            return status
        return cls.STATUS_ALIASES.get(status, status)

    @classmethod
    def can_transition(cls, current_status: str, next_status: str) -> bool:
        """Check whether a state transition is permitted."""
        current_norm = cls.normalize_status(current_status)
        next_norm = cls.normalize_status(next_status)
        allowed = cls.VALID_TRANSITIONS.get(current_norm, set())
        return next_norm in allowed

    @classmethod
    def transition(cls, task: Dict[str, Any], next_status: str, message: Optional[str] = None) -> None:
        """
        Transition task to next_status, appending a truthful progress timeline entry.
        Raises ValueError if the transition is invalid.
        """
        current_status = task.get("status", "pending")
        current_norm = cls.normalize_status(current_status)
        next_norm = cls.normalize_status(next_status)

        if current_norm == next_norm:
            task["status"] = next_status
            if message:
                task["message"] = message
            return

        if not cls.can_transition(current_status, next_status):
            raise ValueError(
                f"Invalid task state transition from '{current_status}' to '{next_status}'. "
                f"Allowed target states: {sorted(list(cls.VALID_TRANSITIONS.get(current_norm, set())))}"
            )

        task["status"] = next_status
        if message:
            task["message"] = message

        timeline: List[Dict[str, Any]] = task.setdefault("timeline", [])
        timeline.append({
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
        "notes": "notepad",
        "text editor": "notepad",
        "calc": "calculator",
        "calculator": "calculator",
        "math": "calculator",
        "chrome": "chrome",
        "google chrome": "chrome",
        "google": "google",
        "youtube": "youtube",
        "yt": "youtube",
        "spotify": "spotify",
        "netflix": "netflix",
        "github": "github",
        "browser": "chrome",
        "my browser": "chrome",
        "web browser": "chrome",
        "internet": "chrome",
        "code": "vscode",
        "vs code": "vscode",
        "vscode": "vscode",
        "visual studio code": "vscode",
        "code editor": "vscode",
        "my code editor": "vscode",
        "editor": "vscode",
        "edge": "edge",
        "microsoft edge": "edge",
        "paint": "paint",
        "drawing": "paint",
    }

    FORBIDDEN_IDENTIFIER_CHARS = {";", "&", "|", ">", "<", "`", "$", "/", "\\", " ", "\n", "\r", "\t", "\0"}

    def __init__(self, catalogue: Optional[List[Dict[str, Any]]] = None):
        self.catalogue = catalogue if catalogue is not None else get_installed_apps()

    def is_valid_application_id(self, app_id: Optional[str]) -> bool:
        """Validate format and characters of an application identifier."""
        if not app_id or not isinstance(app_id, str):
            return False
        clean = app_id.strip()
        if not clean:
            return False
        return not any(ch in clean for ch in self.FORBIDDEN_IDENTIFIER_CHARS)

    def is_ambiguous(self, target: str) -> bool:
        """
        Detect ambiguous targets that match multiple installed applications.
        Uses both static check and the Windows Application Catalogue.
        """
        clean = (target or "").strip().lower().rstrip("?.!,")
        # Static check: "visual studio" or "vs" match both VS Code and VS 2022
        if clean in ("visual studio", "vs"):
            return True
        # Dynamic check via Windows Application Catalogue
        is_amb, _ = _windows_catalogue.is_ambiguous(clean)
        return is_amb

    def validate_structured_request(self, req: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate structured execution request parameters before dispatching.
        Returns: (is_valid, error_code, error_message)
        """
        action = req.get("action")
        if not action or action not in ("open_application", "launch_application", "search_web_app"):
            return False, "ERR_INVALID_INTENT", f"Action '{action}' is not supported."

        app_id = req.get("application_id")
        if not self.is_valid_application_id(app_id):
            return False, "ERR_INVALID_APPLICATION_ID", f"Invalid application identifier: '{app_id}'"

        params = req.get("parameters")
        if params is None or not isinstance(params, dict):
            return False, "ERR_MISSING_PARAMETERS", "Missing or invalid 'parameters' dictionary in structured request."

        target = req.get("target")
        if not target or not isinstance(target, str) or not target.strip():
            return False, "ERR_MISSING_PARAMETERS", "Missing required 'target' parameter in structured request."

        return True, None, None

    def resolve(self, target: str) -> Optional[Dict[str, Any]]:
        """
        Resolve an application name or alias to its installed catalogue entry.

        Resolution order:
        1. AI Engine catalogue (direct name/id/executable match)
        2. Static ALIASES map
        3. Windows Application Catalogue (new dynamic catalogue with Settings URIs)
        4. Notepad hardcoded fallback
        """
        clean = (target or "").strip().lower().rstrip("?.!,")
        if not clean:
            return None

        clean_no_prefix = clean[4:] if clean.startswith("app_") else clean
        clean_space = clean_no_prefix.replace("_", " ")

        # 1. Direct check against AI Engine catalogue by app_name, app_id, or executable
        for app in self.catalogue:
            candidates = (
                app["app_name"].lower(),
                app["app_id"].lower(),
                app.get("executable", "").lower(),
                app["app_name"].replace(" ", "").lower(),
            )
            if clean in candidates or clean_no_prefix in candidates or clean_space in candidates:
                return app

        # 2. Check static ALIASES map
        for check in (clean, clean_no_prefix, clean_space):
            if check in self.ALIASES:
                aliased_id = self.ALIASES[check]
                for app in self.catalogue:
                    if app["app_id"] == aliased_id:
                        return app

        # 3. Windows Application Catalogue (dynamic — covers Settings pages, built-ins, third‑party)
        catalogue_entry = _windows_catalogue.resolve_phrase(target)
        if catalogue_entry:
            return {
                "app_name": catalogue_entry["app_name"],
                "app_id": catalogue_entry["app_id"],
                "executable": catalogue_entry["executable"],
                "launch_target": catalogue_entry.get("launch_target", catalogue_entry["executable"]),
                "launch_type": catalogue_entry.get("launch_type", "executable"),
                "allowlisted": catalogue_entry.get("allowlisted", False),
            }

        # 4. Hardcoded fallback for Notepad (always allowlisted)
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

    DIRECT_ALLOWLIST = {"notepad", "notepad.exe", "app_notepad"}
    HUMAN_ACTIVITY_ACTIONS = {
        "search_web_app",
        "open_website",
        "search",
        "play_video",
        "ask_prompt",
        "prompt_ai_chat",
        "type_text",
        "clipboard_copy",
        "clipboard_paste",
        "click_youtube_result",
        "capture_ai_response",
        "batch_download",
        "compose_email",
        "navigate_url",
        "press_hotkey",
        "wait",
    }

    def evaluate(self, task_id: str, action_name: str, target: str) -> AuthorizationDecision:
        """
        Evaluate security permission for a specific plan step.
        Returns an AuthorizationDecision instance.
        """
        decision_id = f"dec_{uuid4()}"
        clean_action = (action_name or "").strip()
        clean_target = (target or "").strip().lower()
        clean_target_base = clean_target[4:] if clean_target.startswith("app_") else clean_target

        # Check supported actions
        if clean_action != "open_application" and clean_action not in self.HUMAN_ACTIVITY_ACTIONS:
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

        # Human-activity, web search, and GUI automation actions are allowlisted for direct execution
        if clean_action in self.HUMAN_ACTIVITY_ACTIONS:
            return AuthorizationDecision(
                decision_id=decision_id,
                permission_status="granted",
                requires_user_approval=False,
                approval_reference="user_auto_allowlist_human_activity",
                reason=f"Action '{clean_action}' on '{target}' is allowlisted.",
            )

        # 1. Milestone 1 Allowlist Check: Direct launch granted for Notepad
        if clean_target in self.DIRECT_ALLOWLIST or clean_target_base in self.DIRECT_ALLOWLIST:
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
                app.get("executable", "").lower(),
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

        # 3. Not in allowlist and not in catalogue → Denied
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
        # Initialize components
        self.planner = planner or TaskPlanner()
        self.adapter = adapter or WindowsAutomationAdapter()
        # Initialize SQLite task repository
        self.repo = TaskRepository()
        # Load persisted tasks into in‑memory dict (or use provided dict)
        if tasks is not None:
            self.tasks: Dict[str, Dict[str, Any]] = tasks
        else:
            self.tasks = {t["task_id"]: t for t in self.repo.list_tasks()}
        self.permission_evaluator = PermissionEvaluator()
        self.resolver = ApplicationResolver()
        self.state_machine = TaskStateMachine()
        # In‑memory register mapping idempotency_key → task_id
        self._idempotency_registry: Dict[str, str] = {}

    def _persist_task(self, task_id: str) -> None:
        """Persist the current state of a task to SQLite."""
        task = self.tasks.get(task_id)
        if task:
            self.repo.update_task(task_id, task)

    # -----------------------------------------------------------------------
    # Application Catalogue
    # -----------------------------------------------------------------------

    def get_catalogue(self) -> List[Dict[str, Any]]:
        """Return the installed application catalogue annotated with allowlist status."""
        apps = get_installed_apps()
        results: List[Dict[str, Any]] = []
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
            "intent": task.get("intent"),
            "selected_application": task.get("selected_application"),
            "application_id": task.get("application_id"),
            "structured_request": task.get("structured_request"),
        }

    # -----------------------------------------------------------------------
    # Common Execution Pipeline (Voice & Text)
    # -----------------------------------------------------------------------

    def run_pipeline(
        self,
        command: Optional[str] = None,
        input_type: InputType = "text",
        auto_execute: bool = True,
        idempotency_key: Optional[str] = None,
        timeout_seconds: float = 10.0,
        simulate_service_down: bool = False,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Common execution pipeline for all user requests (voice and text).

        Flow:
        User Input → Voice/Text Processing → AI Intent → Application Matching →
        Windows Automation → Verification → Task Status (launched / failed)
        """
        # Step 1: Idempotency Gate
        if idempotency_key and idempotency_key in self._idempotency_registry:
            existing_id = self._idempotency_registry[idempotency_key]
            raise DuplicateRequestError(
                f"Duplicate request detected for idempotency key '{idempotency_key}'. Task ID: '{existing_id}'."
            )

        # Step 2: Task Record Initialization
        task_id = task_id or f"task_{uuid4()}"
        initial_status = "listening" if (input_type == "voice" and not command) else "processing"

        task: Dict[str, Any] = {
            "task_id": task_id,
            "title": command or ("Voice Command" if input_type == "voice" else "Task"),
            "description": "",
            "command": command,
            "input_type": input_type,
            "idempotency_key": idempotency_key,
            "intent": None,
            "selected_application": None,
            "application_id": None,
            "structured_request": None,
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

        # If initially listening, wait for voice transcript unless command is provided
        if task["status"] == "listening":
            if not command or not command.strip():
                task["message"] = "Listening for voice input audio."
                return task
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

        # Step 4.1: Ambiguity / Clarification
        clean_cmd = (command or "").strip().lower()
        is_launch_command = any(
            clean_cmd.startswith(prefix)
            for prefix in ("open", "launch", "start", "please open", "can you open", "could you open", "would you open")
        )
        app_entity = getattr(plan_response.entities, "application", None)
        target_candidate = app_entity or (command.split()[-1] if len(command.split()) > 1 else "")

        if (
            plan_response.status == "clarification_required"
            or self.resolver.is_ambiguous(target_candidate)
            or self.resolver.is_ambiguous(command)
        ):
            clarification_msg = (
                plan_response.clarification_question
                or plan_response.message
                or f"Command '{command}' is ambiguous. Please specify the exact application."
            )
            self.state_machine.transition(task, "failed", clarification_msg)
            task["error_code"] = "ERR_AMBIGUOUS_COMMAND"
            task["error_message"] = clarification_msg
            task["completed_at"] = current_iso_timestamp()
            return task

        # Step 4.2: Unsupported / Missing Steps – try fallback resolution
        if plan_response.status == "unsupported" or not plan_response.steps:
            if is_launch_command:
                resolved_app = self.resolver.resolve(target_candidate) or self.resolver.resolve(clean_cmd)
                if resolved_app and resolved_app.get("allowlisted", True) is not False:
                    task["intent"] = "open_application"
                    task["steps"] = [{
                        "step_id": 1,
                        "action": "open_application",
                        "target": resolved_app["app_name"],
                        "depends_on": [],
                        "expected_outcome": f"{resolved_app['app_name']} should open successfully.",
                    }]
                else:
                    self.state_machine.transition(task, "failed", f"Unknown application: '{target_candidate}' is not recognized.")
                    task["error_code"] = "ERR_UNKNOWN_APPLICATION"
                    task["error_message"] = f"Application '{target_candidate}' not found in installed catalogue."
                    task["completed_at"] = current_iso_timestamp()
                    return task
            else:
                self.state_machine.transition(task, "failed", plan_response.message or "Invalid or unsupported command intent.")
                task["error_code"] = "ERR_INVALID_INTENT"
                task["error_message"] = plan_response.message or "Planner could not extract an actionable intent."
                task["completed_at"] = current_iso_timestamp()
                return task
        else:
            task["steps"] = [
                {
                    "step_id": step.step_id,
                    "action": step.action,
                    "target": step.target,
                    "depends_on": getattr(step, "depends_on", []),
                    "expected_outcome": step.expected_outcome,
                    "parameters": getattr(step, "parameters", {}),
                }
                for step in plan_response.steps
            ]

        # Step 5: Application Identifier Resolution & Structured Request Generation
        self.state_machine.transition(task, "matching", "Resolving target application against installed catalogue.")
        steps_list: List[Dict[str, Any]] = task["steps"]
        if len(steps_list) > 1 or steps_list[0].get("action") not in ("open_application", "search_web_app"):
            return self._execute_multistep_run_command(
                task=task,
                steps_list=steps_list,
                auto_execute=auto_execute,
                timeout_seconds=timeout_seconds,
                plan_response=plan_response,
            )

        step_data = steps_list[0]
        action_name = str(step_data.get("action", ""))
        raw_target = str(step_data.get("target", ""))
        raw_params = step_data.get("parameters") if isinstance(step_data.get("parameters"), dict) else {}
        if not raw_params and hasattr(plan_response, "entities"):
            entities_params = getattr(plan_response.entities, "parameters", {})
            if isinstance(entities_params, dict):
                raw_params = entities_params
        step_params = raw_params or {}

        resolved_app = self.resolver.resolve(raw_target)
        if not resolved_app and raw_target.lower() not in ("notepad", "notepad.exe"):
            self.state_machine.transition(task, "failed", f"Unknown application: '{raw_target}' is not recognized.")
            task["error_code"] = "ERR_UNKNOWN_APPLICATION"
            task["error_message"] = f"Application '{raw_target}' not found in installed catalogue."
            task["completed_at"] = current_iso_timestamp()
            return task

        canonical_target = str(resolved_app["app_name"]) if resolved_app else raw_target
        app_id = str(resolved_app.get("app_id", "notepad")) if resolved_app else ("notepad" if raw_target.lower().startswith("notepad") else raw_target.lower())
        step_data["target"] = canonical_target
        step_data["parameters"] = step_params

        task["selected_application"] = canonical_target
        task["application_id"] = app_id

        # Generate StructuredActionRequest
        structured_action = "search_web_app" if action_name == "search_web_app" else "launch_application"
        structured_req = StructuredActionRequest(
            action=structured_action,
            application_id=app_id,
            target=canonical_target,
            parameters=step_params,
            source=input_type,
        )
        task["structured_request"] = structured_req.model_dump()

        is_valid, val_err_code, val_err_msg = self.resolver.validate_structured_request(task["structured_request"])
        if not is_valid:
            self.state_machine.transition(task, "failed", val_err_msg or "Invalid structured request.")
            task["error_code"] = val_err_code or "ERR_INVALID_REQUEST"
            task["error_message"] = val_err_msg
            task["completed_at"] = current_iso_timestamp()
            return task

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

        # Automation service availability check
        if self.adapter is None:
            self.state_machine.transition(task, "failed", "Windows Automation service is unavailable.")
            task["error_code"] = "ERR_AUTOMATION_UNAVAILABLE"
            task["error_message"] = "Windows Automation service is offline or unreachable."
            task["completed_at"] = current_iso_timestamp()
            return task

        # Step 7: Windows Automation Dispatch (launching)
        self.state_machine.transition(
            task, "launching", f"Dispatching '{action_name}' on '{canonical_target}' to Windows Automation."
        )

        # Build the PlanStep with merged parameters (no extra params at this point)
        plan_step = PlanStep(
            step_id=step_data.get("step_id", 1),
            action=action_name,
            target=canonical_target,
            depends_on=step_data.get("depends_on", []),
            expected_outcome=step_data.get("expected_outcome", ""),
            parameters=step_params,
        )

        try:
            exec_result: ExecutionResult = self.adapter.execute_plan_step(
                step=plan_step,
                task_id=task_id,
                authorization=auth,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            self.state_machine.transition(task, "failed", f"Windows Automation execution failure: {str(exc)}")
            task["active_action_id"] = None
            task["error_code"] = "ERR_AUTOMATION_FAILURE"
            task["error_message"] = str(exc)
            task["completed_at"] = current_iso_timestamp()
            return task

        # Record execution result
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
            task["error_code"] = None
            task["error_message"] = None

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

    def _execute_multistep_run_command(
        self,
        task: Dict[str, Any],
        steps_list: List[Dict[str, Any]],
        auto_execute: bool,
        timeout_seconds: float,
        plan_response: Any,
    ) -> Dict[str, Any]:
        """Execute multi-step and human-activity plans sequentially with inter-step context passing."""
        task_id = task["task_id"]
        if not auto_execute:
            return task

        if self.adapter is None:
            self.state_machine.transition(task, "failed", "Windows Automation service is unavailable.")
            task["error_code"] = "ERR_AUTOMATION_UNAVAILABLE"
            task["error_message"] = "Windows Automation service is offline or unreachable."
            task["completed_at"] = current_iso_timestamp()
            return task

        context: Dict[str, Any] = {}
        last_result: Optional[ExecutionResult] = None

        for idx, step_data in enumerate(steps_list):
            task["current_step_index"] = idx
            action_name = str(step_data.get("action", ""))
            target = str(step_data.get("target", ""))
            raw_params = step_data.get("parameters") if isinstance(step_data.get("parameters"), dict) else {}
            merged_params = {**context, **raw_params} if context else dict(raw_params)

            # Resolve desktop app target when action is open_application
            if action_name == "open_application":
                resolved_app = self.resolver.resolve(target)
                if resolved_app:
                    target = str(resolved_app["app_name"])
                    step_data["target"] = target

            auth = self.permission_evaluator.evaluate(task_id, action_name, target)
            task["authorization"] = auth.to_dict()
            if auth.permission_status == "denied":
                self.state_machine.transition(task, "failed", auth.reason)
                task["error_code"] = "ERR_PERMISSION_DENIED"
                task["error_message"] = auth.reason
                task["completed_at"] = current_iso_timestamp()
                return task

            self.state_machine.transition(
                task, "launching", f"Step {idx + 1}/{len(steps_list)}: '{action_name}' on '{target}'."
            )
            plan_step = PlanStep(
                step_id=step_data.get("step_id", idx + 1),
                action=action_name,
                target=target,
                depends_on=step_data.get("depends_on", []),
                expected_outcome=step_data.get("expected_outcome", ""),
                parameters=merged_params,
            )

            try:
                exec_result: ExecutionResult = self.adapter.execute_plan_step(
                    step=plan_step,
                    task_id=task_id,
                    authorization=auth,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                self.state_machine.transition(task, "failed", f"Step {idx + 1} failed: {str(exc)}")
                task["error_code"] = "ERR_AUTOMATION_FAILURE"
                task["error_message"] = str(exc)
                task["completed_at"] = current_iso_timestamp()
                return task

            last_result = exec_result
            if exec_result.status != "completed":
                self.state_machine.transition(task, "failed", exec_result.error_message or f"Step {idx + 1} failed.")
                task["error_code"] = exec_result.error_code or "ERR_LAUNCH_FAILED"
                task["error_message"] = exec_result.error_message or "Step execution failed."
                task["completed_at"] = current_iso_timestamp()
                return task

            # Pass captured/copied output forward to subsequent steps (e.g. capture_ai_response -> clipboard_paste)
            if exec_result.verification and isinstance(exec_result.verification.details, dict):
                details = exec_result.verification.details
                captured = details.get("captured_text") or details.get("copied_text")
                if captured:
                    context["text"] = captured
                    context["output_text"] = captured

        if last_result:
            task["active_action_id"] = None
            task["duration_ms"] = last_result.duration_ms
            task["completed_at"] = last_result.completed_at
            result_dict = last_result.to_dict()
            if context.get("output_text"):
                result_dict["output_text"] = context["output_text"]
            task["result"] = result_dict
            task["verification"] = last_result.verification.to_dict() if last_result.verification else None
            task["audit"] = last_result.audit.to_dict() if last_result.audit else None

        if getattr(plan_response, "requires_clarification", False) and getattr(plan_response, "clarification_question", None):
            task["requires_clarification"] = True
            task["clarification_question"] = plan_response.clarification_question
            task["message"] = plan_response.clarification_question
            self.state_machine.transition(task, "launched", plan_response.clarification_question)
        else:
            msg = f"Completed {len(steps_list)}-step human-activity workflow."
            task["message"] = msg
            self.state_machine.transition(task, "launched", msg)

        task["error_code"] = None
        task["error_message"] = None
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

        requires_clarification = False
        clarification_question = None

        command_text = command
        if command_text:
            plan_response = self.planner.process_command(CommandRequest(text=command_text))
            intent = plan_response.intent
            message = plan_response.message
            requires_clarification = bool(getattr(plan_response, "requires_clarification", False))
            clarification_question = getattr(plan_response, "clarification_question", None)

            steps = [
                {
                    "step_id": step.step_id,
                    "action": step.action,
                    "target": step.target,
                    "depends_on": getattr(step, "depends_on", []),
                    "expected_outcome": step.expected_outcome,
                    "parameters": getattr(step, "parameters", {}),
                }
                for step in plan_response.steps
            ]

            if plan_response.status == "clarification_required":
                message = plan_response.clarification_question or plan_response.message
            elif plan_response.status == "unsupported":
                initial_status = "failed"
                message = plan_response.message

        task: Dict[str, Any] = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "command": command_text,
            "intent": intent,
            "status": initial_status,
            "steps": steps,
            "requires_clarification": requires_clarification,
            "clarification_question": clarification_question,
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
        """Execute pending plan steps through policy evaluation, dispatch, and verification.
        The task state is persisted to SQLite after each mutation."""
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        current_status = task["status"]

        if current_status in self.state_machine.TERMINAL_STATES:
            return task

        steps = task.get("steps", [])
        context: Dict[str, Any] = {}

        if not steps:
            if current_status == "pending":
                task["message"] = "No executable plan steps found for this task."
                self._persist_task(task_id)
            return task

        for step_idx, step_data in enumerate(steps):
            task["current_step_index"] = step_idx
            action_name = step_data.get("action", "")
            target = step_data.get("target", "")
            step_id = step_data.get("step_id", 1)

            # Merge any explicit parameters with context from previous step
            step_params = step_data.get("parameters", {}) or {}
            merged_params = {**context, **step_params} if context else step_params
            step_data["parameters"] = merged_params

            auth_dict = task.get("authorization")
            if auth_dict and auth_dict.get("permission_status") == "granted":
                auth = AuthorizationDecision.from_dict(auth_dict)
            else:
                auth = self.permission_evaluator.evaluate(task_id, action_name, target)
                task["authorization"] = auth.to_dict()

            if auth.permission_status == "requires_approval":
                self.state_machine.transition(task, "requires_approval", auth.reason)
                self._persist_task(task_id)
                return task

            if auth.permission_status == "denied":
                self.state_machine.transition(task, "failed", auth.reason)
                task["error_code"] = "ERR_PERMISSION_DENIED"
                task["error_message"] = auth.reason
                task["completed_at"] = current_iso_timestamp()
                self._persist_task(task_id)
                return task

            # Mark running state (skip redundant transition if already running on multi-step)
            if task["status"] != "running":
                self.state_machine.transition(task, "running", f"Executing '{action_name}' on '{target}'.")
            else:
                task["timeline"].append({
                    "timestamp": current_iso_timestamp(),
                    "state": "running",
                    "message": f"Step {step_idx + 1}/{len(steps)}: Executing '{action_name}' on '{target}'.",
                })
            task["started_at"] = task["started_at"] or current_iso_timestamp()

            plan_step = PlanStep(
                step_id=step_id,
                action=action_name,
                target=target,
                depends_on=step_data.get("depends_on", []),
                expected_outcome=step_data.get("expected_outcome", ""),
                parameters=merged_params,
            )

            try:
                exec_result: ExecutionResult = self.adapter.execute_plan_step(
                    step=plan_step,
                    task_id=task_id,
                    authorization=auth,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                self.state_machine.transition(task, "failed", f"Windows Automation execution failure: {str(exc)}")
                task["active_action_id"] = None
                task["error_code"] = "ERR_AUTOMATION_FAILURE"
                task["error_message"] = str(exc)
                task["completed_at"] = current_iso_timestamp()
                self._persist_task(task_id)
                return task

            task["active_action_id"] = exec_result.action_id

            if exec_result.status == "completed":
                task["active_action_id"] = None
                task["result"] = exec_result.to_dict()
                task["verification"] = exec_result.verification.to_dict() if exec_result.verification else None
                task["audit"] = exec_result.audit.to_dict() if exec_result.audit else None
                task["duration_ms"] = exec_result.duration_ms
                task["completed_at"] = exec_result.completed_at

                if step_idx == len(steps) - 1:
                    self.state_machine.transition(task, "completed", f"Action '{action_name}' completed and verified.")
                    if task.get("requires_clarification") and task.get("clarification_question"):
                        task["message"] = task["clarification_question"]
                    else:
                        task["message"] = f"Action '{action_name}' completed and verified successfully."
                else:
                    task["message"] = f"Step {step_idx + 1}/{len(steps)} ('{action_name}') completed."

                self._persist_task(task_id)
                # Accumulate context across steps so captured/copied text persists through open_website -> clipboard_paste
                if exec_result.verification and isinstance(exec_result.verification.details, dict):
                    details = exec_result.verification.details
                    context.update(details)
                    captured = details.get("captured_text") or details.get("copied_text")
                    if captured:
                        context["text"] = captured
                continue

            elif exec_result.status == "cancelled":
                self.state_machine.transition(task, "cancelled", "Action was cancelled.")
                task["active_action_id"] = None
                task["error_code"] = exec_result.error_code or "ERR_CANCELLED"
                task["error_message"] = exec_result.error_message or "Action was cancelled."
                task["completed_at"] = exec_result.completed_at
                self._persist_task(task_id)
                return task

            else:
                self.state_machine.transition(task, "failed", exec_result.error_message or "Execution failed.")
                task["active_action_id"] = None
                task["error_code"] = exec_result.error_code or "ERR_EXECUTION_FAILED"
                task["error_message"] = exec_result.error_message or "Action execution failed."
                task["duration_ms"] = exec_result.duration_ms
                task["completed_at"] = exec_result.completed_at
                self._persist_task(task_id)
                return task

        # All steps processed – ensure final persistence
        self._persist_task(task_id)
        return task
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

        for step_idx, step_data in enumerate(steps):
            task["current_step_index"] = step_idx
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
                parameters=step_data.get("parameters", {}),
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
        auth_data: Dict[str, Any] = dict(task.get("authorization") or {})
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