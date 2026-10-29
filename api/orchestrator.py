"""
Task Orchestrator, State Machine, and Permission Evaluator for Backend API.

Implements the core backend orchestration layer bridging:
1. AI Engine (TaskPlanner & Application Catalogue)
2. Windows Automation (WindowsAutomationAdapter, Policy, and Schemas)
3. API / Client Task Lifecycle State Machine
"""

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


class TaskStateMachine:
    """
    Deterministic Task State Machine.
    
    States:
    - pending: Created and queued; plan being evaluated.
    - requires_approval: Action requires explicit human confirmation before execution.
    - running: Action dispatched and currently executing.
    - completed: Action executed and verified by automation verifier.
    - failed: Validation, policy check, launch, or verification failed.
    - cancelled: Execution aborted by user request or timeout.
    """

    VALID_TRANSITIONS = {
        "pending": {"running", "requires_approval", "cancelled", "failed"},
        "requires_approval": {"running", "failed", "cancelled"},
        "running": {"completed", "failed", "cancelled"},
        "completed": set(),  # Terminal state
        "failed": set(),     # Terminal state
        "cancelled": set(),  # Terminal state
    }

    TERMINAL_STATES = {"completed", "failed", "cancelled"}

    @classmethod
    def can_transition(cls, current_status: str, next_status: str) -> bool:
        """Check whether a state transition is permitted."""
        allowed = cls.VALID_TRANSITIONS.get(current_status, set())
        return next_status in allowed

    @classmethod
    def transition(cls, task: Dict[str, Any], next_status: str) -> None:
        """
        Transition task to next_status.
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


class TaskOrchestrator:
    """
    Central orchestration service coordinating TaskPlanner, Application Catalogue,
    PermissionEvaluator, and WindowsAutomationAdapter.
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
        self.state_machine = TaskStateMachine()

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
    # Task Lifecycle Management
    # -----------------------------------------------------------------------

    def create_task(
        self,
        title: str,
        description: str = "",
        command: Optional[str] = None,
        auto_execute: bool = False,
        timeout_seconds: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Create a new task, optionally planning steps if a command is provided.
        """
        task_id = f"task_{uuid4()}"
        steps: List[Dict[str, Any]] = []
        intent = None
        message = "Task initialized."
        initial_status = "pending"

        # Plan command if command is provided
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

    # -----------------------------------------------------------------------
    # Task Execution & State Transitions
    # -----------------------------------------------------------------------

    def execute_task(self, task_id: str, timeout_seconds: float = 10.0) -> Dict[str, Any]:
        """
        Execute pending plan steps through policy evaluation, dispatch, and verification.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        current_status = task["status"]

        # Check terminal state
        if current_status in self.state_machine.TERMINAL_STATES:
            return task

        steps = task.get("steps", [])
        if not steps:
            if current_status == "pending":
                task["message"] = "No executable plan steps found for this task."
            return task

        # Execute steps sequentially
        for step_data in steps:
            action_name = step_data.get("action", "")
            target = step_data.get("target", "")
            step_id = step_data.get("step_id", 1)

            # Evaluate permission unless previously granted
            auth_dict = task.get("authorization")
            if auth_dict and auth_dict.get("permission_status") == "granted":
                auth = AuthorizationDecision.from_dict(auth_dict)
            else:
                auth = self.permission_evaluator.evaluate(task_id, action_name, target)
                task["authorization"] = auth.to_dict()

            # Handle permission outcomes
            if auth.permission_status == "requires_approval":
                self.state_machine.transition(task, "requires_approval")
                task["message"] = auth.reason
                return task

            if auth.permission_status == "denied":
                self.state_machine.transition(task, "failed")
                task["error_code"] = "ERR_PERMISSION_DENIED"
                task["error_message"] = auth.reason
                task["message"] = f"Task failed: {auth.reason}"
                task["completed_at"] = current_iso_timestamp()
                return task

            # Permission granted -> transition to running
            self.state_machine.transition(task, "running")
            task["started_at"] = task["started_at"] or current_iso_timestamp()
            task["message"] = f"Executing '{action_name}' on target '{target}'."

            # Construct PlanStep object or use dict directly with adapter
            plan_step = PlanStep(
                step_id=step_id,
                action=action_name,
                target=target,
                depends_on=step_data.get("depends_on", []),
                expected_outcome=step_data.get("expected_outcome", ""),
            )

            # Dispatch execution to Windows Automation Adapter
            exec_result: ExecutionResult = self.adapter.execute_plan_step(
                step=plan_step,
                task_id=task_id,
                authorization=auth,
                timeout_seconds=timeout_seconds,
            )

            task["active_action_id"] = exec_result.action_id

            # Process execution outcome
            if exec_result.status == "completed":
                self.state_machine.transition(task, "completed")
                task["active_action_id"] = None
                task["result"] = exec_result.to_dict()
                task["verification"] = (
                    exec_result.verification.to_dict()
                    if exec_result.verification else None
                )
                task["audit"] = (
                    exec_result.audit.to_dict()
                    if exec_result.audit else None
                )
                task["duration_ms"] = exec_result.duration_ms
                task["completed_at"] = exec_result.completed_at
                task["message"] = f"Action '{action_name}' completed and verified successfully."

            elif exec_result.status == "cancelled":
                self.state_machine.transition(task, "cancelled")
                task["active_action_id"] = None
                task["error_code"] = exec_result.error_code or "ERR_CANCELLED"
                task["error_message"] = exec_result.error_message or "Action was cancelled."
                task["completed_at"] = exec_result.completed_at
                task["message"] = "Task was cancelled."
                return task

            else:
                self.state_machine.transition(task, "failed")
                task["active_action_id"] = None
                task["error_code"] = exec_result.error_code or "ERR_EXECUTION_FAILED"
                task["error_message"] = exec_result.error_message or "Action execution failed."
                task["duration_ms"] = exec_result.duration_ms
                task["completed_at"] = exec_result.completed_at
                task["message"] = f"Task failed: {task['error_message']}"
                return task

        return task

    def approve_task(
        self,
        task_id: str,
        approval_reference: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Explicitly approve a task paused in 'requires_approval' status and resume execution.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        if task["status"] != "requires_approval":
            raise ValueError(
                f"Task '{task_id}' is in status '{task['status']}', expected 'requires_approval'."
            )

        ref = approval_reference or f"user_approval_{uuid4().hex[:8]}"

        # Update authorization record to granted with approval reference
        auth_data = task.get("authorization") or {}
        auth_data["permission_status"] = "granted"
        auth_data["requires_user_approval"] = True
        auth_data["approval_reference"] = ref
        auth_data["reason"] = f"User explicitly approved action via reference: {ref}"
        task["authorization"] = auth_data

        # Resume execution
        return self.execute_task(task_id, timeout_seconds=timeout_seconds)

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a pending or running task.
        If running, safely terminates the active automation process.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        current_status = task["status"]

        if current_status in self.state_machine.TERMINAL_STATES:
            raise ValueError(f"Cannot cancel task in terminal state '{current_status}'.")

        # If currently running an action, signal cancellation to adapter
        active_action = task.get("active_action_id")
        if active_action:
            self.adapter.cancel_action(active_action)
            task["active_action_id"] = None

        self.state_machine.transition(task, "cancelled")
        task["completed_at"] = current_iso_timestamp()
        task["error_code"] = "ERR_CANCELLED"
        task["error_message"] = "Task was cancelled by user request."
        task["message"] = "Task cancelled."

        return task

    def run_command(
        self,
        text: str,
        auto_approve: bool = False,
        timeout_seconds: float = 10.0,
    ) -> Dict[str, Any]:
        """
        One-shot end-to-end command orchestration:
        1. Natural language planning
        2. Task creation
        3. Permission evaluation & dispatch
        4. Verified outcome return
        """
        # Create task from command
        task = self.create_task(
            title=text,
            command=text,
            auto_execute=False,
            timeout_seconds=timeout_seconds,
        )

        # If plan had errors, clarification, or unsupported
        if task["status"] != "pending":
            return task

        if not task.get("steps"):
            task["status"] = "failed"
            task["message"] = "Planner did not generate any actionable steps."
            return task

        # If auto_approve is requested, pre-approve catalogue apps
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
