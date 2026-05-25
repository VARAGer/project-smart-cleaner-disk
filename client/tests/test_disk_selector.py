import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from client.gui.disk_selector import DiskSelectScreen, build_disk_options


class DiskSelectorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_build_disk_options_uses_real_detector_fields(self):
        options = build_disk_options(
            [
                {
                    "device": "C:",
                    "mountpoint": "C:\\",
                    "fstype": "NTFS",
                    "total_bytes": 1024 * 1024 * 1024,
                    "used_bytes": 512 * 1024 * 1024,
                }
            ]
        )

        self.assertEqual(options[0]["name"], "C:\\")
        self.assertEqual(options[0]["label"], "C:")
        self.assertIn("NTFS", options[0]["meta"])
        self.assertIn("512.0 МБ", options[0]["meta"])

    def test_custom_folder_can_be_added_as_scan_target(self):
        with patch("client.gui.disk_selector.get_available_disks", return_value=[]):
            screen = DiskSelectScreen()

        screen.add_custom_scan_path("C:/demo-smartcleaner")

        self.assertEqual(
            screen.selected_disks,
            [os.path.normpath("C:/demo-smartcleaner")],
        )
        self.assertTrue(screen.scan_button.isEnabled())

    def test_disk_options_are_not_selected_by_default(self):
        with patch("client.gui.disk_selector.get_available_disks", return_value=[]):
            screen = DiskSelectScreen()

        self.assertEqual(screen.selected_disks, [])
        self.assertFalse(screen.scan_button.isEnabled())

    def test_duplicate_custom_folder_is_not_added_twice(self):
        with patch("client.gui.disk_selector.get_available_disks", return_value=[]):
            screen = DiskSelectScreen()

        screen.add_custom_scan_path("C:/demo-smartcleaner")
        screen.add_custom_scan_path("C:/demo-smartcleaner")

        self.assertEqual(
            screen.selected_disks.count(os.path.normpath("C:/demo-smartcleaner")),
            1,
        )
        self.assertEqual(len(screen.disk_checks), 4)

    def test_existing_custom_folder_becomes_exclusive_scan_target(self):
        with patch("client.gui.disk_selector.get_available_disks", return_value=[]):
            screen = DiskSelectScreen()

        screen.add_custom_scan_path("C:/demo-smartcleaner")
        screen.disk_checks[0].setChecked(True)
        screen.add_custom_scan_path("C:/demo-smartcleaner")

        self.assertEqual(
            screen.selected_disks,
            [os.path.normpath("C:/demo-smartcleaner")],
        )

    def test_filter_badges_show_saved_scan_settings(self):
        with (
            patch("client.gui.disk_selector.get_available_disks", return_value=[]),
            patch(
                "client.gui.disk_selector.load_scan_filter_settings",
                return_value=(3, 4096),
            ),
        ):
            screen = DiskSelectScreen()

        self.assertEqual(screen.age_badge.text(), "Старше 3 месяцев")
        self.assertEqual(screen.size_badge.text(), "Больше 4.0 КБ")


if __name__ == "__main__":
    unittest.main()
