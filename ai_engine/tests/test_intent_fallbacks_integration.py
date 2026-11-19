"""
Integration and End-to-End Tests for Backend Intent Fallbacks.

Tests:
1. Command intent parsing (open_application, search_web_app).
2. Schema validation (parameters preservation, action types).
3. 50 Popular applications catalogue coverage across all categories.
4. API / Orchestrator integration (run_pipeline, structured requests).
5. Web fallback and search execution.
"""

import unittest
from unittest.mock import MagicMock

from ai_engine.planner.task_planner import TaskPlanner
from ai_engine.schemas.command_schema import (
    CommandRequest,
    CommandEntities,
    PlanStep,
    PlannerResponse,
)
from ai_engine.catalogue import get_installed_apps
from api.orchestrator import TaskOrchestrator
from windows_automation.schemas import ActionRequest, AuthorizationDecision
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.policy import WindowsActionPolicy


class TestIntentFallbacksIntegration(unittest.TestCase):

    def setUp(self):
        self.planner = TaskPlanner()
        self.orchestrator = TaskOrchestrator()

    # -----------------------------------------------------------------------
    # 1. Schema Validation Tests
    # -----------------------------------------------------------------------

    def test_schema_plan_step_parameters(self):
        step = PlanStep(
            step_id=1,
            action="search_web_app",
            target="youtube",
            expected_outcome="Play video",
            parameters={"query": "believer"}
        )
        self.assertEqual(step.action, "search_web_app")
        self.assertEqual(step.target, "youtube")
        self.assertEqual(step.parameters, {"query": "believer"})

    def test_schema_command_entities_parameters(self):
        entities = CommandEntities(
            application="YouTube",
            parameters={"query": "believer"}
        )
        self.assertEqual(entities.application, "YouTube")
        self.assertEqual(entities.parameters["query"], "believer")

    def test_schema_planner_response_integrity(self):
        step = PlanStep(
            step_id=1,
            action="search_web_app",
            target="google",
            parameters={"query": "python tutorials"}
        )
        entities = CommandEntities(
            application="Google",
            parameters={"query": "python tutorials"}
        )
        res = PlannerResponse(
            intent="search_web_app",
            entities=entities,
            steps=[step],
            requires_clarification=False,
            clarification_question=None,
            status="plan_ready",
            message="Plan ready"
        )
        self.assertEqual(res.intent, "search_web_app")
        self.assertEqual(res.status, "plan_ready")
        self.assertEqual(len(res.steps), 1)
        self.assertEqual(res.steps[0].parameters["query"], "python tutorials")

    # -----------------------------------------------------------------------
    # 2. 50 Popular Applications Coverage Test
    # -----------------------------------------------------------------------

    def test_catalogue_contains_50_plus_popular_apps(self):
        apps = get_installed_apps()
        self.assertGreaterEqual(len(apps), 50)

        app_ids = {a["app_id"] for a in apps}

        # Media
        for expected in ["youtube", "spotify", "netflix", "primevideo", "disney"]:
            self.assertIn(expected, app_ids, f"Missing Media app: {expected}")

        # Productivity
        for expected in [
            "gmail", "drive", "docs", "sheets", "meet", "chatgpt", "claude",
            "notion", "slack", "trello", "word", "excel", "powerpoint", "outlook", "onedrive"
        ]:
            self.assertIn(expected, app_ids, f"Missing Productivity app: {expected}")

        # Developer
        for expected in [
            "github", "gitlab", "stackoverflow", "vscode", "terminal",
            "replit", "codepen", "dockerhub", "aws"
        ]:
            self.assertIn(expected, app_ids, f"Missing Developer app: {expected}")

        # Social and Communication
        for expected in [
            "whatsapp", "linkedin", "twitter", "reddit", "instagram",
            "facebook", "discord", "telegram", "zoom", "teams"
        ]:
            self.assertIn(expected, app_ids, f"Missing Social app: {expected}")

        # Learning and Other Services
        for expected in [
            "coursera", "udemy", "wikipedia", "figma", "canva", "jira",
            "calendar", "maps", "pinterest"
        ]:
            self.assertIn(expected, app_ids, f"Missing Learning app: {expected}")

    # -----------------------------------------------------------------------
    # 3. API / Orchestrator Integration Tests
    # -----------------------------------------------------------------------

    def test_orchestrator_play_believer_on_youtube(self):
        task = self.orchestrator.run_pipeline("play believer on youtube", auto_execute=False)
        self.assertEqual(task["intent"], "search_web_app")
        self.assertEqual(task["selected_application"], "YouTube")
        self.assertEqual(task["application_id"], "youtube")
        self.assertIsNotNone(task["structured_request"])
        self.assertEqual(task["structured_request"]["action"], "search_web_app")
        self.assertEqual(task["structured_request"]["application_id"], "youtube")
        self.assertEqual(task["structured_request"]["parameters"], {"query": "believer"})

    def test_orchestrator_search_python_tutorials_on_google(self):
        task = self.orchestrator.run_pipeline("search python tutorials on google", auto_execute=False)
        self.assertEqual(task["intent"], "search_web_app")
        self.assertEqual(task["selected_application"], "Google")
        self.assertEqual(task["application_id"], "google")
        self.assertIsNotNone(task["structured_request"])
        self.assertEqual(task["structured_request"]["action"], "search_web_app")
        self.assertEqual(task["structured_request"]["application_id"], "google")
        self.assertEqual(task["structured_request"]["parameters"], {"query": "python tutorials"})

    def test_orchestrator_open_spotify(self):
        task = self.orchestrator.run_pipeline("open spotify", auto_execute=False)
        self.assertEqual(task["intent"], "open_application")
        self.assertEqual(task["selected_application"], "Spotify")
        self.assertEqual(task["application_id"], "spotify")
        self.assertIsNotNone(task["structured_request"])
        self.assertEqual(task["structured_request"]["action"], "launch_application")
        self.assertEqual(task["structured_request"]["application_id"], "spotify")

    def test_orchestrator_open_chrome(self):
        task = self.orchestrator.run_pipeline("open chrome", auto_execute=False)
        self.assertEqual(task["intent"], "open_application")
        self.assertEqual(task["selected_application"], "Google Chrome")
        self.assertEqual(task["application_id"], "chrome")
        self.assertIsNotNone(task["structured_request"])
        self.assertEqual(task["structured_request"]["action"], "launch_application")
        self.assertEqual(task["structured_request"]["application_id"], "chrome")

    # -----------------------------------------------------------------------
    # 4. Web Fallback & Search Execution Tests
    # -----------------------------------------------------------------------

    def test_executor_search_web_app_execution(self):
        runner_mock = MagicMock()
        executor = WindowsAutomationExecutor(
            policy=WindowsActionPolicy(),
            subprocess_runner=runner_mock,
        )

        request = ActionRequest(
            action_id="act-search-1",
            task_id="task-1",
            action_name="search_web_app",
            target="YouTube",
            parameters={"query": "believer"},
            authorization=AuthorizationDecision(
                decision_id="dec-1",
                permission_status="granted",
                requires_user_approval=False,
            )
        )

        result = executor.execute(request)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "verified")
        self.assertIsNotNone(result.verification)
        self.assertTrue(result.verification.verified)
        self.assertIn("youtube.com", result.verification.details.get("url", ""))
        self.assertIn("believer", result.verification.details.get("url", ""))

    def test_executor_web_fallback_execution_for_uninstalled_service(self):
        runner_mock = MagicMock()
        executor = WindowsAutomationExecutor(
            policy=WindowsActionPolicy(),
            subprocess_runner=runner_mock,
        )

        request = ActionRequest(
            action_id="act-fallback-1",
            task_id="task-2",
            action_name="open_application",
            target="Netflix",
            parameters={},
            authorization=AuthorizationDecision(
                decision_id="dec-2",
                permission_status="granted",
                requires_user_approval=False,
            )
        )

        result = executor.execute(request)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "verified")
        self.assertIsNotNone(result.verification)
        self.assertTrue(result.verification.verified)
        self.assertIn("netflix.com", result.verification.details.get("url", ""))


if __name__ == "__main__":
    unittest.main()
