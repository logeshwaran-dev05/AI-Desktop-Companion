"""
App Catalogue & Orchestration Tests — 18 Scenarios.

Covers:
  Catalogue tests (1-11): phrase resolution, ambiguity, unknown apps,
  catalogue size, and ID validation.
  Pipeline tests (12-18): timeout, automation failure, duplicate request,
  voice/text parity, structured request fields.

All tests use unittest.mock.MagicMock — real applications are never launched.
Run with:
    python -m unittest api.tests.test_app_catalogue_orchestration -v
"""

import unittest
from unittest.mock import MagicMock, patch

from api.app_catalogue import (
    WindowsApplicationCatalogue,
    catalogue_service,
    get_windows_catalogue,
    resolve_application,
)
from api.orchestrator import (
    ApplicationResolver,
    DuplicateRequestError,
    TaskOrchestrator,
)
from api.schemas import StructuredActionRequest
from windows_automation.schemas import (
    AuthorizationDecision,
    ExecutionResult,
    VerificationEvidence,
    AuditRecord,
)


# ---------------------------------------------------------------------------
# Helper: build a mock planner and mock installed-apps list for pipeline tests
# ---------------------------------------------------------------------------

def _make_mock_planner():
    """Return a MagicMock that mimics TaskPlanner.process_command for Notepad."""
    mock_step = MagicMock()
    mock_step.step_id = 1
    mock_step.action = "open_application"
    mock_step.target = "Notepad"
    mock_step.depends_on = []
    mock_step.expected_outcome = "Notepad should open"

    plan_response = MagicMock()
    plan_response.intent = "open_application"
    plan_response.status = "success"
    plan_response.message = "Open Notepad"
    plan_response.clarification_question = None
    plan_response.steps = [mock_step]
    plan_response.entities = MagicMock()
    plan_response.entities.application = "Notepad"

    mock_planner = MagicMock()
    mock_planner.process_command.return_value = plan_response
    return mock_planner


_NOTEPAD_APP_LIST = [
    {"app_name": "Notepad", "app_id": "notepad", "executable": "notepad.exe"}
]


def _make_success_exec_result():
    """Return a mock ExecutionResult for a successful Notepad launch."""
    mock_verification = MagicMock()
    mock_verification.verified = True
    mock_verification.to_dict.return_value = {"verified": True}

    mock_audit = MagicMock()
    mock_audit.to_dict.return_value = {}

    mock_result = MagicMock(spec=ExecutionResult)
    mock_result.status = "completed"
    mock_result.action_id = "act_test"
    mock_result.duration_ms = 100
    mock_result.completed_at = "2026-01-01T00:00:00+00:00"
    mock_result.error_code = None
    mock_result.error_message = None
    mock_result.verification = mock_verification
    mock_result.audit = mock_audit
    mock_result.to_dict.return_value = {"status": "completed"}
    return mock_result


def _make_timeout_exec_result():
    """Return a mock ExecutionResult that represents a timeout."""
    mock_result = MagicMock(spec=ExecutionResult)
    mock_result.status = "failed"
    mock_result.action_id = "act_t"
    mock_result.duration_ms = 10000
    mock_result.completed_at = "2026-01-01T00:00:00+00:00"
    mock_result.error_code = "ERR_TIMEOUT"
    mock_result.error_message = "Timed out"
    mock_result.verification = None
    mock_result.audit = None
    mock_result.to_dict.return_value = {"status": "failed"}
    return mock_result


# ---------------------------------------------------------------------------
# Class 1: Catalogue Resolution Tests (Scenarios 1-11)
# ---------------------------------------------------------------------------

class TestAppCatalogueResolution(unittest.TestCase):
    """Test WindowsApplicationCatalogue phrase resolution and catalogue content."""

    # -------------------------------------------------------------------
    # Scenario 1: Chrome Resolution
    # -------------------------------------------------------------------
    def test_01_catalogue_chrome_resolution(self):
        """catalogue_service.resolve_phrase('Open Chrome') resolves to app_id=='chrome'."""
        result = catalogue_service.resolve_phrase("Open Chrome")
        self.assertIsNotNone(result, "Expected a resolved entry for 'Open Chrome', got None")
        self.assertEqual(result["app_id"], "chrome")

    # -------------------------------------------------------------------
    # Scenario 2: VS Code Resolution
    # -------------------------------------------------------------------
    def test_02_catalogue_vscode_resolution(self):
        """catalogue_service.resolve_phrase('Open VS Code') resolves to app_id=='vscode'."""
        result = catalogue_service.resolve_phrase("Open VS Code")
        self.assertIsNotNone(result, "Expected a resolved entry for 'Open VS Code', got None")
        self.assertEqual(result["app_id"], "vscode")

    # -------------------------------------------------------------------
    # Scenario 3: Calculator Resolution
    # -------------------------------------------------------------------
    def test_03_catalogue_calculator_resolution(self):
        """catalogue_service.resolve_phrase('Open Calculator') resolves to app_id=='calculator'."""
        result = catalogue_service.resolve_phrase("Open Calculator")
        self.assertIsNotNone(result, "Expected a resolved entry for 'Open Calculator', got None")
        self.assertEqual(result["app_id"], "calculator")

    # -------------------------------------------------------------------
    # Scenario 4: Notepad Resolution
    # -------------------------------------------------------------------
    def test_04_catalogue_notepad_resolution(self):
        """catalogue_service.resolve_phrase('Open Notepad') resolves to app_id=='notepad'."""
        result = catalogue_service.resolve_phrase("Open Notepad")
        self.assertIsNotNone(result, "Expected a resolved entry for 'Open Notepad', got None")
        self.assertEqual(result["app_id"], "notepad")

    # -------------------------------------------------------------------
    # Scenario 5: File Explorer Resolution
    # -------------------------------------------------------------------
    def test_05_catalogue_file_explorer_resolution(self):
        """catalogue_service.resolve_phrase('Open File Explorer') resolves to app_id=='explorer'."""
        result = catalogue_service.resolve_phrase("Open File Explorer")
        self.assertIsNotNone(result, "Expected a resolved entry for 'Open File Explorer', got None")
        self.assertEqual(result["app_id"], "explorer")

    # -------------------------------------------------------------------
    # Scenario 6: Settings Resolution
    # -------------------------------------------------------------------
    def test_06_catalogue_settings_resolution(self):
        """catalogue_service.resolve_phrase('Open Settings') resolves to app_id=='settings'."""
        result = catalogue_service.resolve_phrase("Open Settings")
        self.assertIsNotNone(result, "Expected a resolved entry for 'Open Settings', got None")
        self.assertEqual(result["app_id"], "settings")

    # -------------------------------------------------------------------
    # Scenario 7: System Settings Resolution
    # -------------------------------------------------------------------
    def test_07_catalogue_system_settings_resolution(self):
        """catalogue_service.resolve_phrase('Open System') resolves to app_id=='settings_system'."""
        result = catalogue_service.resolve_phrase("Open System")
        self.assertIsNotNone(result, "Expected a resolved entry for 'Open System', got None")
        self.assertEqual(result["app_id"], "settings_system")

    # -------------------------------------------------------------------
    # Scenario 8: Bluetooth Settings Resolution
    # -------------------------------------------------------------------
    def test_08_catalogue_bluetooth_settings_resolution(self):
        """catalogue_service.resolve_phrase('Open Bluetooth settings') resolves to app_id=='settings_bluetooth'."""
        result = catalogue_service.resolve_phrase("Open Bluetooth settings")
        self.assertIsNotNone(
            result, "Expected a resolved entry for 'Open Bluetooth settings', got None"
        )
        self.assertEqual(result["app_id"], "settings_bluetooth")

    # -------------------------------------------------------------------
    # Scenario 9: Alternative Phrases for Chrome
    # -------------------------------------------------------------------
    def test_09_alternative_phrases_for_chrome(self):
        """'Launch Chrome', 'Start Google Chrome', and 'Can you open my browser?' all resolve to chrome."""
        alt_phrases = [
            "Launch Chrome",
            "Start Google Chrome",
            "Can you open my browser?",
        ]
        for phrase in alt_phrases:
            with self.subTest(phrase=phrase):
                result = catalogue_service.resolve_phrase(phrase)
                self.assertIsNotNone(
                    result, f"Expected a resolved entry for '{phrase}', got None"
                )
                self.assertEqual(
                    result["app_id"],
                    "chrome",
                    f"Phrase '{phrase}' should resolve to 'chrome', got '{result.get('app_id')}'",
                )

    # -------------------------------------------------------------------
    # Scenario 10: Unknown Application Returns None
    # -------------------------------------------------------------------
    def test_10_unknown_application_returns_none(self):
        """catalogue_service.resolve_phrase('Open NonExistentApp99') returns None."""
        result = catalogue_service.resolve_phrase("Open NonExistentApp99")
        self.assertIsNone(result, f"Expected None for unknown app, got: {result}")

    # -------------------------------------------------------------------
    # Scenario 11: Ambiguous Visual Studio Query
    # -------------------------------------------------------------------
    def test_11_ambiguous_visual_studio(self):
        """catalogue_service.is_ambiguous('visual studio') returns (True, candidates) with >=2 entries."""
        is_ambig, candidates = catalogue_service.is_ambiguous("visual studio")
        self.assertTrue(is_ambig, "Expected 'visual studio' to be flagged as ambiguous")
        self.assertGreaterEqual(
            len(candidates), 2,
            f"Expected at least 2 candidate entries, got {len(candidates)}: {candidates}",
        )


# ---------------------------------------------------------------------------
# Class 2: Application ID Validation (Scenario 12)
# ---------------------------------------------------------------------------

class TestApplicationIdValidation(unittest.TestCase):
    """Test ApplicationResolver.is_valid_application_id()."""

    def setUp(self):
        self.resolver = ApplicationResolver()

    # -------------------------------------------------------------------
    # Scenario 12: Invalid Application ID
    # -------------------------------------------------------------------
    def test_12_invalid_application_id_validation(self):
        """is_valid_application_id returns False for empty/bad IDs and True for valid ones."""
        # Empty string is invalid
        self.assertFalse(
            self.resolver.is_valid_application_id(""),
            "Empty string should be invalid",
        )
        # 'valid' is a valid ID
        self.assertTrue(
            self.resolver.is_valid_application_id("valid"),
            "'valid' should be a valid application ID",
        )
        # ID containing ';' is invalid
        self.assertFalse(
            self.resolver.is_valid_application_id("bad;id"),
            "'bad;id' should be invalid due to forbidden character ';'",
        )


# ---------------------------------------------------------------------------
# Class 3: Pipeline Tests (Scenarios 13-18)
# ---------------------------------------------------------------------------

class TestPipelineOrchestration(unittest.TestCase):
    """
    Pipeline-level tests that mock out TaskPlanner, get_installed_apps,
    and the Windows Automation adapter to avoid any real OS interaction.
    """

    def _make_orchestrator(self, adapter):
        """Create a TaskOrchestrator with fresh state and the given adapter."""
        return TaskOrchestrator(adapter=adapter, tasks={})

    # -------------------------------------------------------------------
    # Scenario 13: Pipeline Launch Timeout
    # -------------------------------------------------------------------
    def test_13_pipeline_launch_timeout(self):
        """
        When the adapter returns ERR_TIMEOUT, run_pipeline sets status='failed'
        and error_code='ERR_TIMEOUT'.
        """
        mock_adapter = MagicMock()
        mock_adapter.execute_plan_step.return_value = _make_timeout_exec_result()

        with patch("api.orchestrator.TaskPlanner", return_value=_make_mock_planner()), \
             patch("api.orchestrator.get_installed_apps", return_value=_NOTEPAD_APP_LIST):

            orchestrator = self._make_orchestrator(mock_adapter)
            task = orchestrator.run_pipeline("Open Notepad", input_type="text")

        self.assertEqual(task["status"], "failed", f"Expected 'failed', got '{task['status']}'")
        self.assertEqual(
            task["error_code"], "ERR_TIMEOUT",
            f"Expected 'ERR_TIMEOUT', got '{task['error_code']}'",
        )

    # -------------------------------------------------------------------
    # Scenario 14: Pipeline Automation Failure
    # -------------------------------------------------------------------
    def test_14_pipeline_automation_failure(self):
        """
        When the adapter raises RuntimeError('OS error'), run_pipeline sets
        status='failed' and error_code='ERR_AUTOMATION_FAILURE'.
        """
        mock_adapter = MagicMock()
        mock_adapter.execute_plan_step.side_effect = RuntimeError("OS error")

        with patch("api.orchestrator.TaskPlanner", return_value=_make_mock_planner()), \
             patch("api.orchestrator.get_installed_apps", return_value=_NOTEPAD_APP_LIST):

            orchestrator = self._make_orchestrator(mock_adapter)
            task = orchestrator.run_pipeline("Open Notepad", input_type="text")

        self.assertEqual(task["status"], "failed", f"Expected 'failed', got '{task['status']}'")
        self.assertEqual(
            task["error_code"], "ERR_AUTOMATION_FAILURE",
            f"Expected 'ERR_AUTOMATION_FAILURE', got '{task['error_code']}'",
        )

    # -------------------------------------------------------------------
    # Scenario 15: Duplicate Request
    # -------------------------------------------------------------------
    def test_15_duplicate_request(self):
        """
        Submitting the same idempotency_key twice raises DuplicateRequestError
        on the second call.
        """
        mock_adapter = MagicMock()
        mock_adapter.execute_plan_step.return_value = _make_success_exec_result()

        with patch("api.orchestrator.TaskPlanner", return_value=_make_mock_planner()), \
             patch("api.orchestrator.get_installed_apps", return_value=_NOTEPAD_APP_LIST):

            orchestrator = self._make_orchestrator(mock_adapter)
            # First call — should succeed
            orchestrator.run_pipeline(
                "Open Notepad", input_type="text", idempotency_key="idem-key-001"
            )
            # Second call with same key — must raise DuplicateRequestError
            with self.assertRaises(DuplicateRequestError):
                orchestrator.run_pipeline(
                    "Open Notepad", input_type="text", idempotency_key="idem-key-001"
                )

    # -------------------------------------------------------------------
    # Scenario 16: Voice and Text Same Pipeline
    # -------------------------------------------------------------------
    def test_16_voice_and_text_same_pipeline(self):
        """
        Running the pipeline with input_type='text' and input_type='voice'
        for the same command both produce the same selected_application.
        """
        mock_adapter = MagicMock()
        mock_adapter.execute_plan_step.return_value = _make_success_exec_result()

        with patch("api.orchestrator.TaskPlanner", return_value=_make_mock_planner()), \
             patch("api.orchestrator.get_installed_apps", return_value=_NOTEPAD_APP_LIST):

            orchestrator = self._make_orchestrator(mock_adapter)

            task_text = orchestrator.run_pipeline("Open Notepad", input_type="text")
            task_voice = orchestrator.run_pipeline("Open Notepad", input_type="voice")

        self.assertIsNotNone(
            task_text.get("selected_application"),
            "Text pipeline: selected_application should not be None",
        )
        self.assertIsNotNone(
            task_voice.get("selected_application"),
            "Voice pipeline: selected_application should not be None",
        )
        self.assertEqual(
            task_text["selected_application"],
            task_voice["selected_application"],
            "Text and voice pipelines should produce the same selected_application",
        )

    # -------------------------------------------------------------------
    # Scenario 17: Catalogue returns ≥15 entries
    # -------------------------------------------------------------------
    def test_17_catalogue_returns_at_least_15_entries(self):
        """get_windows_catalogue() returns a list with at least 15 entries."""
        entries = get_windows_catalogue()
        self.assertIsInstance(entries, list, "Expected a list from get_windows_catalogue()")
        self.assertGreaterEqual(
            len(entries), 15,
            f"Expected ≥15 catalogue entries, got {len(entries)}",
        )

    # -------------------------------------------------------------------
    # Scenario 18: Structured Request Fields Present After Successful Launch
    # -------------------------------------------------------------------
    def test_18_structured_request_fields_present(self):
        """
        After a successful pipeline run, the task dict contains non-None
        selected_application, application_id, and structured_request.
        """
        mock_adapter = MagicMock()
        mock_adapter.execute_plan_step.return_value = _make_success_exec_result()

        with patch("api.orchestrator.TaskPlanner", return_value=_make_mock_planner()), \
             patch("api.orchestrator.get_installed_apps", return_value=_NOTEPAD_APP_LIST):

            orchestrator = self._make_orchestrator(mock_adapter)
            task = orchestrator.run_pipeline("Open Notepad", input_type="text")

        self.assertIsNotNone(
            task.get("selected_application"),
            "Task should have a non-None selected_application",
        )
        self.assertIsNotNone(
            task.get("application_id"),
            "Task should have a non-None application_id",
        )
        self.assertIsNotNone(
            task.get("structured_request"),
            "Task should have a non-None structured_request",
        )


if __name__ == "__main__":
    unittest.main()
