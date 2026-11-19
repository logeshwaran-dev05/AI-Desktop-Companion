
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
    
    # Natural language command tests

    def test_i_want_to_use_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="I want to use Notepad")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "open_application")
        self.assertEqual(response.entities.application, "Notepad")

    def test_please_start_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Please start Notepad")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Notepad")

    def test_can_you_open_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Can you open Notepad?")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Notepad")

    def test_i_need_calculator(self):
        response = self.planner.process_command(
            CommandRequest(text="I need to use Calculator")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Calculator")

    def test_could_you_launch_chrome(self):
        response = self.planner.process_command(
            CommandRequest(text="Could you launch Chrome?")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Google Chrome")
        # Additional command variation tests

    def test_run_notepad(self):
        response = self.planner.process_command(
            CommandRequest(text="Run Notepad")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Notepad")

    def test_bring_up_calculator(self):
        response = self.planner.process_command(
            CommandRequest(text="Bring up Calculator")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "Calculator")

    def test_please_run_chrome(self):
        response = self.planner.process_command(
            CommandRequest(text="Please run Chrome")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(
            response.entities.application,
            "Google Chrome"
        )

    # ── Backend Intent Fallbacks & Search Tests ──

    def test_open_chrome_intent(self):
        response = self.planner.process_command(
            CommandRequest(text="open chrome")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "open_application")
        self.assertEqual(response.steps[0].action, "open_application")
        self.assertEqual(response.steps[0].target, "chrome")

    def test_open_spotify_intent(self):
        response = self.planner.process_command(
            CommandRequest(text="open spotify")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "open_application")
        self.assertEqual(response.steps[0].action, "open_application")
        self.assertEqual(response.steps[0].target, "spotify")
        self.assertEqual(response.entities.application, "Spotify")

    def test_play_believer_on_youtube(self):
        response = self.planner.process_command(
            CommandRequest(text="play believer on youtube")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "search_web_app")
        self.assertEqual(response.steps[0].action, "search_web_app")
        self.assertEqual(response.steps[0].target, "youtube")
        self.assertEqual(response.steps[0].parameters, {"query": "believer"})
        self.assertEqual(response.entities.parameters, {"query": "believer"})
        self.assertEqual(response.entities.application, "YouTube")

    def test_search_python_tutorials_on_google(self):
        response = self.planner.process_command(
            CommandRequest(text="search python tutorials on google")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "search_web_app")
        self.assertEqual(response.steps[0].action, "search_web_app")
        self.assertEqual(response.steps[0].target, "google")
        self.assertEqual(response.steps[0].parameters, {"query": "python tutorials"})
        self.assertEqual(response.entities.parameters, {"query": "python tutorials"})
        self.assertEqual(response.entities.application, "Google")

    def test_multi_word_search_query_youtube(self):
        response = self.planner.process_command(
            CommandRequest(text="play bohemian rhapsody remastered on youtube")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "search_web_app")
        self.assertEqual(response.steps[0].target, "youtube")
        self.assertEqual(response.steps[0].parameters, {"query": "bohemian rhapsody remastered"})

    def test_multi_word_search_query_google(self):
        response = self.planner.process_command(
            CommandRequest(text="search python tutorials for beginners on google")
        )
        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "search_web_app")
        self.assertEqual(response.steps[0].target, "google")
        self.assertEqual(response.steps[0].parameters, {"query": "python tutorials for beginners"})

    def test_case_insensitive_commands(self):
        for cmd in [
            "OPEN CHROME",
            "PLAY BELIEVER ON YOUTUBE",
            "SEARCH PYTHON TUTORIALS ON GOOGLE",
            "Open Spotify",
        ]:
            response = self.planner.process_command(CommandRequest(text=cmd))
            self.assertEqual(response.status, "plan_ready")
            self.assertIn(response.intent, ("open_application", "search_web_app"))

    def test_extra_spaces_handling(self):
        response_yt = self.planner.process_command(
            CommandRequest(text="   play    believer    on    youtube   ")
        )
        self.assertEqual(response_yt.status, "plan_ready")
        self.assertEqual(response_yt.steps[0].target, "youtube")
        self.assertEqual(response_yt.steps[0].parameters, {"query": "believer"})

        response_sp = self.planner.process_command(
            CommandRequest(text="   open    spotify   ")
        )
        self.assertEqual(response_sp.status, "plan_ready")
        self.assertEqual(response_sp.steps[0].target, "spotify")

    def test_missing_search_query(self):
        for incomplete_cmd in [
            "search on google",
            "play on youtube",
            "search",
            "play",
        ]:
            response = self.planner.process_command(CommandRequest(text=incomplete_cmd))
            self.assertEqual(response.status, "clarification_required")
            self.assertTrue(response.requires_clarification)
            self.assertIsNotNone(response.clarification_question)

    def test_unknown_search_application(self):
        response = self.planner.process_command(
            CommandRequest(text="play believer on non_existent_app_xyz")
        )
        self.assertEqual(response.status, "unsupported")


if __name__ == "__main__":
    unittest.main()
