"""
Unit tests for FastAPI API endpoints in api/main.py.
"""

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from fastapi import HTTPException

import api.main as main_module
from api.schemas import (
    CommandRunRequest,
    PlanRequest,
    TaskApproveRequest,
    TaskCreate,
    TaskExecuteRequest,
)
from windows_automation.schemas import ExecutionResult, VerificationEvidence


class TestAPIEndpoints(unittest.TestCase):
    """Test all FastAPI endpoints in api/main.py directly."""

    def setUp(self):
        # Clear shared tasks store before each test
        main_module.tasks.clear()
        # Reset mock adapter on orchestrator
        self.mock_adapter = MagicMock()
        main_module.orchestrator.adapter = self.mock_adapter

    def test_health_check(self):
        response = main_module.health_check()
        self.assertEqual(response, {"status": "ok"})

    def test_create_plan_valid(self):
        request = PlanRequest(text="Open Notepad")
        response = main_module.create_plan(request)
        self.assertEqual(response["status"], "plan_ready")
        self.assertEqual(response["intent"], "open_application")
        self.assertFalse(response["requires_clarification"])
        steps = response["steps"]
        assert isinstance(steps, list)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["target"], "Notepad")

    def test_create_plan_requires_clarification(self):
        request = PlanRequest(text="Open")
        response = main_module.create_plan(request)
        self.assertEqual(response["status"], "clarification_required")
        self.assertTrue(response["requires_clarification"])
        self.assertIsNotNone(response["clarification_question"])

    def test_list_catalogue(self):
        catalogue = main_module.list_catalogue()
        self.assertIsInstance(catalogue, list)
        self.assertGreaterEqual(len(catalogue), 7)
        app_names = [item["app_name"] for item in catalogue]
        self.assertIn("Notepad", app_names)
        self.assertIn("Calculator", app_names)
        self.assertIn("Google Chrome", app_names)

    def test_get_catalogue_app_found(self):
        app_item = main_module.get_catalogue_app("notepad")
        self.assertEqual(app_item["app_name"], "Notepad")
        self.assertTrue(app_item["allowlisted"])

    def test_get_catalogue_app_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            main_module.get_catalogue_app("nonexistent_app_id")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_create_task_and_list_tasks(self):
        task_in = TaskCreate(title="Test Task", description="Testing description")
        created = main_module.create_task(task_in)
        self.assertTrue(created["task_id"].startswith("task_"))
        self.assertEqual(created["status"], "pending")

        all_tasks = main_module.list_tasks(task_status=None)
        self.assertEqual(len(all_tasks), 1)
        self.assertEqual(all_tasks[0]["task_id"], created["task_id"])

    def test_get_task_status_found_and_not_found(self):
        task_in = TaskCreate(title="Status Test")
        created = main_module.create_task(task_in)
        task_id = created["task_id"]

        status_res = main_module.get_task_status(task_id)
        self.assertEqual(status_res["task_id"], task_id)
        self.assertEqual(status_res["status"], "pending")

        with self.assertRaises(HTTPException) as ctx:
            main_module.get_task_status("invalid_task_id")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_task_result_found_and_not_found(self):
        task_in = TaskCreate(title="Result Test")
        created = main_module.create_task(task_in)
        task_id = created["task_id"]

        result_res = main_module.get_task_result(task_id)
        self.assertEqual(result_res["task_id"], task_id)
        self.assertEqual(result_res["status"], "pending")
        self.assertIsNone(result_res["result"])

        with self.assertRaises(HTTPException) as ctx:
            main_module.get_task_result("invalid_task_id")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_execute_task_endpoint(self):
        mock_result = ExecutionResult(
            action_id="act-api-1",
            task_id="task-api-1",
            status="completed",
            duration_ms=100,
            verification=VerificationEvidence(
                verified=True,
                details={"window_title": "Untitled - Notepad"},
            ),
        )
        self.mock_adapter.execute_plan_step.return_value = mock_result

        task_in = TaskCreate(title="Open Notepad", command="Open Notepad")
        created = main_module.create_task(task_in)
        task_id = created["task_id"]

        exec_res = main_module.execute_task(task_id, TaskExecuteRequest(timeout_seconds=5.0))
        self.assertEqual(exec_res["status"], "completed")
        verification: Dict[str, Any] = exec_res["verification"]  # type: ignore[assignment]
        self.assertIs(verification["verified"], True)
        self.mock_adapter.execute_plan_step.assert_called_once()

    def test_approve_task_endpoint(self):
        # Create calculator task which triggers requires_approval
        task_in = TaskCreate(title="Open Calculator", command="Open Calculator")
        created = main_module.create_task(task_in)
        task_id = created["task_id"]

        # Run execute to enter requires_approval
        main_module.execute_task(task_id, TaskExecuteRequest())
        status_res = main_module.get_task_status(task_id)
        self.assertEqual(status_res["status"], "requires_approval")
        self.assertTrue(status_res["requires_approval"])

        # Mock adapter for approval execution
        mock_result = ExecutionResult(
            action_id="act-calc-api",
            task_id=task_id,
            status="completed",
            verification=VerificationEvidence(verified=True),
        )
        self.mock_adapter.execute_plan_step.return_value = mock_result

        # User approves
        approved_res = main_module.approve_task(
            task_id, TaskApproveRequest(approval_reference="user_approved_calc")
        )
        self.assertEqual(approved_res["status"], "completed")

    def test_cancel_task_endpoint(self):
        task_in = TaskCreate(title="To Cancel", command="Open Notepad")
        created = main_module.create_task(task_in)
        task_id = created["task_id"]

        cancelled_res = main_module.cancel_task(task_id)
        self.assertEqual(cancelled_res["status"], "cancelled")

        with self.assertRaises(HTTPException) as ctx:
            main_module.cancel_task("unknown_task_id")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_run_command_endpoint(self):
        mock_result = ExecutionResult(
            action_id="act-run-1",
            task_id="task-run-1",
            status="completed",
            verification=VerificationEvidence(verified=True),
        )
        self.mock_adapter.execute_plan_step.return_value = mock_result

        request = CommandRunRequest(text="Open Notepad")
        run_res = main_module.run_command(request)
        self.assertEqual(run_res["status"], "completed")
        task_id_res = run_res["task_id"]
        assert task_id_res is not None
        self.assertTrue(task_id_res.startswith("task_"))


if __name__ == "__main__":
    unittest.main()
