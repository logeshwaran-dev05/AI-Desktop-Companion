"""
Integration adapter for Windows Automation module.

Provides a clean bridge between:
1. Booviha's `ai_engine` (PlanStep objects).
2. Hariram's `api` / backend (dictionary or FastAPI model requests).
3. Vinay's `desktop` (Electron IPC or local display results).

Keeps integration strictly isolated behind this narrow adapter until
team contracts are formally finalized.
"""

import uuid
from typing import Any, Dict, Optional, Union
from windows_automation.schemas import (
    ActionRequest,
    ExecutionResult,
    AuthorizationDecision,
)
from windows_automation.executor import WindowsAutomationExecutor


class WindowsAutomationAdapter:
    """Adapter bridging external caller models to Windows Automation executor."""

    def __init__(self, executor: Optional[WindowsAutomationExecutor] = None):
        self.executor = executor or WindowsAutomationExecutor()

    def execute_plan_step(
        self,
        step: Any,
        task_id: Optional[str] = None,
        authorization: Optional[Union[AuthorizationDecision, Dict[str, Any]]] = None,
        timeout_seconds: float = 10.0,
    ) -> ExecutionResult:
        """
        Execute a step received from Booviha's `ai_engine.schemas.command_schema.PlanStep`.
        """
        task_id = task_id or f"task_{uuid.uuid4()}"
        action_id = f"act_{uuid.uuid4()}"

        # Extract attributes from PlanStep or dict
        action_name = getattr(step, "action", None) or (step.get("action") if isinstance(step, dict) else "")
        target = getattr(step, "target", None) or (step.get("target") if isinstance(step, dict) else "")
        step_id = getattr(step, "step_id", 1) or (step.get("step_id", 1) if isinstance(step, dict) else 1)

        # Handle authorization
        auth_obj = None
        if isinstance(authorization, AuthorizationDecision):
            auth_obj = authorization
        elif isinstance(authorization, dict):
            auth_obj = AuthorizationDecision.from_dict(authorization)
        else:
            # Default: if no authorization provided, build a placeholder that requires check
            auth_obj = AuthorizationDecision(
                decision_id=f"dec_{uuid.uuid4()}",
                permission_status="denied",
                reason="No authorization provided to adapter.",
            )

        request = ActionRequest(
            action_id=action_id,
            task_id=task_id,
            step_id=step_id,
            action_name=action_name,
            target=target,
            timeout_seconds=timeout_seconds,
            authorization=auth_obj,
        )

        return self.executor.execute(request)

    def execute_raw_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute raw JSON payload from Backend API or Desktop IPC.
        Returns a serializable dictionary matching the proposed TEAM_CONTRACTS schema.
        """
        request = ActionRequest.from_dict(payload)
        result = self.executor.execute(request)
        return result.to_dict()

    def cancel_action(self, action_id: str) -> bool:
        """Cancel an ongoing action by its action_id."""
        return self.executor.cancel(action_id)
