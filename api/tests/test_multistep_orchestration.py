"""Tests for multi-step sequential orchestration and inter-step context passing."""

import unittest
from unittest.mock import MagicMock

from api.orchestrator import TaskOrchestrator
from windows_automation.schemas import ExecutionResult, VerificationEvidence


class TestMultiStepOrchestration(unittest.TestCase):
    def setUp(self):
        self.mock_adapter = MagicMock()
        self.orchestrator = TaskOrchestrator()
        self.orchestrator.adapter = self.mock_adapter

    def test_email_multistep_passes_captured_text_and_asks_recipient(self):
        def fake_execute(step, task_id, authorization, timeout_seconds=10.0):
            details = {}
            if step.action == "capture_ai_response":
                details = {"captured_text": "Dear Manager, I am requesting leave tomorrow."}
            return ExecutionResult(
                action_id=f"act_{step.step_id}",
                task_id=task_id,
                status="completed",
                verification_status="verified",
                started_at="2026-11-26T20:00:00Z",
                completed_at="2026-11-26T20:00:01Z",
                duration_ms=10,
                verification=VerificationEvidence(
                    verified=True,
                    method=step.action,
                    verification_status="verified",
                    details=details,
                ),
            )

        self.mock_adapter.execute_plan_step.side_effect = fake_execute

        task = self.orchestrator.run_command(
            "ask gpt to write an email to my manager",
        )

        self.assertEqual(task["status"], "completed")
        self.assertEqual(self.mock_adapter.execute_plan_step.call_count, 5)
        # Step 5 (clipboard_paste) must receive captured_text from Step 3
        paste_call_step = self.mock_adapter.execute_plan_step.call_args_list[4].kwargs["step"]
        self.assertEqual(paste_call_step.action, "clipboard_paste")
        self.assertEqual(paste_call_step.parameters.get("text"), "Dear Manager, I am requesting leave tomorrow.")
        self.assertTrue(task.get("requires_clarification"))
        self.assertIn("whom", (task.get("clarification_question") or "").lower())

    def test_batch_download_executes_cleanly(self):
        self.mock_adapter.execute_plan_step.return_value = ExecutionResult(
            action_id="act_dl",
            task_id="t_dl",
            status="completed",
            verification_status="verified",
            started_at="2026-11-26T20:00:00Z",
            completed_at="2026-11-26T20:00:01Z",
            duration_ms=10,
            verification=VerificationEvidence(
                verified=True,
                method="batch_download_loop",
                verification_status="verified",
                details={"downloaded_count": 2},
            ),
        )

        task = self.orchestrator.run_command(
            "loop download python pdf, react docs",
        )
        self.assertEqual(task["status"], "completed")
        self.mock_adapter.execute_plan_step.assert_called_once()


if __name__ == "__main__":
    unittest.main()
