import unittest
from unittest.mock import patch, MagicMock
from windows_automation.browser_profiles import (
    get_browser_profiles,
    resolve_profile_directory,
    build_chrome_launch_args,
    get_default_profile_directory,
)
from windows_automation.schemas import ActionRequest, AuthorizationDecision
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.policy import WindowsActionPolicy


class TestBrowserProfiles(unittest.TestCase):
    def test_get_profiles_returns_list(self):
        profiles = get_browser_profiles("chrome")
        self.assertIsInstance(profiles, list)
        if profiles:
            first = profiles[0]
            self.assertIn("directory", first)
            self.assertIn("name", first)

    def test_build_chrome_launch_args(self):
        args = build_chrome_launch_args(profile_dir="Profile 2", url="https://youtube.com")
        self.assertEqual(args, ["--profile-directory=Profile 2", "https://youtube.com"])

        no_profile_args = build_chrome_launch_args(url="https://chatgpt.com")
        self.assertEqual(no_profile_args, ["https://chatgpt.com"])

    def test_resolve_profile_none(self):
        self.assertIsNone(resolve_profile_directory("chrome", None))
        self.assertIsNone(resolve_profile_directory("chrome", ""))

    def test_get_default_profile_directory(self):
        default_dir = get_default_profile_directory("chrome")
        if default_dir is not None:
            self.assertIsInstance(default_dir, str)

    def test_chrome_launch_with_profile_2_in_executor(self):
        """Test that executor launches Chrome with --profile-directory='Profile 2'."""
        mock_runner = MagicMock()
        policy = WindowsActionPolicy()
        executor = WindowsAutomationExecutor(policy=policy, subprocess_runner=mock_runner)

        req = ActionRequest(
            action_id="act-chrome-prof2",
            task_id="task-prof2",
            action_name="open_application",
            target="Google Chrome",
            parameters={"profile_dir": "Profile 2"},
            authorization=AuthorizationDecision(
                decision_id="dec-prof2",
                permission_status="granted",
                requires_user_approval=False,
            )
        )
        with patch.object(executor.verifier, "verify_window_readiness") as mock_verify:
            mock_verify.return_value = MagicMock(verified=True, verification_status="verified", details={})
            executor.execute(req)
            self.assertTrue(mock_runner.called)
            called_cmd = mock_runner.call_args[0][0]
            self.assertTrue(any("--profile-directory=Profile 2" in str(arg) for arg in called_cmd))


if __name__ == "__main__":
    unittest.main()
