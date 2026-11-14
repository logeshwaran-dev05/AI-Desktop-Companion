
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


if __name__ == "__main__":
    unittest.main()
