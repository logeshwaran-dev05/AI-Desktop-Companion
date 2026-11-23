"""
Unit tests for Windows Automation module using mocks.

Covers the 10 core safety and behavior scenarios:
1. Valid Notepad launch.
2. Invalid request and unsupported action.
3. Permission denied.
4. Missing approval.
5. Launch failure.
6. Timeout.
7. Process started but verification failed.
8. Cancellation.
9. Repeated or duplicate requests.
10. Audit-log redaction.
"""

import unittest
from unittest.mock import MagicMock, patch
from windows_automation.schemas import (
    ActionRequest,
    AuthorizationDecision,
    VerificationEvidence,
)
from windows_automation.policy import WindowsActionPolicy
from windows_automation.verifier import WindowsWindowVerifier
from windows_automation.audit import AuditLogger
from windows_automation.executor import WindowsAutomationExecutor


class MockProcess:
    """Simulates a subprocess.Popen object."""

    def __init__(self, pid: int = 12345, returncode: int = None):
        self.pid = pid
        self._returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        return self._returncode

    def terminate(self):
        self.terminated = True
        self._returncode = -15

    def kill(self):
        self.killed = True
        self._returncode = -9

    def wait(self, timeout=None):
        return self._returncode


class TestWindowsAutomationMocked(unittest.TestCase):

    def setUp(self):
        self.policy = WindowsActionPolicy()
        self.audit_logger = AuditLogger()

    def _create_authorized_request(
        self,
        action_name: str = "open_application",
        target: str = "Notepad",
        action_id: str = "act-1",
        task_id: str = "task-1",
        idempotency_key: str = None,
        timeout_seconds: float = 2.0,
    ) -> ActionRequest:
        auth = AuthorizationDecision(
            decision_id="dec-1",
            permission_status="granted",
            requires_user_approval=False,
            approval_reference="auth-ref-1",
            reason="Allowlisted Notepad launch approved.",
        )
        return ActionRequest(
            action_id=action_id,
            task_id=task_id,
            action_name=action_name,
            target=target,
            idempotency_key=idempotency_key,
            timeout_seconds=timeout_seconds,
            authorization=auth,
        )

    # 1. Valid Notepad launch
    def test_01_valid_notepad_launch(self):
        mock_proc = MockProcess(pid=9999)
        mock_runner = MagicMock(return_value=mock_proc)

        # Mock window finder returning window info
        def mock_finder(pid):
            return {"hwnd": 54321, "window_title": "Untitled - Notepad", "width": 800, "height": 600}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request()
        result = executor.execute(req)

        self.assertEqual(result.status, "completed")
        self.assertIsNone(result.error_code)
        self.assertTrue(result.verification.verified)
        self.assertEqual(result.verification.details["window_handle"], 54321)
        self.assertEqual(result.verification.details["process_id"], 9999)
        self.assertEqual(result.verification.details["window_title"], "Untitled - Notepad")
        mock_runner.assert_called_once()

    # 2. Invalid request and unsupported action
    def test_02_invalid_request_and_unsupported_action(self):
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
        )

        # Unsupported action
        req_unsupported = self._create_authorized_request(action_name="format_drive")
        res_unsupported = executor.execute(req_unsupported)
        self.assertEqual(res_unsupported.status, "failed")
        self.assertEqual(res_unsupported.error_code, "ERR_UNSUPPORTED_ACTION")

        # Unsupported target (not allowlisted)
        req_bad_target = self._create_authorized_request(target="cmd.exe")
        res_bad_target = executor.execute(req_bad_target)
        self.assertEqual(res_bad_target.status, "failed")
        self.assertEqual(res_bad_target.error_code, "ERR_TARGET_NOT_ALLOWLISTED")

        # Malformed request missing IDs
        req_malformed = ActionRequest(
            action_id="",
            task_id="",
            action_name="open_application",
            target="Notepad",
        )
        res_malformed = executor.execute(req_malformed)
        self.assertEqual(res_malformed.status, "failed")
        self.assertEqual(res_malformed.error_code, "ERR_INVALID_REQUEST")

    # 3. Permission denied
    def test_03_permission_denied(self):
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
        )

        req = self._create_authorized_request()
        # Set permission status to denied
        req.authorization.permission_status = "denied"
        req.authorization.reason = "Restricted administrative policy"

        res = executor.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.error_code, "ERR_PERMISSION_DENIED")
        self.assertIn("denied", res.error_message.lower())

    # 4. Missing approval
    def test_04_missing_approval(self):
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
        )

        req = self._create_authorized_request()
        # Requires user approval but approval_reference is missing
        req.authorization.requires_user_approval = True
        req.authorization.approval_reference = None

        res = executor.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.error_code, "ERR_MISSING_APPROVAL")

    # 5. Launch failure (e.g. executable not found or OS error)
    def test_05_launch_failure(self):
        def failing_runner(*args, **kwargs):
            raise FileNotFoundError("System cannot find notepad.exe")

        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
            subprocess_runner=failing_runner,
        )

        req = self._create_authorized_request()
        res = executor.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.error_code, "ERR_LAUNCH_FAILED")
        self.assertIn("System cannot find", res.error_message)

    # 6. Timeout
    def test_06_timeout(self):
        mock_proc = MockProcess(pid=1111)
        mock_runner = MagicMock(return_value=mock_proc)

        # Window finder never finds window
        def never_finder(pid):
            return None

        verifier = WindowsWindowVerifier(window_finder_override=never_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request(timeout_seconds=0.2)
        res = executor.execute(req)

        self.assertEqual(res.status, "failed")
        self.assertEqual(res.error_code, "ERR_TIMEOUT")
        self.assertFalse(res.verification.verified)
        # Verify unverified process was terminated
        self.assertTrue(mock_proc.terminated)

    # 7. Process started but verification failed (e.g. process crashed or window never appeared)
    def test_07_process_started_but_verification_failed(self):
        # Process starts, but terminates immediately before window appears
        mock_proc = MockProcess(pid=2222, returncode=1)
        mock_runner = MagicMock(return_value=mock_proc)

        def mock_finder(pid):
            return None

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request(timeout_seconds=0.5)
        res = executor.execute(req)

        self.assertEqual(res.status, "failed")
        self.assertFalse(res.verification.verified)
        self.assertFalse(res.verification.details.get("window_found", False))

    # 8. Cancellation
    def test_08_cancellation(self):
        mock_proc = MockProcess(pid=3333)
        mock_runner = MagicMock(return_value=mock_proc)

        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request(action_id="act-cancel-1")

        # Pre-cancel before execution
        executor.cancel("act-cancel-1")
        res = executor.execute(req)

        self.assertEqual(res.status, "cancelled")
        self.assertEqual(res.error_code, "ERR_CANCELLED")
        mock_runner.assert_not_called()

    # 9. Repeated or duplicate requests
    def test_09_duplicate_requests(self):
        mock_proc = MockProcess(pid=4444)
        mock_runner = MagicMock(return_value=mock_proc)

        def mock_finder(pid):
            return {"hwnd": 123, "window_title": "Untitled - Notepad", "width": 800, "height": 600}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        idempotency_key = "task-duplicate:1:open_application"
        req1 = self._create_authorized_request(action_id="act-d1", idempotency_key=idempotency_key)
        req2 = self._create_authorized_request(action_id="act-d2", idempotency_key=idempotency_key)

        res1 = executor.execute(req1)
        self.assertEqual(res1.status, "completed")

        # Second identical request should be rejected as duplicate
        res2 = executor.execute(req2)
        self.assertEqual(res2.status, "failed")
        self.assertEqual(res2.error_code, "ERR_DUPLICATE_REQUEST")
        self.assertEqual(mock_runner.call_count, 1)

    # 10. Audit-log redaction
    def test_10_audit_log_redaction(self):
        logger = AuditLogger()
        record = logger.log_event(
            event_type="test_event",
            action_id="act-redact-1",
            task_id="task-redact-1",
            summary="User authenticated with bearer super_secret_token_12345",
            details={
                "api_key": "secret_api_key_abc",
                "password": "my_password_xyz",
                "normal_param": "Notepad",
                "auth_token": "token: 9876543210abc",
            },
        )

        # Sensitive dictionary keys should be masked
        self.assertEqual(record.details["api_key"], "[REDACTED]")
        self.assertEqual(record.details["password"], "[REDACTED]")
        self.assertEqual(record.details["auth_token"], "[REDACTED]")
        self.assertEqual(record.details["normal_param"], "Notepad")

        # Bearer token substring in summary should be redacted
        self.assertNotIn("super_secret_token_12345", record.redacted_summary)
        self.assertIn("[REDACTED_CREDENTIAL]", record.redacted_summary)

    # 11. URI launch uses os.startfile and succeeds without a direct process handle
    def test_11_settings_uri_launch_uses_startfile(self):
        policy = WindowsActionPolicy()
        policy.load_catalogue_entries([
            {
                "app_id": "settings",
                "app_name": "Windows Settings",
                "executable": "ms-settings:",
                "launch_target": "ms-settings:",
                "launch_type": "uri",
                "application_type": "uri",
                "launch_method": "os.startfile",
                "allowlisted": False,
            }
        ])

        executor = WindowsAutomationExecutor(
            policy=policy,
            audit_logger=self.audit_logger,
            subprocess_runner=MagicMock(),
        )

        req = self._create_authorized_request(
            action_name="open_application",
            target="Windows Settings",
            action_id="act-uri",
            task_id="task-uri",
            idempotency_key="uri-test-key",
        )

        with patch("os.startfile") as mock_startfile:
            result = executor.execute(req)

        self.assertEqual(result.status, "completed")
        self.assertTrue(result.verification.verified)
        mock_startfile.assert_called_once_with("ms-settings:")


if __name__ == "__main__":
    unittest.main()
