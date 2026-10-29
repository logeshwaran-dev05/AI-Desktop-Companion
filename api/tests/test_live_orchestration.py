"""
Live Windows end-to-end integration tests for Backend Orchestrator.

Tests full execution path:
User Command ("Open Notepad")
-> TaskPlanner
-> PermissionEvaluator
-> WindowsAutomationAdapter
-> Real Notepad process spawn and Win32 EnumWindows verification
-> Clean process teardown
"""

import sys
import unittest

from api.orchestrator import TaskOrchestrator
from windows_automation.adapter import WindowsAutomationAdapter


@unittest.skipUnless(sys.platform == "win32", "Live orchestration requires Windows OS.")
class TestLiveOrchestration(unittest.TestCase):
    """Verify live end-to-end execution of 'Open Notepad' workflow."""

    def setUp(self):
        self.adapter = WindowsAutomationAdapter()
        self.orchestrator = TaskOrchestrator(adapter=self.adapter)
        self.actions_to_clean = []

    def tearDown(self):
        # Cancel any actions to ensure no open windows remain
        for action_id in self.actions_to_clean:
            try:
                self.adapter.cancel_action(action_id)
            except Exception:
                pass

    def test_live_open_notepad_command_orchestration(self):
        """End-to-end test of command planning, allowlisting, execution, and verification."""
        task = self.orchestrator.run_command("Open Notepad", timeout_seconds=8.0)

        # Track for cleanup
        if task.get("result") and task["result"].get("action_id"):
            self.actions_to_clean.append(task["result"]["action_id"])

        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["intent"], "open_application")
        self.assertIsNotNone(task["result"])
        self.assertTrue(task["verification"]["verified"])
        self.assertEqual(
            task["verification"]["details"].get("process_name"),
            "notepad.exe",
        )
        self.assertTrue(task["verification"]["details"].get("window_found"))
        self.assertGreater(
            task["verification"]["details"].get("window_handle", 0),
            0,
        )

        # Clean up
        if task["result"].get("action_id"):
            self.adapter.cancel_action(task["result"]["action_id"])


if __name__ == "__main__":
    unittest.main()
