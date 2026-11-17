
import unittest

from ai_engine.nlp.semantic_matcher import SemanticMatcher


class TestSemanticMatcher(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.matcher = SemanticMatcher()

    def test_open_application(self):
        result = self.matcher.predict_intent("Open Notepad")
        self.assertEqual(result["intent"], "open_application")
        self.assertEqual(result["status"], "recognized")

    def test_move_window(self):
        result = self.matcher.predict_intent("Move the window")
        self.assertEqual(result["intent"], "move_window")
        self.assertEqual(result["status"], "recognized")

    def test_drag_window(self):
        result = self.matcher.predict_intent("Drag this window")
        self.assertEqual(result["intent"], "move_window")
        self.assertEqual(result["status"], "recognized")

    def test_maximize_window(self):
        result = self.matcher.predict_intent("Maximize the window")
        self.assertEqual(result["intent"], "maximize_window")
        self.assertEqual(result["status"], "recognized")

    def test_full_screen(self):
        result = self.matcher.predict_intent("Make it full screen")
        self.assertEqual(result["intent"], "maximize_window")
        self.assertEqual(result["status"], "recognized")

    def test_empty_input(self):
        result = self.matcher.predict_intent("")
        self.assertIsNone(result["intent"])
        self.assertEqual(result["status"], "empty_input")

    def test_unsupported_command(self):
        result = self.matcher.predict_intent("Do something")
        self.assertIsNone(result["intent"])
        self.assertEqual(result["status"], "unsupported")

    def test_unclear_command(self):
        result = self.matcher.predict_intent("I want to write something")
        self.assertIsNone(result["intent"])
        self.assertEqual(result["status"], "unsupported")


if __name__ == "__main__":
    unittest.main()
