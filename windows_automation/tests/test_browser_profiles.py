import unittest
from windows_automation.browser_profiles import (
    get_browser_profiles,
    resolve_profile_directory,
    build_chrome_launch_args,
)


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


if __name__ == "__main__":
    unittest.main()
