import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from client.gui.settings_widget import SettingsScreen  # noqa: E402


class SettingsScreenTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_scan_settings_save_min_size_bytes(self):
        with patch(
            "client.gui.settings_widget.load_user_settings",
            return_value={
                "theme": "light",
                "min_age_months": 6,
                "min_size_bytes": 2048,
                "skip_duration_days": 30,
                "skip_review_mode": "days",
            },
        ):
            screen = SettingsScreen()

        screen.age_spin.setValue(9)
        screen.size_spin.setValue(128)
        screen.skip_spin.setValue(14)

        with (
            patch("client.gui.settings_widget.save_user_settings") as save_settings,
            patch.object(QMessageBox, "information"),
        ):
            screen.save_settings()

        save_settings.assert_called_once()
        settings = save_settings.call_args.args[0]
        self.assertEqual(settings["min_age_months"], 9)
        self.assertEqual(settings["min_size_bytes"], 128 * 1024)
        self.assertEqual(settings["skip_duration_days"], 14)


if __name__ == "__main__":
    unittest.main()
