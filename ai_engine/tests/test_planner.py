
import unittest

from ai_engine.schemas.command_schema import CommandRequest
from ai_engine.planner.task_planner import TaskPlanner


class TestTaskPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = TaskPlanner()

    # Test 1: Valid application command
    def test_open_notepad(self):
        request = CommandRequest(text="Open Notepad")

        response = self.planner.process_command(request)

        self.assertEqual(response.intent, "open_application")
        self.assertEqual(response.entities.application, "Notepad")
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(len(response.steps), 1)

    # Test 2: Missing application name
    def test_missing_application(self):
        request = CommandRequest(text="Open")

        response = self.planner.process_command(request)

        self.assertTrue(response.requires_clarification)
        self.assertEqual(
            response.status, "clarification_required"
        )

    # Test 3: General question
    def test_general_question(self):
        request = CommandRequest(text="What is Python?")

        response = self.planner.process_command(request)

        self.assertEqual(response.intent, "general_question")
        self.assertEqual(response.steps, [])

    # Test 4: Unsupported application
    def test_unsupported_application(self):
        request = CommandRequest(text="Open Photoshop")

        response = self.planner.process_command(request)

        self.assertEqual(response.status, "unsupported")
        self.assertEqual(response.steps, [])

    # Test 5: Empty input
    def test_empty_input(self):
        request = CommandRequest(text="")

        response = self.planner.process_command(request)

        self.assertTrue(response.requires_clarification)
        self.assertEqual(
            response.status, "clarification_required"
        )


if __name__ == "__main__":
    unittest.main()
