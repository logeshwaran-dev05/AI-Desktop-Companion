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
        with patch("windows_automation.gui_primitives.clipboard_copy", return_value="Sample Copied Output") as mock_copy:
            res = self.executor.execute(req)
            self.assertEqual(res.status, "completed")
            mock_copy.assert_called_once()
            self.assertEqual(res.verification.details.get("copied_text"), "Sample Copied Output")

    def test_clipboard_paste_action(self):
        req = ActionRequest(
            action_id="act-clip-paste",
            task_id="task-1",
            action_name="clipboard_paste",
            target="notepad",
            parameters={"text": "Pasted text"}
        )
        with patch("windows_automation.gui_primitives.clipboard_paste") as mock_paste:
            res = self.executor.execute(req)
            self.assertEqual(res.status, "completed")
            mock_paste.assert_called_once_with(target_app="notepad", text="Pasted text")

    def test_click_youtube_result_action(self):
        req = ActionRequest(
            action_id="act-yt-click",
            task_id="task-1",
            action_name="click_youtube_result",
            target="active_window",
            parameters={"ordinal_index": 2}
        )
        with patch("windows_automation.gui_primitives.click_youtube_result") as mock_click:
            res = self.executor.execute(req)
            self.assertEqual(res.status, "completed")
            self.assertEqual(res.verification_status, "verified")
            mock_click.assert_called_once_with(ordinal_index=2)
            self.assertEqual(res.verification.details.get("ordinal_index"), 2)

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

    def test_direct_type_text(self):
        from windows_automation.gui_primitives import type_text
        with patch("windows_automation.gui_primitives.send_unicode_char") as mock_char, \
             patch("windows_automation.gui_primitives.press_vk_key") as mock_key:
            type_text("Hi", press_enter=True, delay=0)
            self.assertEqual(mock_char.call_count, 2)
            mock_key.assert_called_once()

    def test_direct_clipboard_copy(self):
        from windows_automation.gui_primitives import clipboard_copy
        with patch("windows_automation.gui_primitives.press_hotkey") as mock_hotkey, \
             patch("pyperclip.paste", return_value="pyperclip_copied"):
            result = clipboard_copy()
            mock_hotkey.assert_called_once_with("ctrl", "c")
            self.assertEqual(result, "pyperclip_copied")

    def test_direct_clipboard_paste(self):
        from windows_automation.gui_primitives import clipboard_paste
        with patch("windows_automation.gui_primitives.focus_window_by_title") as mock_focus, \
             patch("windows_automation.gui_primitives.press_hotkey") as mock_hotkey, \
             patch("pyperclip.copy") as mock_copy:
            res = clipboard_paste(target_app="Notepad", text="Text to paste")
            self.assertTrue(res)
            mock_copy.assert_called_once_with("Text to paste")
            mock_focus.assert_called_once_with("Notepad")
            mock_hotkey.assert_called_once_with("ctrl", "v")

    def test_direct_click_youtube_result(self):
        from windows_automation.gui_primitives import click_youtube_result
        with patch("windows_automation.gui_primitives.focus_window_by_title", return_value=True), \
             patch("windows_automation.gui_primitives.mouse_click") as mock_mouse:
            res = click_youtube_result(ordinal_index=3)
            self.assertTrue(res)
            mock_mouse.assert_called_once_with(520, 280 + 2 * 180)


if __name__ == "__main__":
    unittest.main()
