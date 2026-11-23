"""
Unit and integration tests for Universal App Discovery, Packaged Apps (WhatsApp, Calculator),
Smart Aliases, and Controlled Launching.
"""

import unittest
from unittest.mock import MagicMock

from windows_automation.schemas import ApplicationRecord, ActionRequest, AuthorizationDecision
from windows_automation.catalogue import ApplicationCatalogue
from windows_automation.policy import WindowsActionPolicy
from windows_automation.executor import WindowsAutomationExecutor
from windows_automation.verifier import WindowsWindowVerifier


class TestUniversalPackagedApps(unittest.TestCase):

    def setUp(self):
        self.catalogue = ApplicationCatalogue()
        self.policy = WindowsActionPolicy(catalogue=self.catalogue)

    def test_01_packaged_record_creation(self):
        """Test ApplicationRecord properly represents modern packaged applications."""
        initial_count = self.catalogue.count()
        rec = ApplicationRecord(
            app_id="app_whatsapp",
            display_name="WhatsApp",
            normalized_name="whatsapp",
            executable_path="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
            source="start_apps",
            app_type="packaged_app",
            status="available",
            launch_method="appx_packaged",
            app_user_model_id="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
            aliases=["whatsapp", "whats app", "wa"],
        )
        self.catalogue.add_record(rec)
        self.assertEqual(self.catalogue.count(), initial_count + 1)

    def test_02_whatsapp_resolution_and_aliases(self):
        """Test WhatsApp resolves via natural variations and aliases."""
        rec = ApplicationRecord(
            app_id="app_whatsapp",
            display_name="WhatsApp",
            normalized_name="whatsapp",
            executable_path="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
            source="start_apps",
            app_type="packaged_app",
            status="available",
            launch_method="appx_packaged",
            app_user_model_id="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
            aliases=["whatsapp", "whats app", "wa"],
        )
        self.catalogue.add_record(rec)

        for q in ["WhatsApp", "whatsapp", "whats app", "wa", "WHATSAPP"]:
            res = self.catalogue.resolve(q)
            self.assertEqual(res.status, "resolved", f"Failed for query '{q}'")
            self.assertEqual(res.matched_record.display_name, "WhatsApp")

    def test_03_policy_allows_valid_packaged_apps(self):
        """Policy permits packaged applications with valid AUMID targets."""
        rec = ApplicationRecord(
            app_id="app_whatsapp",
            display_name="WhatsApp",
            normalized_name="whatsapp",
            executable_path="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
            source="start_apps",
            app_type="packaged_app",
            status="available",
            launch_method="appx_packaged",
            app_user_model_id="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
        )
        self.catalogue.add_record(rec)

        req = ActionRequest(
            action_id="act_1",
            task_id="task_1",
            step_id=1,
            action_name="open_application",
            target="whatsapp",
            resolved_record=rec,
        )
        is_valid, err_code, _ = self.policy.validate_request(req)
        self.assertTrue(is_valid)
        self.assertIsNone(err_code)

    def test_04_policy_rejects_unsafe_packaged_targets(self):
        """Policy rejects packaged application targets containing command injection tokens."""
        rec = ApplicationRecord(
            app_id="app_malicious",
            display_name="Malicious App",
            normalized_name="malicious app",
            executable_path="malicious; calc.exe",
            source="start_apps",
            app_type="packaged_app",
            launch_method="appx_packaged",
            app_user_model_id="malicious; calc.exe",
        )
        self.catalogue.add_record(rec)

        req = ActionRequest(
            action_id="act_2",
            task_id="task_2",
            step_id=1,
            action_name="open_application",
            target="malicious app",
            resolved_record=rec,
        )
        is_valid, err_code, _ = self.policy.validate_request(req)
        self.assertFalse(is_valid)
        self.assertEqual(err_code, "ERR_TARGET_NOT_ALLOWLISTED")

    def test_05_controlled_launch_packaged_app(self):
        """Test controlled launch uses shell shortcut launcher without shell=True."""
        mock_launcher = MagicMock()
        mock_verifier = WindowsWindowVerifier(
            window_finder_override=lambda pid, name=None: {
                "hwnd": 9999,
                "window_pid": 1234,
                "window_title": "WhatsApp",
                "window_class": "ApplicationFrameWindow",
                "width": 800,
                "height": 600,
            }
        )

        executor = WindowsAutomationExecutor(
            policy=self.policy,
            verifier=mock_verifier,
            shortcut_launcher=mock_launcher,
        )

        rec = ApplicationRecord(
            app_id="app_whatsapp",
            display_name="WhatsApp",
            normalized_name="whatsapp",
            executable_path="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
            source="start_apps",
            app_type="packaged_app",
            status="available",
            launch_method="appx_packaged",
            app_user_model_id="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
        )
        self.catalogue.add_record(rec)

        req = ActionRequest(
            action_id="act_3",
            task_id="task_3",
            step_id=1,
            action_name="open_application",
            target="whatsapp",
            resolved_record=rec,
            authorization=AuthorizationDecision(decision_id="dec_1", permission_status="granted"),
        )

        res = executor.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.verification_status, "launch_verified")
        mock_launcher.assert_called_once_with("shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App")


if __name__ == "__main__":
    unittest.main()
