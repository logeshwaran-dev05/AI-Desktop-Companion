
import unittest

from ai_engine.planner.task_planner import TaskPlanner
from ai_engine.schemas.command_schema import CommandRequest


class TestTaskPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = TaskPlanner()

    def test_open_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Notepad")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_launch_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Launch Notepad")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_start_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Start Notepad")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_missing_application(self):
        response = self.planner.process_command(
            CommandRequest(text="Open")
        )
        self.assertEqual(response.status, "clarification_required")

    def test_unsupported_application(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Photoshop")
        )
        self.assertEqual(response.status, "unsupported")

    def test_unsupported_command(self):
        response = self.planner.process_command(
            CommandRequest(text="Delete a file")
        )
        self.assertEqual(response.status, "unsupported")

    def test_empty_input(self):
        response = self.planner.process_command(
            CommandRequest(text="")
        )
        self.assertEqual(response.status, "clarification_required")

    def test_general_question(self):
        response = self.planner.process_command(
            CommandRequest(text="What is Python?")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_uppercase_command(self):
        response = self.planner.process_command(
            CommandRequest(text="OPEN NOTEPAD")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_extra_spaces(self):
        response = self.planner.process_command(
            CommandRequest(text="  Open     Notepad  ")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_please_open_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Please open Notepad")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_spelling_mistake(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Notepd")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_uncertain_application_name(self):
        response = self.planner.process_command(
            CommandRequest(text="Open notep")
        )
        self.assertEqual(response.status, "clarification_required")

    def test_open_calculator(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Calculator")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Calculator")

    def test_open_chrome(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Chrome")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Google Chrome")

    def test_open_paint(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Paint")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Paint")

    def test_open_photoshop(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Photoshop")
        )
        self.assertEqual(response.status, "unsupported")

    def test_open_visual_studio_ambiguous(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Visual Studio")
        )
        self.assertEqual(response.status, "clarification_required")

    def test_mixed_case_command(self):
        response = self.planner.process_command(
            CommandRequest(text="OpEn NoTePaD")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_launch_calculator(self):
        response = self.planner.process_command(
            CommandRequest(text="Please launch Calculator")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Calculator")

    def test_could_you_start_chrome(self):
        response = self.planner.process_command(
            CommandRequest(text="Could you start Chrome")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Google Chrome")

    def test_misspelled_notepad_variant(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Notepadd")
        )
        self.assertEqual(response.status, "plan_ready")

    def test_unknown_application_name(self):
        response = self.planner.process_command(
            CommandRequest(text="Open Blender")
        )
        self.assertEqual(response.status, "unsupported")

    def test_whitespace_only_input(self):
        response = self.planner.process_command(
            CommandRequest(text="       ")
        )
        self.assertEqual(response.status, "clarification_required")

    # Application alias tests

    def test_notepad_alias(self):
        response = self.planner.process_command(
            CommandRequest(text="open note pad")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Notepad")

    def test_calculator_alias(self):
        response = self.planner.process_command(
            CommandRequest(text="open calc")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Calculator")

    def test_vscode_alias(self):
        response = self.planner.process_command(
            CommandRequest(text="open vs code")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(
            response.entities.application,
            "Visual Studio Code"
        )

    # Voice-originated command test

    def test_voice_command_opens_notepad(self):
        response = self.planner.process_command(
            CommandRequest(
                text="open notepad",
                input_type="voice",
                language="en"
            )
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Notepad")


if __name__ == "__main__":
    unittest.main()
