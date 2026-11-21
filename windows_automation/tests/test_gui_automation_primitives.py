import unittest
from unittest.mock import patch, MagicMock
from windows_automation.schemas import ActionRequest
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.policy import WindowsActionPolicy


class TestGuiAutomationPrimitives(unittest.TestCase):
    def setUp(self):
        self.policy = WindowsActionPolicy()
        self.executor = WindowsAutomationExecutor(policy=self.policy)

    def test_navigate_url_action(self):
        req = ActionRequest(
            action_id="act-nav-1",
            task_id="task-1",
            action_name="navigate_url",
            target="https://chatgpt.com",
            parameters={"profile_name": "LOKI"}
        )
        with patch.object(self.executor, "_open_url") as mock_open:
            res = self.executor.execute(req)
            self.assertEqual(res.status, "completed")
            self.assertEqual(res.verification_status, "verified")
            mock_open.assert_called_once_with("https://chatgpt.com", profile_dir=None, profile_name="LOKI")

    def test_type_text_action(self):
        req = ActionRequest(
            action_id="act-type-1",
            task_id="task-1",
            action_name="type_text",
            target="notepad",
            parameters={"text": "Hello World", "press_enter": True}
        )
        with patch("windows_automation.gui_primitives.type_text") as mock_type, \
             patch("windows_automation.gui_primitives.focus_window_by_title") as mock_focus:
            res = self.executor.execute(req)
            self.assertEqual(res.status, "completed")
            mock_focus.assert_called_once_with("notepad")
            mock_type.assert_called_once_with("Hello World", press_enter=True)

    def test_clipboard_copy_action(self):
        req = ActionRequest(
            action_id="act-clip-copy",
            task_id="task-1",
            action_name="clipboard_copy",
            target="active_window"
        )
        with patch("windows_automation.gui_primitives.press_hotkey") as mock_hotkey, \
             patch("windows_automation.gui_primitives.get_clipboard_text", return_value="Sample Copied Output"):
            res = self.executor.execute(req)
            self.assertEqual(res.status, "completed")
            mock_hotkey.assert_called_once_with("ctrl", "c")
            self.assertEqual(res.verification.details.get("copied_text"), "Sample Copied Output")

    def test_clipboard_paste_action(self):
        req = ActionRequest(
            action_id="act-clip-paste",
            task_id="task-1",
            action_name="clipboard_paste",
            target="notepad",
            parameters={"text": "Pasted text"}
        )
        with patch("windows_automation.gui_primitives.press_hotkey") as mock_hotkey, \
             patch("windows_automation.gui_primitives.set_clipboard_text") as mock_set, \
             patch("windows_automation.gui_primitives.focus_window_by_title") as mock_focus:
            res = self.executor.execute(req)
            self.assertEqual(res.status, "completed")
            mock_set.assert_called_once_with("Pasted text")
            mock_focus.assert_called_once_with("notepad")
            mock_hotkey.assert_called_once_with("ctrl", "v")

    def test_wait_action(self):
        req = ActionRequest(
            action_id="act-wait-1",
            task_id="task-1",
            action_name="wait",
            target="active_window",
            parameters={"seconds": 0.05}
        )
        res = self.executor.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.verification.details.get("waited_seconds"), 0.05)


if __name__ == "__main__":
    unittest.main()
