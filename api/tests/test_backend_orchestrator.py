"""
Unit tests for Task Orchestrator, State Machine, and Permission Evaluator.
"""

import unittest
from unittest.mock import MagicMock

from api.orchestrator import (
    PermissionEvaluator,
    TaskOrchestrator,
    TaskStateMachine,
)
from windows_automation.schemas import (
    AuditRecord,
    ExecutionResult,
    VerificationEvidence,
)


class TestTaskStateMachine(unittest.TestCase):
    """Verify deterministic state machine transitions and invalid transition blocks."""

    def test_valid_transitions(self):
        # pending -> running -> completed
        task = {"status": "pending"}
        TaskStateMachine.transition(task, "running")
        self.assertEqual(task["status"], "running")
        TaskStateMachine.transition(task, "completed")
        self.assertEqual(task["status"], "completed")

        # pending -> requires_approval -> running -> completed
        task2 = {"status": "pending"}
        TaskStateMachine.transition(task2, "requires_approval")
        self.assertEqual(task2["status"], "requires_approval")
        TaskStateMachine.transition(task2, "running")
        self.assertEqual(task2["status"], "running")

        # pending -> cancelled
        task3 = {"status": "pending"}
        TaskStateMachine.transition(task3, "cancelled")
        self.assertEqual(task3["status"], "cancelled")

        # running -> cancelled
        task4 = {"status": "running"}
        TaskStateMachine.transition(task4, "cancelled")
        self.assertEqual(task4["status"], "cancelled")

        # running -> failed
        task5 = {"status": "running"}
        TaskStateMachine.transition(task5, "failed")
        self.assertEqual(task5["status"], "failed")

    def test_invalid_transitions_raise_value_error(self):
        # Direct jump pending -> completed (must go through running)
        task = {"status": "pending"}
        with self.assertRaises(ValueError):
            TaskStateMachine.transition(task, "completed")

        # Terminal state completed -> running
        completed_task = {"status": "completed"}
        with self.assertRaises(ValueError):
            TaskStateMachine.transition(completed_task, "running")

        # Terminal state failed -> running
        failed_task = {"status": "failed"}
        with self.assertRaises(ValueError):
            TaskStateMachine.transition(failed_task, "running")

        # Terminal state cancelled -> running
        cancelled_task = {"status": "cancelled"}
        with self.assertRaises(ValueError):
            TaskStateMachine.transition(cancelled_task, "running")


class TestPermissionEvaluator(unittest.TestCase):
    """Verify explicit authorization and catalogue permission checks."""

    def setUp(self):
        self.evaluator = PermissionEvaluator()

    def test_notepad_direct_launch_granted(self):
        auth = self.evaluator.evaluate("task-1", "open_application", "Notepad")
        self.assertEqual(auth.permission_status, "granted")
        self.assertFalse(auth.requires_user_approval)
        self.assertEqual(auth.approval_reference, "user_auto_allowlist_v1")

    def test_notepad_exe_direct_launch_granted(self):
        auth = self.evaluator.evaluate("task-1", "open_application", "notepad.exe")
        self.assertEqual(auth.permission_status, "granted")
        self.assertFalse(auth.requires_user_approval)

    def test_catalogue_application_requires_approval(self):
        auth = self.evaluator.evaluate("task-1", "open_application", "Calculator")
        self.assertEqual(auth.permission_status, "requires_approval")
        self.assertTrue(auth.requires_user_approval)
        self.assertIsNone(auth.approval_reference)

    def test_chrome_requires_approval(self):
        auth = self.evaluator.evaluate("task-1", "open_application", "Google Chrome")
        self.assertEqual(auth.permission_status, "requires_approval")
        self.assertTrue(auth.requires_user_approval)

    def test_unsupported_action_denied(self):
        auth = self.evaluator.evaluate("task-1", "delete_file", "Notepad")
        self.assertEqual(auth.permission_status, "denied")

    def test_unknown_target_denied(self):
        auth = self.evaluator.evaluate("task-1", "open_application", "UnknownApp")
        self.assertEqual(auth.permission_status, "denied")

    def test_empty_target_denied(self):
        auth = self.evaluator.evaluate("task-1", "open_application", "")
        self.assertEqual(auth.permission_status, "denied")


class TestTaskOrchestrator(unittest.TestCase):
    """Verify task orchestration, planning integration, adapter dispatch, and cancellation."""

    def setUp(self):
        self.tasks_store = {}
        self.mock_adapter = MagicMock()
        self.orchestrator = TaskOrchestrator(
            adapter=self.mock_adapter,
            tasks=self.tasks_store,
        )

    def test_create_task_classic(self):
        task = self.orchestrator.create_task(
            title="My Task",
            description="Testing task creation",
        )
        self.assertTrue(task["task_id"].startswith("task_"))
        self.assertEqual(task["title"], "My Task")
        self.assertEqual(task["status"], "pending")
        self.assertIn(task["task_id"], self.tasks_store)

    def test_create_task_with_command(self):
        task = self.orchestrator.create_task(
            title="Launch Notepad",
            command="Open Notepad",
        )
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["intent"], "open_application")
        self.assertEqual(len(task["steps"]), 1)
        self.assertEqual(task["steps"][0]["target"], "Notepad")

    def test_create_task_unsupported_command(self):
        task = self.orchestrator.create_task(
            title="Unsupported",
            command="Delete everything",
        )
        self.assertEqual(task["status"], "failed")
        self.assertIn("not currently supported", task["message"])

    def test_execute_task_notepad_success(self):
        # Setup mock adapter to return a completed execution result
        mock_evidence = VerificationEvidence(
            verified=True,
            method="win32_window_and_process_polling",
            details={"process_name": "notepad.exe", "window_found": True, "window_handle": 12345},
        )
        mock_audit = AuditRecord(
            event_type="action_completed_verified",
            action_id="act-123",
            task_id="task-123",
            redacted_summary="Launched Notepad",
        )
        mock_result = ExecutionResult(
            action_id="act-123",
            task_id="task-123",
            status="completed",
            duration_ms=150,
            verification=mock_evidence,
            audit=mock_audit,
        )
        self.mock_adapter.execute_plan_step.return_value = mock_result

        task = self.orchestrator.create_task(
            title="Open Notepad",
            command="Open Notepad",
        )
        result = self.orchestrator.execute_task(task["task_id"])

        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(result["result"])
        self.assertTrue(result["verification"]["verified"])
        self.assertEqual(result["verification"]["details"]["window_handle"], 12345)
        self.mock_adapter.execute_plan_step.assert_called_once()

    def test_execute_task_requires_approval(self):
        # Calculator is in the catalogue but requires approval
        task = self.orchestrator.create_task(
            title="Open Calculator",
            command="Open Calculator",
        )
        result = self.orchestrator.execute_task(task["task_id"])

        self.assertEqual(result["status"], "requires_approval")
        self.assertIn("requires explicit user approval", result["message"])
        self.mock_adapter.execute_plan_step.assert_not_called()

    def test_approve_task_and_execute(self):
        # Calculator task
        task = self.orchestrator.create_task(
            title="Open Calculator",
            command="Open Calculator",
        )
        self.orchestrator.execute_task(task["task_id"])
        self.assertEqual(task["status"], "requires_approval")

        # Mock adapter outcome
        mock_result = ExecutionResult(
            action_id="act-calc",
            task_id=task["task_id"],
            status="completed",
            verification=VerificationEvidence(verified=True),
        )
        self.mock_adapter.execute_plan_step.return_value = mock_result

        # User approves
        approved_task = self.orchestrator.approve_task(
            task["task_id"],
            approval_reference="user_approved_calc_123",
        )
        self.assertEqual(approved_task["status"], "completed")
        self.assertEqual(
            approved_task["authorization"]["approval_reference"],
            "user_approved_calc_123",
        )
        self.mock_adapter.execute_plan_step.assert_called_once()

    def test_cancel_pending_task(self):
        task = self.orchestrator.create_task(
            title="Task to cancel",
            command="Open Notepad",
        )
        self.assertEqual(task["status"], "pending")

        cancelled = self.orchestrator.cancel_task(task["task_id"])
        self.assertEqual(cancelled["status"], "cancelled")

    def test_cancel_running_task(self):
        task = self.orchestrator.create_task(title="Running Task")
        task["status"] = "running"
        task["active_action_id"] = "act-active-123"

        cancelled = self.orchestrator.cancel_task(task["task_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.mock_adapter.cancel_action.assert_called_once_with("act-active-123")

    def test_cancel_completed_task_raises(self):
        task = self.orchestrator.create_task(title="Completed Task")
        task["status"] = "completed"

        with self.assertRaises(ValueError):
            self.orchestrator.cancel_task(task["task_id"])

    def test_catalogue_inspection(self):
        catalogue = self.orchestrator.get_catalogue()
        self.assertGreaterEqual(len(catalogue), 7)

        # Notepad should be marked allowlisted=True
        notepad_item = self.orchestrator.get_app_by_id("notepad")
        self.assertIsNotNone(notepad_item)
        self.assertEqual(notepad_item["app_name"], "Notepad")
        self.assertTrue(notepad_item["allowlisted"])

        # Calculator should be allowlisted=False
        calc_item = self.orchestrator.get_app_by_id("calculator")
        self.assertIsNotNone(calc_item)
        self.assertFalse(calc_item["allowlisted"])

        # Missing app returns None
        missing = self.orchestrator.get_app_by_id("non_existent_app")
        self.assertIsNone(missing)

    def test_run_command_notepad_one_shot(self):
        mock_result = ExecutionResult(
            action_id="act-one-shot",
            task_id="task-one-shot",
            status="completed",
            duration_ms=120,
            verification=VerificationEvidence(verified=True),
        )
        self.mock_adapter.execute_plan_step.return_value = mock_result

        task = self.orchestrator.run_command("Please open Notepad")
        self.assertEqual(task["status"], "completed")
        self.assertIsNotNone(task["result"])
        self.mock_adapter.execute_plan_step.assert_called_once()


if __name__ == "__main__":
    unittest.main()
