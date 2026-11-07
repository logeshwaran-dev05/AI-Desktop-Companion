"""
Unit tests for Windows Automation module using mocks.

Covers all 15 required core scenarios:
1. Application discovery across sources (Registry, Start Menu, Builtins, App Paths).
2. Duplicate applications handling & deduplication.
3. Missing applications.
4. Invalid targets & script extensions.
5. Normal EXE launch.
6. Start Menu shortcut launch.
7. Packaged application launch (AppX / Execution Alias).
8. Alias matching and whitespace handling.
9. Ambiguous application names.
10. Launch failures & diagnostics.
11. Verification success and failure / timeout.
12. Permission and safety behavior (denials, arbitrary commands).
13. Repeated requests / idempotency deduplication.
14. Existing typed-command regression (Notepad).
15. Integration with the existing workflow (Booviha's PlanStep adapter).
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

    def _create_sample_record(
        self,
        name="Test App",
        exe="C:\\Apps\\test.exe",
        aliases=None,
        app_type="executable",
        launch_method="subprocess_executable",
        shortcut_path=None,
    ) -> ApplicationRecord:
        return ApplicationRecord(
            app_id=generate_stable_app_id(name),
            display_name=name,
            normalized_name=normalize_app_name(name),
            executable_path=exe,
            source="test_source",
            app_type=app_type,
            status="available",
            launch_method=launch_method,
            shortcut_path=shortcut_path,
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

    # 1. Application discovery
    def test_01_application_discovery(self):
        discoverer = ApplicationDiscoverer(
            include_builtins=True,
            include_start_menu=False,
            include_registry=False,
            include_app_paths=False,
            include_packaged_apps=False,
        )
        result = discoverer.discover_all()

        self.assertIsInstance(result, DiscoveryResult)
        self.assertGreater(result.total_discovered, 0)
        self.assertIn("system_builtin", result.sources_scanned)
        app_names = [a.display_name for a in result.applications]
        self.assertIn("Notepad", app_names)
        self.assertIn("Calculator", app_names)

    # 2. Duplicate applications
    def test_02_duplicate_applications(self):
        catalogue = ApplicationCatalogue([], include_builtins=False)
        rec1 = self._create_sample_record("Chrome", "C:\\Program Files\\Google\\Chrome\\chrome.exe", ["chrome"])
        rec2 = self._create_sample_record("Google Chrome", "C:\\Program Files\\Google\\Chrome\\chrome.exe", ["google chrome", "chrome"])

        catalogue.add_record(rec1)
        catalogue.add_record(rec2)

        res = catalogue.resolve("Google Chrome", verify_existence=False)
        self.assertEqual(res.status, "resolved")
        self.assertEqual(res.matched_record.display_name, "Google Chrome")

    # 3. Missing applications
    def test_03_missing_applications(self):
        catalogue = ApplicationCatalogue([], include_builtins=False)
        res = catalogue.resolve("CompletelyFakeApp_99999")
        self.assertEqual(res.status, "not_found")
        self.assertIn("No installed application found", res.reason)

    # 4. Invalid targets
    def test_04_invalid_targets(self):
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
        )

        # Prohibited script extension
        req1 = self._create_authorized_request(target="script.bat")
        res1 = executor.execute(req1)
        self.assertEqual(res1.status, "failed")
        self.assertEqual(res1.error_code, "ERR_TARGET_NOT_ALLOWLISTED")

        # Dangerous command injection
        req2 = self._create_authorized_request(target="notepad.exe & calc.exe")
        res2 = executor.execute(req2)
        self.assertEqual(res2.status, "failed")
        self.assertEqual(res2.error_code, "ERR_TARGET_NOT_ALLOWLISTED")

    # 5. Normal EXE launch
    def test_05_exe_launch(self):
        mock_proc = MockProcess(pid=1001)
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

    # 6. Start Menu shortcut launch
    def test_06_start_menu_shortcut_launch(self):
        mock_launcher = MagicMock()
        rec = self._create_sample_record(
            name="Access",
            exe="",
            app_type="shortcut",
            launch_method="start_menu_shortcut",
            shortcut_path="C:\\Shortcuts\\Access.lnk",
        )
        catalogue = ApplicationCatalogue([rec], include_builtins=False)

        def mock_finder(pid, name=None):
            return {"hwnd": 777, "window_title": "Microsoft Access", "width": 1024, "height": 768}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            catalogue=catalogue,
            verifier=verifier,
            audit_logger=self.audit_logger,
            shortcut_launcher=mock_launcher,
        )

        req = self._create_authorized_request(target="Access")
        req.resolved_record = rec  # Pre-resolved record for mocked shortcut

        with patch("os.path.exists", return_value=True):
            result = executor.execute(req)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "launch_verified")
        mock_launcher.assert_called_once_with("C:\\Shortcuts\\Access.lnk")

    # 7. Packaged application launch (AppX / Execution Alias)
    def test_07_packaged_app_launch(self):
        mock_proc = MockProcess(pid=2002)
        mock_runner = MagicMock(return_value=mock_proc)

        rec = self._create_sample_record(
            name="Windows Terminal",
            exe="C:\\Users\\test\\AppData\\Local\\Microsoft\\WindowsApps\\wt.exe",
            app_type="packaged_app",
            launch_method="subprocess_executable",
        )
        catalogue = ApplicationCatalogue([rec], include_builtins=False)

        def mock_finder(pid, name=None):
            return {"hwnd": 888, "window_title": "Windows Terminal", "width": 800, "height": 600}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            catalogue=catalogue,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request(target="Windows Terminal")
        req.resolved_record = rec  # Pre-resolved record for mocked packaged app
        result = executor.execute(req)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "launch_verified")
        mock_runner.assert_called_once()

    # 8. Alias matching and extra whitespace
    def test_08_alias_matching_and_spaces(self):
        rec = self._create_sample_record("Google Chrome", "C:\\Chrome\\chrome.exe", ["chrome", "web browser"])
        catalogue = ApplicationCatalogue([rec], include_builtins=False)

        # Match alias with extra spaces and uppercase
        res = catalogue.resolve("   CHROME   ", verify_existence=False)
        self.assertEqual(res.status, "resolved")
        self.assertEqual(res.matched_record.display_name, "Google Chrome")

        # Second alias
        res2 = catalogue.resolve("Web Browser", verify_existence=False)
        self.assertEqual(res2.status, "resolved")

    # 9. Ambiguous application names
    def test_09_ambiguous_application_names(self):
        rec1 = self._create_sample_record("Visual Studio", "C:\\VS\\devenv.exe", ["vs"])
        rec2 = self._create_sample_record("Visual Studio Code", "C:\\VSCode\\code.exe", ["vs", "code"])
        catalogue = ApplicationCatalogue([rec1, rec2], include_builtins=False)

        res = catalogue.resolve("vs")
        self.assertEqual(res.status, "ambiguous")
        self.assertEqual(len(res.candidates), 2)
        self.assertIn("matches multiple applications", res.reason)

    # 10. Launch failures and diagnostics
    def test_10_launch_failures_and_diagnostics(self):
        def failing_runner(*args, **kwargs):
            raise OSError("Subprocess access denied or corrupted binary")

        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
            subprocess_runner=failing_runner,
        )

        req = self._create_authorized_request()
        res = executor.execute(req)

        self.assertEqual(res.status, "failed")
        self.assertEqual(res.error_code, "ERR_LAUNCH_FAILED")
        self.assertIsNotNone(res.diagnostics)
        self.assertEqual(res.diagnostics.failing_stage, "launch_spawn")
        self.assertIn("Subprocess access denied", res.diagnostics.exception_details)

    # 11. Verification success and failure / timeout
    def test_11_verification_success_and_timeout(self):
        # Verification Success
        verifier = WindowsWindowVerifier(
            window_finder_override=lambda pid, name=None: {
                "hwnd": 999,
                "window_title": "Notepad",
                "width": 640,
                "height": 480,
            }
        )
        ev_success = verifier.verify_window_readiness(1234, "notepad.exe", timeout_seconds=1.0)
        self.assertTrue(ev_success.verified)
        self.assertEqual(ev_success.verification_status, "launch_verified")

        # Verification Timeout
        mock_proc = MockProcess(pid=4321, returncode=None)
        mock_runner = MagicMock(return_value=mock_proc)
        verifier_timeout = WindowsWindowVerifier(window_finder_override=lambda pid, name=None: None)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier_timeout,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request(timeout_seconds=0.2)
        res = executor.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.error_code, "ERR_TIMEOUT")
        self.assertEqual(res.verification_status, "timed_out")
        self.assertEqual(res.diagnostics.failing_stage, "verification")

    # 12. Permission and safety behavior
    def test_12_permission_and_safety_behavior(self):
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            audit_logger=self.audit_logger,
        )

        # Policy explicitly denied
        req_denied = self._create_authorized_request()
        req_denied.authorization.permission_status = "denied"
        req_denied.authorization.reason = "Restricted workstation profile"
        res_denied = executor.execute(req_denied)

        self.assertEqual(res_denied.status, "failed")
        self.assertEqual(res_denied.verification_status, "denied")
        self.assertEqual(res_denied.error_code, "ERR_PERMISSION_DENIED")

        # Arbitrary shell command
        req_shell = self._create_authorized_request(target="powershell -Command Write-Host Bad")
        res_shell = executor.execute(req_shell)
        self.assertEqual(res_shell.status, "failed")
        self.assertEqual(res_shell.error_code, "ERR_TARGET_NOT_ALLOWLISTED")

    # 13. Repeated requests / idempotency
    def test_13_repeated_requests_idempotency(self):
        mock_proc = MockProcess(pid=5005)
        mock_runner = MagicMock(return_value=mock_proc)

        def mock_finder(pid, name=None):
            return {"hwnd": 505, "window_title": "Notepad", "width": 800, "height": 600}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        key = "task-dup:1:open_application:Notepad"
        req1 = self._create_authorized_request(action_id="act-d1", idempotency_key=key)
        req2 = self._create_authorized_request(action_id="act-d2", idempotency_key=key)

        res1 = executor.execute(req1)
        self.assertEqual(res1.status, "completed")

        res2 = executor.execute(req2)
        self.assertEqual(res2.status, "failed")
        self.assertEqual(res2.error_code, "ERR_DUPLICATE_REQUEST")
        self.assertEqual(mock_runner.call_count, 1)

    # 14. Existing typed-command regression (Notepad)
    def test_14_existing_typed_command_regression(self):
        mock_proc = MockProcess(pid=6006)
        mock_runner = MagicMock(return_value=mock_proc)

        def mock_finder(pid, name=None):
            return {"hwnd": 606, "window_title": "Untitled - Notepad", "width": 800, "height": 600}

        verifier = WindowsWindowVerifier(window_finder_override=mock_finder)
        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=verifier,
            audit_logger=self.audit_logger,
            subprocess_runner=mock_runner,
        )

        req = self._create_authorized_request(target="Notepad")
        res = executor.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.verification_status, "launch_verified")
        self.assertTrue(res.verification.verified)

    # 15. Integration with the existing workflow (Booviha's PlanStep adapter)
    def test_15_integration_with_existing_workflow(self):
        mock_proc = MockProcess(pid=7007)
        mock_runner = MagicMock(return_value=mock_proc)

        def mock_finder(pid, name=None):
            return {"hwnd": 707, "window_title": "Untitled - Notepad", "width": 800, "height": 600}

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
            expected_outcome="Notepad opens.",
        )
        res = adapter.execute_plan_step(step, "task-workflow-1")

        self.assertEqual(res.status, "completed")
        self.assertEqual(res.verification_status, "launch_verified")
        self.assertTrue(res.verification.verified)


if __name__ == "__main__":
    unittest.main()
