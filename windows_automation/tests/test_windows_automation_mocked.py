"""
Unit tests for Windows Automation module using mocks.

Covers all 17 required scenarios:
1. Successful discovery.
2. Duplicate catalogue entries.
3. Missing or inaccessible discovery sources.
4. Empty catalogue versus discovery failure.
5. Valid target resolution.
6. Invalid, missing, and unavailable targets.
7. Successful launch using a controlled test.
8. Launch failure.
9. Permission denied.
10. Missing approval.
11. Cancellation before launch.
12. Cancellation during a supported workflow.
13. Repeated or duplicate requests.
14. Timeout handling where applicable.
15. Verification success.
16. Verification failure or inconclusive evidence.
17. Rejection of arbitrary command strings.
+ Regression tests for existing Notepad & AI Engine PlanStep workflow.
"""

import os
import unittest
from unittest.mock import MagicMock, patch
from windows_automation.schemas import (
    ActionRequest,
    AuthorizationDecision,
    ApplicationRecord,
    DiscoveryResult,
)
from windows_automation.discovery import (
    ApplicationDiscoverer,
    normalize_app_name,
    generate_stable_app_id,
)
from windows_automation.catalogue import ApplicationCatalogue
from windows_automation.policy import WindowsActionPolicy
from windows_automation.verifier import WindowsWindowVerifier
from windows_automation.audit import AuditLogger
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.adapter import WindowsAutomationAdapter


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

    def _create_sample_record(self, name="Test App", exe="C:\\Apps\\test.exe", aliases=None) -> ApplicationRecord:
        return ApplicationRecord(
            app_id=generate_stable_app_id(name),
            display_name=name,
            normalized_name=normalize_app_name(name),
            executable_path=exe,
            source="test_source",
            status="available",
            aliases=aliases or [normalize_app_name(name)],
        )

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
            reason="Allowlisted launch approved.",
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

    # 1. Successful discovery
    def test_01_successful_discovery(self):
        discoverer = ApplicationDiscoverer(
            include_builtins=True,
            include_start_menu=False,
            include_registry=False,
        )
        result = discoverer.discover_all()

        self.assertIsInstance(result, DiscoveryResult)
        self.assertGreater(result.total_discovered, 0)
        self.assertIn("system_builtin", result.sources_scanned)
        app_names = [a.display_name for a in result.applications]
        self.assertIn("Notepad", app_names)

    # 2. Duplicate catalogue entries
    def test_02_duplicate_catalogue_entries(self):
        catalogue = ApplicationCatalogue()
        rec1 = self._create_sample_record("Chrome", "C:\\Program Files\\Google\\Chrome\\chrome.exe", ["chrome"])
        rec2 = self._create_sample_record("Google Chrome", "C:\\Program Files\\Google\\Chrome\\chrome.exe", ["google chrome", "chrome"])

        catalogue.add_record(rec1)
        catalogue.add_record(rec2)

        # Both records are searchable, resolving 'Google Chrome' resolves uniquely without error
        res = catalogue.resolve("Google Chrome", verify_existence=False)
        self.assertEqual(res.status, "resolved")
        self.assertEqual(res.matched_record.display_name, "Google Chrome")

    # 3. Missing or inaccessible discovery sources
    def test_03_missing_or_inaccessible_discovery_sources(self):
        discoverer = ApplicationDiscoverer(
            include_builtins=False,
            include_start_menu=False,
            include_registry=False,
            custom_search_dirs=["C:\\NonExistentPath_xyz123"],
        )
        result = discoverer.discover_all()
        # Should complete cleanly without uncaught exception
        self.assertEqual(result.total_discovered, 0)
        self.assertIn("custom:C:\\NonExistentPath_xyz123", result.sources_scanned)

    # 4. Empty catalogue versus discovery failure
    def test_04_empty_catalogue_vs_discovery_failure(self):
        empty_catalogue = ApplicationCatalogue([], include_builtins=False)
        self.assertEqual(empty_catalogue.count(), 0)

        res = empty_catalogue.resolve("AnyApp")
        self.assertEqual(res.status, "not_found")
        self.assertIn("No installed application found", res.reason)

    # 5. Valid target resolution
    def test_05_valid_target_resolution(self):
        rec = self._create_sample_record("Slack", "C:\\Users\\test\\slack.exe", ["slack", "team chat"])
        catalogue = ApplicationCatalogue([rec])

        # By exact display name
        res1 = catalogue.resolve("Slack", verify_existence=False)
        self.assertEqual(res1.status, "resolved")
        self.assertEqual(res1.matched_record.app_id, "app_slack")

        # By alias
        res2 = catalogue.resolve("team chat", verify_existence=False)
        self.assertEqual(res2.status, "resolved")

        # By app_id
        res3 = catalogue.resolve("app_slack", verify_existence=False)
        self.assertEqual(res3.status, "resolved")

    # 6. Invalid, missing, and unavailable targets
    def test_06_invalid_missing_unavailable_targets(self):
        rec1 = self._create_sample_record("Visual Studio", "C:\\VS\\devenv.exe", ["vs"])
        rec2 = self._create_sample_record("Visual Studio Code", "C:\\VSCode\\code.exe", ["vscode", "vs"])
        catalogue = ApplicationCatalogue([rec1, rec2])

        # Missing target
        res_missing = catalogue.resolve("Photoshop")
        self.assertEqual(res_missing.status, "not_found")

        # Ambiguous target (both share alias 'vs')
        res_ambiguous = catalogue.resolve("vs")
        self.assertEqual(res_ambiguous.status, "ambiguous")
        self.assertEqual(len(res_ambiguous.candidates), 2)

        # Empty query
        res_empty = catalogue.resolve("")
        self.assertEqual(res_empty.status, "not_found")

    # 7. Successful launch using a controlled test
    def test_07_successful_controlled_launch(self):
        mock_proc = MockProcess(pid=8888)
        mock_runner = MagicMock(return_value=mock_proc)

        def mock_finder(pid, name=None):
            return {"hwnd": 54321, "window_title": "Untitled - Notepad", "width": 800, "height": 600}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request(target="Notepad")
        result = executor.execute(req)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "launch_verified")
        self.assertTrue(result.verification.verified)
        self.assertEqual(result.verification.details["window_handle"], 54321)
        mock_runner.assert_called_once()

    # 8. Launch failure
    def test_08_launch_failure(self):
        def failing_runner(*args, **kwargs):
            raise OSError("Subprocess failed to spawn")

        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
            subprocess_runner=failing_runner,
        )

        req = self._create_authorized_request()
        res = executor.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.verification_status, "launch_failed")
        self.assertEqual(res.error_code, "ERR_LAUNCH_FAILED")

    # 9. Permission denied
    def test_09_permission_denied(self):
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
        )

        req = self._create_authorized_request()
        req.authorization.permission_status = "denied"
        req.authorization.reason = "Explicit policy denial"

        res = executor.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.verification_status, "denied")
        self.assertEqual(res.error_code, "ERR_PERMISSION_DENIED")

    # 10. Missing approval
    def test_10_missing_approval(self):
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
        )

        req = self._create_authorized_request()
        req.authorization.requires_user_approval = True
        req.authorization.approval_reference = None

        res = executor.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.error_code, "ERR_MISSING_APPROVAL")

    # 11. Cancellation before launch
    def test_11_cancellation_before_launch(self):
        mock_runner = MagicMock()
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request(action_id="act-cancel-pre")
        executor.cancel("act-cancel-pre")
        res = executor.execute(req)

        self.assertEqual(res.status, "cancelled")
        self.assertEqual(res.verification_status, "cancelled")
        self.assertEqual(res.error_code, "ERR_CANCELLED")
        mock_runner.assert_not_called()

    # 12. Cancellation during a supported workflow
    def test_12_cancellation_during_supported_workflow(self):
        mock_proc = MockProcess(pid=9999)
        mock_runner = MagicMock(return_value=mock_proc)

        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        executor._active_processes["act-run-1"] = mock_proc
        stopped = executor.cancel("act-run-1")

        self.assertTrue(stopped)
        self.assertTrue(mock_proc.terminated)

    # 13. Repeated or duplicate requests
    def test_13_duplicate_requests(self):
        mock_proc = MockProcess(pid=7777)
        mock_runner = MagicMock(return_value=mock_proc)

        def mock_finder(pid, name=None):
            return {"hwnd": 123, "window_title": "Notepad", "width": 800, "height": 600}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        idempotency_key = "task-dup:1:open_application:Notepad"
        req1 = self._create_authorized_request(action_id="act-d1", idempotency_key=idempotency_key)
        req2 = self._create_authorized_request(action_id="act-d2", idempotency_key=idempotency_key)

        res1 = executor.execute(req1)
        self.assertEqual(res1.status, "completed")

        res2 = executor.execute(req2)
        self.assertEqual(res2.status, "failed")
        self.assertEqual(res2.error_code, "ERR_DUPLICATE_REQUEST")
        self.assertEqual(mock_runner.call_count, 1)

    # 14. Timeout handling where applicable
    def test_14_timeout_handling(self):
        # Process starts, stays alive, but window never appears within timeout deadline
        mock_proc = MockProcess(pid=6666, returncode=None)
        mock_runner = MagicMock(return_value=mock_proc)

        def never_finder(pid, name=None):
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
        self.assertEqual(res.verification_status, "timed_out")

    # 15. Verification success
    def test_15_verification_success(self):
        verifier = WindowsWindowVerifier(
            window_finder_override=lambda pid, name=None: {
                "hwnd": 9876,
                "window_title": "Notepad",
                "width": 640,
                "height": 480,
            }
        )
        evidence = verifier.verify_window_readiness(5555, "notepad.exe", timeout_seconds=1.0)

        self.assertTrue(evidence.verified)
        self.assertEqual(evidence.verification_status, "launch_verified")
        self.assertEqual(evidence.details["window_handle"], 9876)

    # 16. Verification failure or inconclusive evidence
    def test_16_verification_inconclusive(self):
        # Process crashed before window could open
        mock_proc = MockProcess(pid=4444, returncode=1)
        verifier = WindowsWindowVerifier(window_finder_override=lambda pid, name=None: None)

        evidence = verifier.verify_window_readiness(
            pid=4444,
            process_name="tool.exe",
            timeout_seconds=0.3,
            is_process_alive_check=lambda p: False,
        )

        self.assertFalse(evidence.verified)
        self.assertEqual(evidence.verification_status, "launch_failed")
        self.assertFalse(evidence.details["process_alive"])

    # 17. Rejection of arbitrary command strings
    def test_17_rejection_of_arbitrary_command_strings(self):
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
        )

        dangerous_targets = [
            "powershell -NoProfile -Command Write-Host bad",
            "cmd.exe /c del important.txt",
            "notepad.exe & calc.exe",
            "test_script.bat",
            "malicious.vbs",
            "evil.ps1",
            "../../escape.exe",
        ]

        for dt in dangerous_targets:
            req = self._create_authorized_request(target=dt)
            res = executor.execute(req)
            self.assertEqual(res.status, "failed", f"Failed to reject dangerous target: {dt}")
            self.assertEqual(res.error_code, "ERR_TARGET_NOT_ALLOWLISTED")

    # 18. Audit log redaction
    def test_18_audit_log_redaction(self):
        logger = AuditLogger()
        record = logger.log_event(
            event_type="auth_event",
            action_id="act-red-1",
            task_id="task-red-1",
            summary="User bearer secret_token_xyz authenticated",
            details={
                "password": "super_secret_pw",
                "api_key": "secret_key_123",
                "normal": "Notepad",
            },
        )

        self.assertEqual(record.details["password"], "[REDACTED]")
        self.assertEqual(record.details["api_key"], "[REDACTED]")
        self.assertEqual(record.details["normal"], "Notepad")
        self.assertNotIn("secret_token_xyz", record.redacted_summary)

    # 19. Regression tests: existing Notepad & PlanStep adapter workflow
    def test_19_regression_notepad_and_ai_plan_step(self):
        mock_proc = MockProcess(pid=3333)
        mock_runner = MagicMock(return_value=mock_proc)

        def mock_finder(pid, name=None):
            return {"hwnd": 111, "window_title": "Untitled - Notepad", "width": 800, "height": 600}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )
        adapter = WindowsAutomationAdapter(executor=executor)

        from ai_engine.schemas.command_schema import PlanStep

        step = PlanStep(
            step_id=1,
            action="open_application",
            target="Notepad",
            expected_outcome="Notepad should open.",
        )
        auth = {
            "decision_id": "dec-reg-1",
            "permission_status": "granted",
            "approval_reference": "user_approved",
        }

        res = adapter.execute_plan_step(step, "task-reg-1", auth)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.verification_status, "launch_verified")
        self.assertTrue(res.verification.verified)


if __name__ == "__main__":
    unittest.main()
