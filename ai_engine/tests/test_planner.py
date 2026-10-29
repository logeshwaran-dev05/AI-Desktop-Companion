
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
        result = self.planner.process_command(
            CommandRequest(text="Open Calculator")
        )
        self.assertEqual(result.status, "plan_ready")
        self.assertEqual(result.entities.application, "Calculator")

    def test_open_chrome(self):
        result = self.planner.process_command(
            CommandRequest(text="Open Chrome")
        )
        self.assertEqual(result.status, "plan_ready")
        self.assertEqual(result.entities.application, "Google Chrome")

    def test_open_paint(self):
        result = self.planner.process_command(
            CommandRequest(text="Open Paint")
        )
        self.assertEqual(result.status, "plan_ready")
        self.assertEqual(result.entities.application, "Paint")

    def test_open_photoshop(self):
        result = self.planner.process_command(
            CommandRequest(text="Open Photoshop")
        )
        self.assertEqual(result.status, "unsupported")

    def test_open_visual_studio_ambiguous(self):
        result = self.planner.process_command(
            CommandRequest(text="Open Visual Studio")
        )
        self.assertEqual(result.status, "clarification_required")
    
   
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



if __name__ == "__main__":
    unittest.main()
