"""
Safe Windows Automation Executor.

Executes allowlisted desktop actions (Notepad, discovered installed applications) with:
1. Strict policy and authorization checking.
2. Dynamic target resolution against the ApplicationCatalogue.
3. Safe subprocess invocation (shell=False, no elevated privileges).
4. Process tracking and active cancellation support.
5. Duplicate request detection and idempotency enforcement.
6. Truthful Windows window & process verification.
7. Structured audit recording with sensitive data redaction.
"""

import os
import subprocess
import time
from typing import Dict, Any, Optional, Callable
from windows_automation.schemas import (
    ActionRequest,
    ExecutionResult,
    VerificationEvidence,
    ApplicationRecord,
    current_iso_timestamp,
)
from windows_automation.policy import WindowsActionPolicy
from windows_automation.verifier import WindowsWindowVerifier
from windows_automation.audit import AuditLogger
from windows_automation.catalogue import ApplicationCatalogue


class WindowsAutomationExecutor:
    """Executes validated and authorized Windows desktop automation actions."""

    def __init__(
        self,
        policy: Optional[WindowsActionPolicy] = None,
        verifier: Optional[WindowsWindowVerifier] = None,
        audit_logger: Optional[AuditLogger] = None,
        catalogue: Optional[ApplicationCatalogue] = None,
        subprocess_runner: Optional[Callable[..., Any]] = None,
    ):
        self.catalogue = catalogue
        self.policy = policy or WindowsActionPolicy(catalogue=self.catalogue)
        if catalogue and not self.policy.catalogue:
            self.policy.catalogue = catalogue
        self.verifier = verifier or WindowsWindowVerifier()
        self.audit_logger = audit_logger or AuditLogger()
        self._subprocess_runner = subprocess_runner or subprocess.Popen

        # Active process tracker: action_id -> dict {"proc": proc, "window_pid": ...}
        self._active_processes: Dict[str, Any] = {}
        # Idempotency cache: idempotency_key -> ExecutionResult
        self._idempotency_cache: Dict[str, ExecutionResult] = {}
        # Cancellation requested set: action_id
        self._cancelled_actions: set = set()

    def execute(self, request: ActionRequest) -> ExecutionResult:
        """
        Execute an automation action safely against policy, verification, and audit standards.
        """
        start_time = time.monotonic()
        started_at = current_iso_timestamp()

        # Step 1: Idempotency check to prevent duplicate executions
        if request.idempotency_key:
            if request.idempotency_key in self._idempotency_cache:
                self.audit_logger.log_event(
                    event_type="duplicate_request_detected",
                    action_id=request.action_id,
                    task_id=request.task_id,
                    summary=f"Duplicate request blocked by idempotency key: {request.idempotency_key}",
                    details={"idempotency_key": request.idempotency_key},
                )
                return ExecutionResult(
                    action_id=request.action_id,
                    task_id=request.task_id,
                    status="failed",
                    verification_status="launch_failed",
                    error_code="ERR_DUPLICATE_REQUEST",
                    error_message=f"Duplicate request detected for idempotency key '{request.idempotency_key}'.",
                    started_at=started_at,
                    completed_at=current_iso_timestamp(),
                    duration_ms=0,
                )

        # Step 2: Validate request format, action, and target against policy and catalogue
        is_valid, err_code, err_msg = self.policy.validate_request(request)
        if not is_valid:
            self.audit_logger.log_event(
                event_type="request_validation_failed",
                action_id=request.action_id,
                task_id=request.task_id,
                summary=f"Validation failed: {err_msg}",
                details={"error_code": err_code, "action_name": request.action_name, "target": request.target},
            )
            return ExecutionResult(
                action_id=request.action_id,
                task_id=request.task_id,
                status="failed",
                verification_status="launch_failed",
                error_code=err_code,
                error_message=err_msg,
                started_at=started_at,
                completed_at=current_iso_timestamp(),
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Step 3: Verify authorization & permissions (never invent approvals)
        is_auth, auth_err_code, auth_err_msg = self.policy.check_authorization(request)
        if not is_auth:
            self.audit_logger.log_event(
                event_type="authorization_check_failed",
                action_id=request.action_id,
                task_id=request.task_id,
                summary=f"Authorization rejected: {auth_err_msg}",
                details={"error_code": auth_err_code},
            )
            return ExecutionResult(
                action_id=request.action_id,
                task_id=request.task_id,
                status="failed",
                verification_status="denied",
                error_code=auth_err_code,
                error_message=auth_err_msg,
                started_at=started_at,
                completed_at=current_iso_timestamp(),
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Step 4: Resolve verified executable path
        executable_path = self.policy.resolve_executable_path(request.target, request=request)
        if not executable_path:
            return ExecutionResult(
                action_id=request.action_id,
                task_id=request.task_id,
                status="failed",
                verification_status="launch_failed",
                error_code="ERR_LAUNCH_FAILED",
                error_message=f"Could not resolve verified executable for target: '{request.target}'.",
                started_at=started_at,
                completed_at=current_iso_timestamp(),
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Step 5: Check pre-launch cancellation checkpoint
        if request.action_id in self._cancelled_actions:
            self.audit_logger.log_event(
                event_type="action_cancelled_pre_launch",
                action_id=request.action_id,
                task_id=request.task_id,
                summary="Action was cancelled prior to launch.",
            )
            return ExecutionResult(
                action_id=request.action_id,
                task_id=request.task_id,
                status="cancelled",
                verification_status="cancelled",
                error_code="ERR_CANCELLED",
                error_message="Action was cancelled before execution started.",
                started_at=started_at,
                completed_at=current_iso_timestamp(),
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Step 6: Safe execution (shell=False, bounded parameters)
        launch_args = [executable_path]
        extra_args = request.parameters.get("args", []) if request.parameters else []
        launch_args.extend([str(a) for a in extra_args])

        self.audit_logger.log_event(
            event_type="launching_process",
            action_id=request.action_id,
            task_id=request.task_id,
            summary=f"Launching application '{request.target}'",
            details={"executable": executable_path, "args": extra_args},
        )

        proc = None
        try:
            # Strictly shell=False to prevent shell injection or arbitrary commands
            proc = self._subprocess_runner(
                launch_args,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._active_processes[request.action_id] = proc
        except Exception as exc:
            self.audit_logger.log_event(
                event_type="launch_failure",
                action_id=request.action_id,
                task_id=request.task_id,
                summary=f"Failed to launch process: {str(exc)}",
                details={"exception": str(exc)},
            )
            return ExecutionResult(
                action_id=request.action_id,
                task_id=request.task_id,
                status="failed",
                verification_status="launch_failed",
                error_code="ERR_LAUNCH_FAILED",
                error_message=f"Process launch failed: {str(exc)}",
                started_at=started_at,
                completed_at=current_iso_timestamp(),
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Step 7: Check post-launch cancellation checkpoint
        if request.action_id in self._cancelled_actions:
            self._terminate_process(proc)
            self._active_processes.pop(request.action_id, None)
            return ExecutionResult(
                action_id=request.action_id,
                task_id=request.task_id,
                status="cancelled",
                verification_status="cancelled",
                error_code="ERR_CANCELLED",
                error_message="Action was cancelled immediately following process launch.",
                started_at=started_at,
                completed_at=current_iso_timestamp(),
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Step 8: Verify Application & Window Readiness (Distinguish process from window)
        def is_alive(pid: int) -> bool:
            return proc.poll() is None

        # Give bounded verification time
        verify_timeout = min(request.timeout_seconds, 10.0)
        evidence = self.verifier.verify_window_readiness(
            pid=proc.pid,
            process_name=os.path.basename(executable_path),
            timeout_seconds=verify_timeout,
            is_process_alive_check=is_alive,
        )

        completed_at = current_iso_timestamp()
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Step 9: Evaluate verification outcome
        if not evidence.verified:
            # Clean up unverified process
            self._terminate_process(proc)
            self._active_processes.pop(request.action_id, None)

            err_code = "ERR_TIMEOUT" if (evidence.verification_status == "timed_out" or "timeout" in evidence.method) else "ERR_VERIFICATION_FAILED"
            reason = evidence.details.get("reason", "Application window verification failed.")

            self.audit_logger.log_event(
                event_type="verification_failed",
                action_id=request.action_id,
                task_id=request.task_id,
                summary=f"Verification failed: {reason}",
                details=evidence.details,
            )

            return ExecutionResult(
                action_id=request.action_id,
                task_id=request.task_id,
                status="failed",
                verification_status=evidence.verification_status,
                error_code=err_code,
                error_message=reason,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                verification=evidence,
                resolved_record=request.resolved_record,
            )

        # Success - Confirmed process and window ready
        window_pid = evidence.details.get("window_pid")
        self._active_processes[request.action_id] = {
            "proc": proc,
            "window_pid": window_pid,
        }

        audit_record = self.audit_logger.log_event(
            event_type="action_completed_verified",
            action_id=request.action_id,
            task_id=request.task_id,
            summary=f"Successfully launched and verified '{request.target}' (PID: {proc.pid})",
            details={
                "process_id": proc.pid,
                "window_pid": window_pid,
                "window_handle": evidence.details.get("window_handle"),
                "window_title": evidence.details.get("window_title"),
            },
        )

        result = ExecutionResult(
            action_id=request.action_id,
            task_id=request.task_id,
            status="completed",
            verification_status="launch_verified",
            error_code=None,
            error_message=None,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            verification=evidence,
            resolved_record=request.resolved_record,
            audit=audit_record,
        )

        # Store in idempotency cache
        if request.idempotency_key:
            self._idempotency_cache[request.idempotency_key] = result

        return result

    def cancel(self, action_id: str) -> bool:
        """
        Request cancellation of an action.
        Terminates the process if running and confirms it has actually stopped.
        """
        self._cancelled_actions.add(action_id)
        entry = self._active_processes.pop(action_id, None)
        if entry:
            proc = entry.get("proc") if isinstance(entry, dict) else entry
            window_pid = entry.get("window_pid") if isinstance(entry, dict) else None
            stopped = self._terminate_process(proc)
            if window_pid and window_pid != getattr(proc, "pid", None):
                self._terminate_pid(window_pid)
            pid_val = getattr(proc, "pid", "unknown")
            self.audit_logger.log_event(
                event_type="process_cancelled_and_terminated",
                action_id=action_id,
                task_id="unknown",
                summary=f"Process for action '{action_id}' was cancelled and terminated (PID: {pid_val}).",
                details={"pid": pid_val, "window_pid": window_pid, "stopped": stopped},
            )
            return stopped
        return True

    def _terminate_pid(self, pid: int) -> bool:
        """Terminate process by PID."""
        if not pid:
            return True
        try:
            import os, signal
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False

    def _terminate_process(self, proc: Any) -> bool:
        """Safely terminate a spawned process and verify exit."""
        if proc is None:
            return True
        try:
            if hasattr(proc, "poll") and proc.poll() is not None:
                return True
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
                return True
            except Exception:
                proc.kill()
                proc.wait(timeout=1.0)
                return True
        except Exception:
            return False

    def is_active(self, action_id: str) -> bool:
        """Check if an action is currently running."""
        entry = self._active_processes.get(action_id)
        proc = entry.get("proc") if isinstance(entry, dict) else entry
        if proc and hasattr(proc, "poll"):
            return proc.poll() is None
        return False

    def get_active_process(self, action_id: str) -> Optional[Any]:
        entry = self._active_processes.get(action_id)
        return entry.get("proc") if isinstance(entry, dict) else entry
