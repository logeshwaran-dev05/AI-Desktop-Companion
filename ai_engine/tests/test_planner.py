
import unittest

from ai_engine.schemas.command_schema import CommandRequest
from ai_engine.planner.task_planner import TaskPlanner


class TestTaskPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = TaskPlanner()

    # Test 1: Open Notepad
    def test_open_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Notepad")
        )

        self.assertEqual(response.intent, "open_application")
        self.assertEqual(response.entities.application, "Notepad")
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(len(response.steps), 1)

    # Test 2: Launch Notepad
    def test_launch_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Launch Notepad")
        )

        self.assertEqual(response.status, "plan_ready")

    # Test 3: Start Notepad
    def test_start_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Start Notepad")
        )

        self.assertEqual(response.status, "plan_ready")

    # Test 4: Missing application
    def test_missing_application(self):
        response = self.planner.process_command(
            CommandRequest(text="Open")
        )

        self.assertEqual(
            response.status, "clarification_required"
        )
        self.assertTrue(response.requires_clarification)

    # Test 5: Unsupported application
    def test_unsupported_application(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Photoshop")
        )

        self.assertEqual(response.status, "unsupported")
        self.assertIn("not currently supported", response.message)

    # Test 6: Unsupported command
    def test_unsupported_command(self):
        response = self.planner.process_command(
            CommandRequest(text="Delete a file")
        )

        self.assertEqual(response.status, "unsupported")

    # Test 7: Empty input
    def test_empty_input(self):
        response = self.planner.process_command(
            CommandRequest(text="")
        )

        self.assertEqual(
            response.status, "clarification_required"
        )

    # Test 8: General question
    def test_general_question(self):
        response = self.planner.process_command(
            CommandRequest(text="What is Python?")
        )

        self.assertEqual(response.intent, "general_question")


if __name__ == "__main__":
    unittest.main()
