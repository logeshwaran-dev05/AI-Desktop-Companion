"""
Live integration tests for Windows Automation on actual Windows OS.

Tests real subprocess invocation of notepad.exe and live Win32 window
detection via EnumWindows. Safely terminates any spawned Notepad instances
after verification to avoid leaving open windows on the desktop.
"""

import sys
import unittest
from windows_automation.schemas import ActionRequest, AuthorizationDecision
from windows_automation.discovery import ApplicationDiscoverer
from windows_automation.catalogue import ApplicationCatalogue
from windows_automation.policy import WindowsActionPolicy
from windows_automation.verifier import WindowsWindowVerifier
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.adapter import WindowsAutomationAdapter
from ai_engine.schemas.command_schema import PlanStep


@unittest.skipUnless(sys.platform == "win32", "Live Windows automation tests require Windows OS.")
class TestWindowsAutomationLive(unittest.TestCase):

    def setUp(self):
        self.discoverer = ApplicationDiscoverer(
            include_builtins=True,
            include_start_menu=True,
            include_registry=True,
        )
        self.catalogue = ApplicationCatalogue()
        self.policy = WindowsActionPolicy(catalogue=self.catalogue)
        self.verifier = WindowsWindowVerifier()
        self.executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=self.verifier,
            catalogue=self.catalogue,
        )
        self.adapter = WindowsAutomationAdapter(
            executor=self.executor,
            catalogue=self.catalogue,
            discoverer=self.discoverer,
            auto_discover=False,
        )
        self.spawned_pids = []

    def tearDown(self):
        # Clean up any processes spawned during live testing
        for pid in self.spawned_pids:
            try:
                import os, signal
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

    def test_live_01_application_discovery(self):
        """Test real Windows application discovery across registry, start menu, and built-ins."""
        discovery = self.discoverer.discover_all()
        self.assertGreater(discovery.total_discovered, 0)
        self.assertIn("system_builtin", discovery.sources_scanned)

        app_names = [a.display_name.lower() for a in discovery.applications]
        self.assertTrue(any("notepad" in n for n in app_names))

    def test_live_02_catalogue_resolution(self):
        """Test resolving discovered applications in live catalogue."""
        self.adapter.refresh_catalogue()
        catalogue = self.adapter.get_catalogue()
        self.assertGreater(catalogue.count(), 0)

        # Resolve Notepad
        res_notepad = catalogue.resolve("Notepad")
        self.assertEqual(res_notepad.status, "resolved")
        self.assertIsNotNone(res_notepad.matched_record)

        # Resolve non-existent application
        res_missing = catalogue.resolve("DefinitelyNonExistentApp_987654")
        self.assertEqual(res_missing.status, "not_found")

    def test_live_03_notepad_launch_and_verification(self):
        """Test real Notepad launch and Win32 window verification on Windows."""
        auth = AuthorizationDecision(
            decision_id="live-dec-1",
            permission_status="granted",
            requires_user_approval=False,
            approval_reference="live-test-ref",
            reason="Controlled live test of Notepad launch",
        )
        request = ActionRequest(
            action_id="live-act-1",
            task_id="live-task-1",
            action_name="open_application",
            target="Notepad",
            timeout_seconds=8.0,
            authorization=auth,
        )

        result = self.executor.execute(request)

        # Track PID for teardown cleanup
        proc = self.executor.get_active_process("live-act-1")
        if proc and hasattr(proc, "pid"):
            self.spawned_pids.append(proc.pid)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "launch_verified")
        self.assertIsNone(result.error_code)
        self.assertTrue(result.verification.verified)
        self.assertTrue(result.verification.details.get("window_found"))
        self.assertGreater(result.verification.details.get("window_handle", 0), 0)

        # Terminate opened test process cleanly
        self.executor.cancel("live-act-1")

    def test_live_04_controlled_launch_via_catalogue(self):
        """Test controlled launch via resolved catalogue record."""
        self.adapter.refresh_catalogue()
        auth = {
            "decision_id": "live-dec-cat-1",
            "permission_status": "granted",
            "approval_reference": "user_approved",
        }

        result = self.adapter.execute_application_launch("Notepad", authorization=auth, timeout_seconds=8.0)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "launch_verified")
        self.assertTrue(result.verification.verified)

        if result.action_id:
            self.adapter.cancel_action(result.action_id)

    def test_live_05_unallowlisted_target_rejection(self):
        """Test that arbitrary shell commands and unallowlisted targets are rejected."""
        auth = AuthorizationDecision(
            decision_id="live-dec-2",
            permission_status="granted",
            reason="Attempt unapproved app",
        )
        request = ActionRequest(
            action_id="live-act-2",
            task_id="live-task-2",
            action_name="open_application",
            target="powershell -Command Write-Host Dangerous",
            authorization=auth,
        )

        result = self.executor.execute(request)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "ERR_TARGET_NOT_ALLOWLISTED")

    def test_live_06_adapter_with_ai_engine_plan_step(self):
        """Test end-to-end integration: Booviha's PlanStep -> Adapter -> Live Notepad Launch."""
        # Step generated by Booviha's TaskPlanner
        step = PlanStep(
            step_id=1,
            action="open_application",
            target="Notepad",
            depends_on=[],
            expected_outcome="Notepad should open successfully.",
        )

        auth = {
            "decision_id": "adapter-dec-1",
            "permission_status": "granted",
            "requires_user_approval": False,
            "approval_reference": "user-approved",
            "reason": "AI Planner request approved",
        }

        result = self.adapter.execute_plan_step(
            step=step,
            task_id="task-adapter-test",
            authorization=auth,
            timeout_seconds=8.0,
        )

        # Clean up
        if result.action_id:
            self.adapter.cancel_action(result.action_id)

        self.assertEqual(result.status, "completed")
        self.assertTrue(result.verification.verified)
        self.assertEqual(result.verification_status, "launch_verified")


if __name__ == "__main__":
    unittest.main()
