"""
Priority 3 Integration Tests: AI Intent Engine + Windows Automation Integration.

Covers all 14 required acceptance scenarios:
1. Chrome launch intent
2. VS Code launch intent
3. Alternative phrases resolving to the same action ("Open Chrome", "Launch Chrome", "Can you open my browser?")
4. Correct structured request generation (StructuredActionRequest)
5. Missing required parameters handling (ERR_MISSING_PARAMETERS)
6. Unknown application rejection (ERR_UNKNOWN_APPLICATION)
7. Invalid application identifier validation (ERR_INVALID_APPLICATION_ID)
8. Windows Automation success execution
9. Windows Automation failure handling (ERR_LAUNCH_FAILED)
10. Execution timeout handling (ERR_TIMEOUT)
11. Invalid AI intent output handling (ERR_INVALID_INTENT)
12. Accurate task status updates (processing -> matching -> launching -> launched)
13. Frontend / Mission Control result consistency
14. Ambiguous command handling (ERR_AMBIGUOUS_COMMAND)
"""

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from api.orchestrator import (
    ApplicationResolver,
    TaskOrchestrator,
)
from api.schemas import (
    StructuredActionRequest,
    TaskSubmitRequest,
)
import api.main as main_module
from windows_automation.schemas import (
    AuditRecord,
    ExecutionResult,
    VerificationEvidence,
)


class TestPriority3Integration(unittest.TestCase):
    """Test suite validating AI Intent Engine + Windows Automation Integration."""

    def setUp(self):
        main_module.tasks.clear()
        self.mock_adapter = MagicMock()
        self.orchestrator = TaskOrchestrator(
            adapter=self.mock_adapter,
            tasks=main_module.tasks,
        )
        main_module.orchestrator = self.orchestrator

        # Default mock verified result for auto-approved launches
        self.mock_verified = VerificationEvidence(
            verified=True,
            method="win32_window_and_process_polling",
            details={
                "process_name": "notepad.exe",
                "window_found": True,
                "window_title": "Untitled - Notepad",
                "window_handle": 54321,
            },
        )
        self.mock_audit = AuditRecord(
            event_type="action_completed_verified",
            action_id="act-mock-p3",
            task_id="task-mock-p3",
            redacted_summary="Launched application: Notepad",
        )
        self.mock_success = ExecutionResult(
            action_id="act-mock-p3",
            task_id="task-mock-p3",
            status="completed",
            duration_ms=250,
            verification=self.mock_verified,
            audit=self.mock_audit,
        )
        self.mock_adapter.execute_plan_step.return_value = self.mock_success

    # -----------------------------------------------------------------------
    # Scenario 1: Chrome Launch Intent
    # -----------------------------------------------------------------------
    def test_01_chrome_launch_intent(self):
        task = self.orchestrator.run_pipeline("Open Chrome", auto_execute=False)
        self.assertEqual(task["status"], "matching")
        self.assertEqual(task["intent"], "open_application")
        self.assertEqual(task["selected_application"], "Google Chrome")
        self.assertEqual(task["application_id"], "chrome")
        self.assertIsNotNone(task["structured_request"])
        self.assertEqual(task["structured_request"]["application_id"], "chrome")
        self.assertEqual(task["structured_request"]["target"], "Google Chrome")

    # -----------------------------------------------------------------------
    # Scenario 2: VS Code Launch Intent
    # -----------------------------------------------------------------------
    def test_02_vscode_launch_intent(self):
        task = self.orchestrator.run_pipeline("Open VS Code", auto_execute=False)
        self.assertEqual(task["status"], "matching")
        self.assertEqual(task["intent"], "open_application")
        self.assertEqual(task["selected_application"], "Visual Studio Code")
        self.assertEqual(task["application_id"], "vscode")
        self.assertIsNotNone(task["structured_request"])
        self.assertEqual(task["structured_request"]["application_id"], "vscode")

    # -----------------------------------------------------------------------
    # Scenario 3: Alternative Phrases Resolving to Same Action
    # -----------------------------------------------------------------------
    def test_03_alternative_phrases_resolution(self):
        phrases = [
            "Open Chrome",
            "Launch Chrome",
            "Start Google Chrome",
            "Can you open my browser?",
        ]
        for phrase in phrases:
            task = self.orchestrator.run_pipeline(phrase, auto_execute=False)
            self.assertEqual(
                task["selected_application"],
                "Google Chrome",
                f"Phrase '{phrase}' failed to resolve to Google Chrome",
            )
            self.assertEqual(task["application_id"], "chrome")
            self.assertEqual(task["structured_request"]["action"], "launch_application")

    # -----------------------------------------------------------------------
    # Scenario 4: Correct Structured Request Generation
    # -----------------------------------------------------------------------
    def test_04_structured_request_generation(self):
        task = self.orchestrator.run_pipeline("Open Notepad", input_type="voice", auto_execute=False)
        req_data = task["structured_request"]
        self.assertIsInstance(req_data, dict)

        # Validate with Pydantic model
        structured_model = StructuredActionRequest(**req_data)
        self.assertEqual(structured_model.action, "launch_application")
        self.assertEqual(structured_model.application_id, "notepad")
        self.assertEqual(structured_model.target, "Notepad")
        self.assertEqual(structured_model.source, "voice")
        self.assertEqual(structured_model.parameters, {})

    # -----------------------------------------------------------------------
    # Scenario 5: Missing Required Parameters Handling
    # -----------------------------------------------------------------------
    def test_05_missing_required_parameters(self):
        resolver = ApplicationResolver()

        # Missing target
        invalid_req_1: Dict[str, Any] = {
            "action": "launch_application",
            "application_id": "notepad",
            "target": "",
            "parameters": {},
        }
        is_val, err_code, _ = resolver.validate_structured_request(invalid_req_1)
        self.assertFalse(is_val)
        self.assertEqual(err_code, "ERR_MISSING_PARAMETERS")

        # Missing parameters dict
        invalid_req_2: Dict[str, Any] = {
            "action": "launch_application",
            "application_id": "notepad",
            "target": "Notepad",
            "parameters": None,
        }
        is_val, err_code, _ = resolver.validate_structured_request(invalid_req_2)
        self.assertFalse(is_val)
        self.assertEqual(err_code, "ERR_MISSING_PARAMETERS")

    # -----------------------------------------------------------------------
    # Scenario 6: Unknown Application Rejection
    # -----------------------------------------------------------------------
    def test_06_unknown_application_rejection(self):
        task = self.orchestrator.run_pipeline("Open Blender")
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "ERR_UNKNOWN_APPLICATION")
        self.assertIn("blender", task["error_message"].lower())
        self.mock_adapter.execute_plan_step.assert_not_called()

    # -----------------------------------------------------------------------
    # Scenario 7: Invalid Application Identifier Validation
    # -----------------------------------------------------------------------
    def test_07_invalid_application_identifier(self):
        resolver = ApplicationResolver()
        self.assertFalse(resolver.is_valid_application_id("calc;rmdir"))
        self.assertFalse(resolver.is_valid_application_id("notepad|del"))
        self.assertFalse(resolver.is_valid_application_id(""))
        self.assertFalse(resolver.is_valid_application_id(" "))

        invalid_req: Dict[str, Any] = {
            "action": "launch_application",
            "application_id": "chrome;malicious",
            "target": "Google Chrome",
            "parameters": {},
        }
        is_val, err_code, _ = resolver.validate_structured_request(invalid_req)
        self.assertFalse(is_val)
        self.assertEqual(err_code, "ERR_INVALID_APPLICATION_ID")

    # -----------------------------------------------------------------------
    # Scenario 8: Windows Automation Success
    # -----------------------------------------------------------------------
    def test_08_windows_automation_success(self):
        task = self.orchestrator.run_pipeline("Open Notepad")
        self.assertEqual(task["status"], "launched")
        self.assertIsNone(task["error_code"])
        self.assertIsNotNone(task["verification"])
        self.assertTrue(task["verification"]["verified"])
        self.assertEqual(task["verification"]["details"]["window_handle"], 54321)

    # -----------------------------------------------------------------------
    # Scenario 9: Windows Automation Failure Handling
    # -----------------------------------------------------------------------
    def test_09_windows_automation_failure(self):
        fail_result = ExecutionResult(
            action_id="act-fail-p3",
            task_id="task-fail-p3",
            status="failed",
            error_code="ERR_LAUNCH_FAILED",
            error_message="Executable not found on filesystem path",
            verification=VerificationEvidence(verified=False),
        )
        self.mock_adapter.execute_plan_step.return_value = fail_result

        task = self.orchestrator.run_pipeline("Open Notepad")
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "ERR_LAUNCH_FAILED")
        self.assertIn("Executable not found", task["error_message"])

    # -----------------------------------------------------------------------
    # Scenario 10: Execution Timeout Handling
    # -----------------------------------------------------------------------
    def test_10_execution_timeout(self):
        timeout_result = ExecutionResult(
            action_id="act-timeout-p3",
            task_id="task-timeout-p3",
            status="failed",
            error_code="ERR_TIMEOUT",
            error_message="Window verification timed out after 5.0 seconds",
            verification=VerificationEvidence(verified=False),
        )
        self.mock_adapter.execute_plan_step.return_value = timeout_result

        task = self.orchestrator.run_pipeline("Open Notepad", timeout_seconds=5.0)
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "ERR_TIMEOUT")
        self.assertIn("timed out", task["error_message"].lower())

    # -----------------------------------------------------------------------
    # Scenario 11: Invalid AI Intent Output
    # -----------------------------------------------------------------------
    def test_11_invalid_ai_intent_output(self):
        # Empty string
        task_empty = self.orchestrator.run_pipeline("")
        self.assertEqual(task_empty["status"], "failed")
        self.assertEqual(task_empty["error_code"], "ERR_INVALID_INTENT")

        # Unsupported arbitrary command
        task_gibberish = self.orchestrator.run_pipeline("Fly to the moon right now")
        self.assertEqual(task_gibberish["status"], "failed")
        self.assertEqual(task_gibberish["error_code"], "ERR_INVALID_INTENT")

    # -----------------------------------------------------------------------
    # Scenario 12: Accurate Task Status Updates & Transitions
    # -----------------------------------------------------------------------
    def test_12_accurate_task_status_updates(self):
        task = self.orchestrator.run_pipeline("Open Notepad")
        self.assertEqual(task["status"], "launched")

        timeline = task.get("timeline", [])
        states = [entry["state"] for entry in timeline]
        self.assertEqual(states, ["processing", "matching", "launching", "launched"])

    # -----------------------------------------------------------------------
    # Scenario 13: Frontend / Mission Control Result Consistency
    # -----------------------------------------------------------------------
    def test_13_frontend_mission_control_consistency(self):
        submit_req = TaskSubmitRequest(command="Open Notepad", input_type="text")
        response = main_module.submit_task(submit_req)

        # 1. Submission API returns required Mission Control metadata
        self.assertIn("task_id", response)
        self.assertIn("status", response)
        self.assertIn("intent", response)
        self.assertIn("selected_application", response)
        self.assertIn("application_id", response)
        self.assertIn("structured_request", response)
        self.assertEqual(response["selected_application"], "Notepad")
        self.assertEqual(response["application_id"], "notepad")

        task_id = response["task_id"]

        # 2. Progress API returns consistent structured request and stages
        progress = main_module.get_task_progress(task_id)
        self.assertEqual(progress["task_id"], task_id)
        self.assertEqual(progress["status"], "launched")
        self.assertEqual(progress["progress_percent"], 100)
        self.assertEqual(progress["selected_application"], "Notepad")
        self.assertEqual(progress["structured_request"]["application_id"], "notepad")

        # 3. Result API returns truthful execution result and verification
        result = main_module.get_task_result(task_id)
        self.assertEqual(result["task_id"], task_id)
        self.assertEqual(result["status"], "launched")
        self.assertEqual(result["selected_application"], "Notepad")
        self.assertEqual(result["application_id"], "notepad")
        self.assertTrue(result["verification"]["verified"])
        self.assertIsNotNone(result["audit"])

    # -----------------------------------------------------------------------
    # Scenario 14: Ambiguous Command Handling
    # -----------------------------------------------------------------------
    def test_14_ambiguous_command_handling(self):
        # "Open Visual Studio" is ambiguous between VS Code and Visual Studio
        task = self.orchestrator.run_pipeline("Open Visual Studio")
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "ERR_AMBIGUOUS_COMMAND")
        self.assertTrue(
            "which application did you mean" in task["error_message"].lower()
            or "ambiguous" in task["error_message"].lower()
        )
        # Automation must NOT be executed for ambiguous commands
        self.mock_adapter.execute_plan_step.assert_not_called()


if __name__ == "__main__":
    unittest.main()
