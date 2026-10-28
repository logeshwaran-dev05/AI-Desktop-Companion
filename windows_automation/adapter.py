"""
Integration adapter for Windows Automation module.

Provides a clean bridge between:
1. Booviha's `ai_engine` (PlanStep objects with natural language targets).
2. Hariram's `api` / backend (dictionary or FastAPI model requests).
3. Vinay's `desktop` (Electron IPC or local display results).
4. Installed-application discovery and resolution.

Keeps integration strictly isolated behind this narrow adapter until
team contracts are formally finalized.
"""

import uuid
from typing import Any, Dict, Optional, Union, List
from windows_automation.schemas import (
    ActionRequest,
    ExecutionResult,
    AuthorizationDecision,
    DiscoveryResult,
    ResolutionResult,
    ApplicationRecord,
)
from windows_automation.discovery import ApplicationDiscoverer
from windows_automation.catalogue import ApplicationCatalogue
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.policy import WindowsActionPolicy


class WindowsAutomationAdapter:
    """Adapter bridging external caller models to Windows Automation executor and catalogue."""

    def __init__(
        self,
        executor: Optional[WindowsAutomationExecutor] = None,
        catalogue: Optional[ApplicationCatalogue] = None,
        discoverer: Optional[ApplicationDiscoverer] = None,
        auto_discover: bool = False,
    ):
        self.discoverer = discoverer or ApplicationDiscoverer()
        self.catalogue = catalogue or ApplicationCatalogue()
        if auto_discover:
            self.refresh_catalogue()

        self.policy = WindowsActionPolicy(catalogue=self.catalogue)
        self.executor = executor or WindowsAutomationExecutor(
            policy=self.policy,
            catalogue=self.catalogue,
        )
        if not self.executor.catalogue:
            self.executor.catalogue = self.catalogue

    def refresh_catalogue(self) -> DiscoveryResult:
        """Scan Windows for installed software and populate the application catalogue."""
        discovery_res = self.discoverer.discover_all()
        for app in discovery_res.applications:
            self.catalogue.add_record(app)
        return discovery_res

    def get_catalogue(self) -> ApplicationCatalogue:
        """Access the current application catalogue."""
        return self.catalogue

    def resolve_application(self, query: str) -> ResolutionResult:
        """Resolve an application query against the discovered catalogue."""
        return self.catalogue.resolve(query)

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

        # Attempt to resolve target against catalogue if catalogue has entries
        resolved_record = None
        if self.catalogue.count() > 0 and target:
            resolution = self.catalogue.resolve(target)
            if resolution.status == "resolved":
                resolved_record = resolution.matched_record

        request = ActionRequest(
            action_id=action_id,
            task_id=task_id,
            step_id=step_id,
            action_name=action_name,
            target=target,
            timeout_seconds=timeout_seconds,
            authorization=auth_obj,
            resolved_record=resolved_record,
        )

        return self.executor.execute(request)

    def execute_application_launch(
        self,
        app_query_or_id: str,
        task_id: Optional[str] = None,
        authorization: Optional[Union[AuthorizationDecision, Dict[str, Any]]] = None,
        timeout_seconds: float = 10.0,
    ) -> ExecutionResult:
        """
        Controlled launcher accepting a resolved application identifier or query.
        """
        task_id = task_id or f"task_{uuid.uuid4()}"
        action_id = f"act_{uuid.uuid4()}"

        # Resolve query
        resolution = self.catalogue.resolve(app_query_or_id)
        if resolution.status == "ambiguous":
            return ExecutionResult(
                action_id=action_id,
                task_id=task_id,
                status="failed",
                verification_status="launch_failed",
                error_code="ERR_AMBIGUOUS_TARGET",
                error_message=resolution.reason,
            )
        elif resolution.status == "not_found":
            return ExecutionResult(
                action_id=action_id,
                task_id=task_id,
                status="failed",
                verification_status="launch_failed",
                error_code="ERR_TARGET_NOT_FOUND",
                error_message=resolution.reason,
            )
        elif resolution.status == "unsupported":
            return ExecutionResult(
                action_id=action_id,
                task_id=task_id,
                status="failed",
                verification_status="launch_failed",
                error_code="ERR_TARGET_UNAVAILABLE",
                error_message=resolution.reason,
            )

        matched_record = resolution.matched_record
        auth_obj = None
        if isinstance(authorization, AuthorizationDecision):
            auth_obj = authorization
        elif isinstance(authorization, dict):
            auth_obj = AuthorizationDecision.from_dict(authorization)
        else:
            auth_obj = AuthorizationDecision(
                decision_id=f"dec_{uuid.uuid4()}",
                permission_status="denied",
                reason="Missing authorization.",
            )

        request = ActionRequest(
            action_id=action_id,
            task_id=task_id,
            action_name="open_application",
            target=matched_record.display_name,
            app_id=matched_record.app_id,
            timeout_seconds=timeout_seconds,
            authorization=auth_obj,
            resolved_record=matched_record,
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
