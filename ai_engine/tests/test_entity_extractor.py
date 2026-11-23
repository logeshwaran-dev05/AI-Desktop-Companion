
import unittest

from ai_engine.nlp.entity_extractor import EntityExtractor


class TestEntityExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = EntityExtractor()

    def test_extract_notepad(self):
        result = self.extractor.extract_entities(
            "Open Notepad", "open_application"
        )
        self.assertEqual(result["application"], "notepad")

    def test_extract_chrome(self):
        result = self.extractor.extract_entities(
            "Launch Google Chrome", "open_application"
        )
        self.assertEqual(result["application"], "chrome")

    def test_extract_calculator(self):
        result = self.extractor.extract_entities(
            "Open calc", "open_application"
        )
        self.assertEqual(result["application"], "calculator")

    def test_extract_move_window(self):
        result = self.extractor.extract_entities(
            "Move the window", "move_window"
        )
        self.assertEqual(result["action"], "move")
        self.assertEqual(result["target"], "window")

    def test_extract_maximize_window(self):
        result = self.extractor.extract_entities(
            "Make it full screen", "maximize_window"
        )
        self.assertEqual(result["action"], "maximize")
        self.assertEqual(result["target"], "window")

    # New tests for multi-step command understanding

    def test_extract_first_video_ordinal(self):
        result = self.extractor.extract_entities(
            "Play the first video", "play_video"
        )
        self.assertEqual(result["ordinal"], 0)
        self.assertEqual(result["video_index"], 0)

    def test_extract_second_video_ordinal(self):
        result = self.extractor.extract_entities(
            "Play the second video", "play_video"
        )
        self.assertEqual(result["ordinal"], 1)
        self.assertEqual(result["video_index"], 1)

    def test_extract_numeric_ordinal(self):
        result = self.extractor.extract_entities(
            "Play the 2nd video", "play_video"
        )
        self.assertEqual(result["ordinal"], 1)
        self.assertEqual(result["video_index"], 1)

    def test_extract_prompt(self):
        result = self.extractor.extract_entities(
            "Open ChatGPT and ask explain artificial intelligence",
            "multi_step"
        )
        self.assertEqual(
            result["prompt"],
            "explain artificial intelligence"
        )

    def test_extract_search_query(self):
        result = self.extractor.extract_entities(
            "Open YouTube and search for lofi hip hop",
            "multi_step"
        )
        self.assertEqual(result["search_query"], "lofi hip hop")

    def test_extract_chrome_profile_name(self):
        result = self.extractor.extract_entities(
            "Open YouTube using my Boovi Chrome profile",
            "multi_step"
        )
        self.assertEqual(result["profile_name"], "Boovi")


if __name__ == "__main__":
    unittest.main()
