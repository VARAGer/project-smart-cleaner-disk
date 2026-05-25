import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from client.gui.main_window import MainWindow  # noqa: E402


class MainWindowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_main_window_minimum_size_fits_common_laptop_displays(self):
        window = MainWindow()
        self.addCleanup(window.close)

        minimum = window.minimumSize()

        self.assertLessEqual(minimum.width(), 1024)
        self.assertLessEqual(minimum.height(), 700)

    def test_detail_resolution_returns_to_disk_when_no_bundles_remain(self):
        window = MainWindow()
        self.addCleanup(window.close)
        window.last_scan_targets = ["C:/demo"]
        window.stack.setCurrentWidget(window.bundle_detail_screen)

        with patch(
            "client.gui.main_window.build_bundles_from_database",
            return_value=[],
        ):
            window.handle_detail_bundle_resolved()

        self.assertIs(window.stack.currentWidget(), window.disk_screen)

    def test_disk_screen_auto_shows_expired_review_bundles(self):
        window = MainWindow()
        self.addCleanup(window.close)
        window.last_scan_targets = ["C:/demo"]
        window.last_bundle_signature = tuple()
        window.stack.setCurrentWidget(window.disk_screen)
        bundle = {
            "bundle_id": "review-protected",
            "name": "Нужна проверка",
            "description": "Expired skip",
            "review": True,
            "files": [
                {
                    "file_id": "expired",
                    "filename": "old.zip",
                    "size_bytes": 2048,
                    "category": "archive",
                    "confidence": 0.91,
                }
            ],
            "total_size_bytes": 2048,
        }

        with patch(
            "client.gui.main_window.build_bundles_from_database",
            return_value=[bundle],
        ):
            window.show_expired_review_bundles_if_any()

        self.assertIs(window.stack.currentWidget(), window.bundle_list_screen)
        self.assertEqual(
            window.bundle_list_screen.bundles[0]["bundle_id"],
            "review-protected",
        )


if __name__ == "__main__":
    unittest.main()
