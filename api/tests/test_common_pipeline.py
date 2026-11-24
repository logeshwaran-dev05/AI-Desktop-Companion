"""
Integration tests for Common Execution Pipeline, Voice & Text APIs,
Application Resolution, and State Transitions.

Covers all required acceptance scenarios:
1. Text task submission
2. Voice transcript submission
3. Shared execution pipeline (both text & voice use the same execution service)
4. Duplicate request handling (ERR_DUPLICATE_REQUEST)
5. Unknown application rejection (ERR_UNKNOWN_APPLICATION)
6. Successful application launch (mocked automation -> launched)
7. Automation failure handling (ERR_LAUNCH_FAILED -> failed)
8. Timeout handling (ERR_TIMEOUT -> failed)
9. Invalid request handling (ERR_INVALID_INTENT)
10. Task state transitions (listening -> processing -> matching -> launching -> launched)
11. False success prevention (unverified launch must NEVER report launched)
12. Unavailable voice service handling (ERR_VOICE_SERVICE_UNAVAILABLE)
13. Task progress tracking and timeline verification
"""

import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

import api.main as main_module
from api.orchestrator import TaskOrchestrator
from api.schemas import (
    TaskSubmitRequest,
    VoiceInputRequest,
    VoiceTranscriptRequest,
)
from windows_automation.schemas import (
    AuditRecord,
    ExecutionResult,
    VerificationEvidence,
)


class TestCommonExecutionPipeline(unittest.TestCase):
    """Test suite for shared backend execution pipeline and safety contracts."""

    def setUp(self):
        main_module.tasks.clear()
        self.mock_adapter = MagicMock()
        self.orchestrator = TaskOrchestrator(
            adapter=self.mock_adapter,
            tasks=main_module.tasks,
        )
        main_module.orchestrator = self.orchestrator

        # Default successful mock execution result
        self.mock_verified_evidence = VerificationEvidence(
            verified=True,
            method="win32_window_and_process_polling",
            details={
                "process_id": 9999,
                "process_name": "notepad.exe",
                "window_found": True,
                "window_title": "Untitled - Notepad",
                "window_handle": 12345,
            },
        )
        self.mock_audit = AuditRecord(
            event_type="action_completed_verified",
            action_id="act-mock-1",
            task_id="task-mock-1",
            redacted_summary="Launched allowlisted application: Notepad",
        )
        self.mock_success_result = ExecutionResult(
            action_id="act-mock-1",
            task_id="task-mock-1",
            status="completed",
            duration_ms=450,
            verification=self.mock_verified_evidence,
            audit=self.mock_audit,
        )
        self.mock_adapter.execute_plan_step.return_value = self.mock_success_result

    # -----------------------------------------------------------------------
    # 1. Text Task Submission
    # -----------------------------------------------------------------------
    def test_01_text_task_submission(self):
        request = TaskSubmitRequest(
            command="Open Notepad",
            input_type="text",
            auto_execute=True,
        )
        response = main_module.submit_task(request)
        self.assertTrue(response["task_id"].startswith("task_"))
        self.assertEqual(response["input_type"], "text")
        self.assertEqual(response["command"], "Open Notepad")
        self.assertEqual(response["status"], "launched")

        task = main_module.tasks[response["task_id"]]
        self.assertEqual(task["status"], "launched")
        self.assertIsNotNone(task["verification"])
        self.assertTrue(task["verification"]["verified"])
        self.mock_adapter.execute_plan_step.assert_called_once()

    # -----------------------------------------------------------------------
    # 2. Voice Transcript Submission
    # -----------------------------------------------------------------------
    def test_02_voice_transcript_submission(self):
        request = VoiceTranscriptRequest(
            transcript="Open Notepad",
            confidence=0.99,
            auto_execute=True,
        )
        response = main_module.submit_voice_transcript(request)
        self.assertTrue(response["task_id"].startswith("task_"))
        self.assertEqual(response["input_type"], "voice")
        self.assertEqual(response["transcript"], "Open Notepad")
        self.assertEqual(response["status"], "launched")

        task = main_module.tasks[response["task_id"]]
        self.assertEqual(task["status"], "launched")
        self.assertEqual(task["input_type"], "voice")
        self.assertTrue(task["verification"]["verified"])

    # -----------------------------------------------------------------------
    # 3. Shared Execution Pipeline (Text & Voice follow identical path)
    # -----------------------------------------------------------------------
    def test_03_shared_execution_pipeline(self):
        # Run text task
        text_task = self.orchestrator.run_pipeline(
            command="Open Notepad",
            input_type="text",
            auto_execute=True,
        )
        # Run voice task
        voice_task = self.orchestrator.run_pipeline(
            command="Open Notepad",
            input_type="voice",
            auto_execute=True,
        )

        self.assertEqual(text_task["status"], "launched")
        self.assertEqual(voice_task["status"], "launched")
        self.assertEqual(text_task["intent"], voice_task["intent"])
        self.assertEqual(
            text_task["steps"][0]["target"],
            voice_task["steps"][0]["target"],
        )
        self.assertEqual(self.mock_adapter.execute_plan_step.call_count, 2)

    # -----------------------------------------------------------------------
    # 4. Duplicate Request Handling
    # -----------------------------------------------------------------------
    def test_04_duplicate_request_handling(self):
        key = "idemp_test_key_001"
        req1 = TaskSubmitRequest(command="Open Notepad", idempotency_key=key)
        res1 = main_module.submit_task(req1)
        self.assertEqual(res1["status"], "launched")

        # Second request with the same idempotency key must raise 409 Conflict
        req2 = TaskSubmitRequest(command="Open Notepad", idempotency_key=key)
        with self.assertRaises(HTTPException) as ctx:
            main_module.submit_task(req2)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Duplicate request detected", str(ctx.exception.detail))

    # -----------------------------------------------------------------------
    # 5. Unknown Application Rejection
    # -----------------------------------------------------------------------
    def test_05_unknown_application_rejection(self):
        task = self.orchestrator.run_pipeline(
            command="Open Photoshop",
            input_type="text",
        )
        self.assertEqual(task["status"], "failed")
        self.assertIn(task["error_code"], ["ERR_UNKNOWN_APPLICATION", "ERR_PERMISSION_DENIED"])
        self.assertIn("photoshop", task["error_message"].lower())
        # Automation must NEVER be called for unknown applications
        self.mock_adapter.execute_plan_step.assert_not_called()

    # -----------------------------------------------------------------------
    # 6. Successful Application Launch (Mocked Automation)
    # -----------------------------------------------------------------------
    def test_06_successful_application_launch(self):
        task = self.orchestrator.run_pipeline("Open Notepad")
        self.assertEqual(task["status"], "launched")
        self.assertIsNotNone(task["verification"])
        self.assertTrue(task["verification"]["verified"])
        self.assertEqual(task["verification"]["details"]["process_name"], "notepad.exe")
        self.assertEqual(task["verification"]["details"]["window_handle"], 12345)

    # -----------------------------------------------------------------------
    # 7. Automation Failure Handling
    # -----------------------------------------------------------------------
    def test_07_automation_failure_handling(self):
        mock_failure = ExecutionResult(
            action_id="act-fail-1",
            task_id="task-fail-1",
            status="failed",
            error_code="ERR_LAUNCH_FAILED",
            error_message="Subprocess spawn returned error code 1",
            verification=VerificationEvidence(verified=False),
        )
        self.mock_adapter.execute_plan_step.return_value = mock_failure

        task = self.orchestrator.run_pipeline("Open Notepad")
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "ERR_LAUNCH_FAILED")
        self.assertIn("Subprocess spawn", task["error_message"])

    # -----------------------------------------------------------------------
    # 8. Timeout Handling
    # -----------------------------------------------------------------------
    def test_08_timeout_handling(self):
        mock_timeout = ExecutionResult(
            action_id="act-timeout-1",
            task_id="task-timeout-1",
            status="failed",
            error_code="ERR_TIMEOUT",
            error_message="Window not visible within bounded timeout of 10.0s",
            verification=VerificationEvidence(verified=False),
        )
        self.mock_adapter.execute_plan_step.return_value = mock_timeout

        task = self.orchestrator.run_pipeline("Open Notepad", timeout_seconds=10.0)
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "ERR_TIMEOUT")
        self.assertIn("Timeout", task["message"])

    # -----------------------------------------------------------------------
    # 9. Invalid Request Handling
    # -----------------------------------------------------------------------
    def test_09_invalid_request_handling(self):
        # Empty command
        task = self.orchestrator.run_pipeline("")
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "ERR_INVALID_INTENT")

        # Unsupported command
        task2 = self.orchestrator.run_pipeline("Delete all files on drive C")
        self.assertEqual(task2["status"], "failed")
        self.assertEqual(task2["error_code"], "ERR_INVALID_INTENT")

    # -----------------------------------------------------------------------
    # 10. Task State Transitions Sequence
    # -----------------------------------------------------------------------
    def test_10_task_state_transitions(self):
        # Track transitions through the timeline
        task = self.orchestrator.run_pipeline(
            command="Open Notepad",
            input_type="text",
        )
        timeline = task.get("timeline", [])
        states_in_order = [entry["state"] for entry in timeline]

        # Expected flow: processing -> matching -> launching -> launched
        self.assertIn("processing", states_in_order)
        self.assertIn("matching", states_in_order)
        self.assertIn("launching", states_in_order)
        self.assertIn("launched", states_in_order)
        self.assertEqual(states_in_order[-1], "launched")

    # -----------------------------------------------------------------------
    # 11. False Success Prevention (Strict Safety Rule)
    # -----------------------------------------------------------------------
    def test_11_false_success_prevention(self):
        """
        Critical safety test: If automation executor returns completed
        but verifier evidence is False, task must NEVER report launched!
        """
        unverified_result = ExecutionResult(
            action_id="act-fake-1",
            task_id="task-fake-1",
            status="completed",  # Subprocess exited without error
            verification=VerificationEvidence(
                verified=False,  # BUT window was NOT found
                details={"window_found": False},
            ),
        )
        self.mock_adapter.execute_plan_step.return_value = unverified_result

        task = self.orchestrator.run_pipeline("Open Notepad")
        # Must NOT be launched
        self.assertNotEqual(task["status"], "launched")
        # Must be failed
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "ERR_VERIFICATION_FAILED")
        self.assertIn("Verification failed", task["message"])

    # -----------------------------------------------------------------------
    # 12. Unavailable Voice Service Handling
    # -----------------------------------------------------------------------
    def test_12_unavailable_voice_service(self):
        req = VoiceInputRequest(simulate_service_down=True)
        with self.assertRaises(HTTPException) as ctx:
            main_module.submit_voice_input(req)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Voice service is currently unavailable", str(ctx.exception.detail))

    # -----------------------------------------------------------------------
    # 13. Task Progress Update Endpoint
    # -----------------------------------------------------------------------
    def test_13_task_progress_endpoint(self):
        req = TaskSubmitRequest(command="Open Notepad")
        submit_res = main_module.submit_task(req)
        task_id = submit_res["task_id"]

        progress_res = main_module.get_task_progress(task_id)
        self.assertEqual(progress_res["task_id"], task_id)
        self.assertEqual(progress_res["status"], "launched")
        self.assertEqual(progress_res["progress_percent"], 100)
        self.assertGreaterEqual(len(progress_res["timeline"]), 3)

        # 404 for unknown task
        with self.assertRaises(HTTPException) as ctx:
            main_module.get_task_progress("non_existent_id")
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
