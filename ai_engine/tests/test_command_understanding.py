
import unittest
from ai_engine.nlp.command_understanding import CommandUnderstanding


class TestCommandUnderstanding(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = CommandUnderstanding()

    def test_open_notepad(self):
        result = self.engine.understand("Open Notepad")
        self.assertEqual(result["intent"], "open_application")
        self.assertEqual(result["entities"]["application"], "notepad")
        self.assertEqual(result["status"], "recognized")

    def test_launch_chrome(self):
        result = self.engine.understand("Launch Google Chrome")
        self.assertEqual(result["intent"], "open_application")
        self.assertEqual(result["entities"]["application"], "chrome")

    def test_move_window(self):
        result = self.engine.understand("Move the window")
        self.assertEqual(result["intent"], "move_window")
        self.assertEqual(result["entities"]["action"], "move")

    def test_maximize_window(self):
        result = self.engine.understand("Make it full screen")
        self.assertEqual(result["intent"], "maximize_window")
        self.assertEqual(result["entities"]["action"], "maximize")

    def test_unsupported_command(self):
        result = self.engine.understand("Do something")
        self.assertIsNone(result["intent"])
        self.assertEqual(result["status"], "unsupported")


if __name__ == "__main__":
    unittest.main()
