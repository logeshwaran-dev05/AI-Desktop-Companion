
import unittest

from ai_engine.planner.task_planner import TaskPlanner
from ai_engine.schemas.command_schema import CommandRequest


class TestTaskPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = TaskPlanner()

    # --------------------------------------------------
    # Basic application tests
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Application alias tests
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Voice-originated command tests
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Natural-language command tests
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Additional command variations
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Dynamic application ID tests
    # --------------------------------------------------

    def test_open_chrome_intent(self):
        response = self.planner.process_command(
            CommandRequest(text="open chrome")
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "open_application")
        self.assertEqual(
            response.steps[0].action,
            "open_application"
        )
        self.assertEqual(
            response.steps[0].target,
            "app_google_chrome"
        )

    def test_open_spotify_intent(self):
        response = self.planner.process_command(
            CommandRequest(text="open spotify")
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "open_application")
        self.assertEqual(
            response.steps[0].action,
            "open_application"
        )
        self.assertEqual(
            response.steps[0].target,
            "app_spotify"
        )
        self.assertEqual(
            response.entities.application,
            "Spotify"
        )

    def test_extra_spaces_handling(self):
        response = self.planner.process_command(
            CommandRequest(text="   open    spotify   ")
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(
            response.steps[0].target,
            "app_spotify"
        )

    def test_case_insensitive_commands(self):
        commands = [
            "OPEN CHROME",
            "OPEN SPOTIFY",
            "OPEN NOTEPAD",
        ]

        for command in commands:
            with self.subTest(command=command):
                response = self.planner.process_command(
                    CommandRequest(text=command)
                )
                self.assertEqual(response.status, "plan_ready")
                self.assertEqual(
                    response.intent,
                    "open_application"
                )

    # --------------------------------------------------
    # Deferred website-search tests
    # --------------------------------------------------
    # Website discovery and search API functionality is
    # currently paused. These tests are retained for future
    # development but are not part of the active test suite.

    @unittest.skip("Website-search functionality is currently deferred")
    def test_youtube_search_and_play_second_video(self):
        response = self.planner.process_command(
            CommandRequest(
                text="Open YouTube, search for lofi hip hop, and play the second video"
            )
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "multi_step")
        self.assertEqual(len(response.steps), 3)

        self.assertEqual(response.steps[0].action, "open_website")
        self.assertEqual(response.steps[1].action, "search")
        self.assertEqual(response.steps[1].target, "lofi hip hop")
        self.assertEqual(response.steps[2].action, "play_video")
        self.assertEqual(response.steps[2].target, "1")

        self.assertEqual(response.steps[1].depends_on, [1])
        self.assertEqual(response.steps[2].depends_on, [2])

    @unittest.skip("Website-search functionality is currently deferred")
    def test_chatgpt_open_and_ask_prompt(self):
        response = self.planner.process_command(
            CommandRequest(
                text="Open ChatGPT and ask explain artificial intelligence"
            )
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "multi_step")
        self.assertEqual(len(response.steps), 2)

        self.assertEqual(response.steps[0].action, "open_website")
        self.assertEqual(response.steps[1].action, "ask_prompt")
        self.assertEqual(
            response.steps[1].target,
            "explain artificial intelligence"
        )

    @unittest.skip("Website-search functionality is currently deferred")
    def test_youtube_profile_and_search(self):
        response = self.planner.process_command(
            CommandRequest(
                text="Open YouTube using my Boovi Chrome profile, search for music, and play the second video"
            )
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.entities.application, "youtube")

        self.assertEqual(
            response.entities.parameters["profile_name"],
            "Boovi"
        )
        self.assertEqual(
            response.entities.parameters["profile_directory"],
            "Default"
        )
        self.assertEqual(
            response.entities.parameters["search_query"],
            "music"
        )
        self.assertEqual(
            response.entities.parameters["video_index"],
            1
        )

    @unittest.skip("Website-search functionality is currently deferred")
    def test_youtube_steps_are_ordered(self):
        response = self.planner.process_command(
            CommandRequest(
                text="Open YouTube, search for music, and play the first video"
            )
        )

        self.assertEqual(
            [step.step_id for step in response.steps],
            [1, 2, 3]
        )
        self.assertEqual(
            [step.depends_on for step in response.steps],
            [[], [1], [2]]
        )

    @unittest.skip("Website-search functionality is currently deferred")
    def test_youtube_play_without_video_number(self):
        response = self.planner.process_command(
            CommandRequest(
                text="Open YouTube and play a video"
            )
        )

        self.assertTrue(response.requires_clarification)
        self.assertEqual(
            response.status,
            "clarification_required"
        )

    @unittest.skip("Website-search functionality is currently deferred")
    def test_play_believer_on_youtube(self):
        response = self.planner.process_command(
            CommandRequest(text="play believer on youtube")
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "search_web_app")
        self.assertEqual(
            response.steps[0].action,
            "search_web_app"
        )
        self.assertEqual(response.steps[0].target, "youtube")
        self.assertEqual(
            response.steps[0].parameters,
            {"query": "believer"}
        )
        self.assertEqual(
            response.entities.parameters,
            {"query": "believer"}
        )
        self.assertEqual(response.entities.application, "YouTube")

    @unittest.skip("Website-search functionality is currently deferred")
    def test_search_python_tutorials_on_google(self):
        response = self.planner.process_command(
            CommandRequest(text="search python tutorials on google")
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "search_web_app")
        self.assertEqual(
            response.steps[0].action,
            "search_web_app"
        )
        self.assertEqual(response.steps[0].target, "google")
        self.assertEqual(
            response.steps[0].parameters,
            {"query": "python tutorials"}
        )
        self.assertEqual(
            response.entities.parameters,
            {"query": "python tutorials"}
        )
        self.assertEqual(response.entities.application, "Google")

    @unittest.skip("Website-search functionality is currently deferred")
    def test_multi_word_search_query_youtube(self):
        response = self.planner.process_command(
            CommandRequest(
                text="play bohemian rhapsody remastered on youtube"
            )
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "search_web_app")
        self.assertEqual(response.steps[0].target, "youtube")
        self.assertEqual(
            response.steps[0].parameters,
            {"query": "bohemian rhapsody remastered"}
        )

    @unittest.skip("Website-search functionality is currently deferred")
    def test_multi_word_search_query_google(self):
        response = self.planner.process_command(
            CommandRequest(
                text="search python tutorials for beginners on google"
            )
        )

        self.assertEqual(response.status, "plan_ready")
        self.assertEqual(response.intent, "search_web_app")
        self.assertEqual(response.steps[0].target, "google")
        self.assertEqual(
            response.steps[0].parameters,
            {"query": "python tutorials for beginners"}
        )

    @unittest.skip("Website-search functionality is currently deferred")
    def test_missing_search_query(self):
        for command in [
            "search on google",
            "play on youtube",
            "search",
            "play",
        ]:
            with self.subTest(command=command):
                response = self.planner.process_command(
                    CommandRequest(text=command)
                )
                self.assertEqual(
                    response.status,
                    "clarification_required"
                )
                self.assertTrue(response.requires_clarification)
                self.assertIsNotNone(
                    response.clarification_question
                )

    def test_unknown_search_application(self):
        response = self.planner.process_command(
            CommandRequest(
                text="play believer on non_existent_app_xyz"
            )
        )
        self.assertEqual(response.status, "unsupported")


if __name__ == "__main__":
    unittest.main()
