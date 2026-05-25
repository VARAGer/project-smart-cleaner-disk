import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from client.database.local_db import MARKER_PROTECTED, MARKER_SKIP  # noqa: E402
from client.files.deletion_service import (  # noqa: E402
    DeletionResult,
    DeletionStatus,
    FileDeletionResult,
)
from client.gui.bundle_detail_widget import BundleDetailScreen  # noqa: E402
from client.gui.bundle_list_widget import BundleListScreen  # noqa: E402


class BundleWidgetsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _bundle(self):
        return {
            "bundle_id": "category-installer",
            "name": "Установщики",
            "description": "Кандидаты",
            "review": False,
            "total_size_bytes": 4096,
            "files": [
                {
                    "file_id": "f1",
                    "path": "C:/tmp/setup.exe",
                    "filename": "setup.exe",
                    "size_bytes": 4096,
                    "category": "installer",
                    "confidence": 0.93,
                    "reason": "Old installer",
                }
            ],
        }

    def _two_file_bundle(self):
        bundle = self._bundle()
        bundle["files"] = [
            {
                "file_id": "setup",
                "path": "E:/Downloads/setup.exe",
                "filename": "setup.exe",
                "size_bytes": 4096,
                "category": "installer",
                "confidence": 0.93,
                "reason": "Old installer",
            },
            {
                "file_id": "project",
                "path": "D:/demo/pyprojecttoml.py",
                "filename": "pyprojecttoml.py",
                "size_bytes": 2048,
                "category": "other",
                "confidence": 0.8,
                "reason": "Demo file",
            },
        ]
        bundle["total_size_bytes"] = 6144
        return bundle

    def test_bundle_list_accepts_pipeline_bundles(self):
        screen = BundleListScreen()

        screen.set_bundles([self._bundle()])

        self.assertEqual(len(screen.cards), 1)
        self.assertEqual(screen.selected_bundle["bundle_id"], "category-installer")
        self.assertTrue(screen.open_button.isEnabled())
        self.assertTrue(screen.delete_button.isEnabled())

    def test_bundle_detail_marks_regular_files_as_temporary_skip(self):
        screen = BundleDetailScreen()
        screen.set_bundle(self._bundle())
        resolved = []
        screen.bundle_resolved.connect(lambda: resolved.append(True))

        with (
            patch("client.gui.bundle_detail_widget.mark_files") as mark_files,
            patch(
                "client.gui.bundle_detail_widget.get_skip_expiration",
                return_value=("2026-05-25T12:01:00", "через 1 минуту"),
            ),
            patch("client.gui.bundle_detail_widget.QMessageBox.information"),
        ):
            screen.mark_selected_as_skipped()

        mark_files.assert_called_once()
        args, kwargs = mark_files.call_args
        self.assertEqual(args[0], {"f1"})
        self.assertEqual(args[1], MARKER_SKIP)
        self.assertEqual(kwargs["expires_at"], "2026-05-25T12:01:00")
        self.assertEqual(screen.current_bundle["files"], [])
        self.assertEqual(resolved, [True])

    def test_bundle_detail_marks_review_files_as_protected(self):
        bundle = self._bundle()
        bundle["review"] = True
        screen = BundleDetailScreen()
        screen.set_bundle(bundle)

        with (
            patch("client.gui.bundle_detail_widget.mark_files") as mark_files,
            patch("client.gui.bundle_detail_widget.QMessageBox.information"),
        ):
            screen.mark_selected_as_skipped()

        mark_files.assert_called_once()
        args, _kwargs = mark_files.call_args
        self.assertEqual(args[0], {"f1"})
        self.assertEqual(args[1], MARKER_PROTECTED)
        self.assertEqual(screen.current_bundle["files"], [])

    def test_bundle_detail_open_uses_selected_row_not_first_checked_file(self):
        screen = BundleDetailScreen()
        screen.set_bundle(self._two_file_bundle())
        screen.table.selectRow(1)

        with (
            patch("client.gui.bundle_detail_widget.os.path.exists", return_value=True),
            patch("client.gui.bundle_detail_widget.os.startfile") as startfile,
        ):
            screen.open_selected_file()

        startfile.assert_called_once_with("D:/demo/pyprojecttoml.py")

    def test_bundle_detail_open_reports_os_error_without_crashing(self):
        screen = BundleDetailScreen()
        screen.set_bundle(self._bundle())

        with (
            patch("client.gui.bundle_detail_widget.os.path.exists", return_value=True),
            patch(
                "client.gui.bundle_detail_widget.os.startfile",
                side_effect=OSError("no file association"),
            ),
            patch("client.gui.bundle_detail_widget.QMessageBox.warning") as warning,
        ):
            screen.open_selected_file()

        warning.assert_called_once()
        self.assertIn("Не удалось открыть файл", warning.call_args.args[2])

    def test_bundle_detail_delete_uses_deletion_service_and_removes_deleted_rows(self):
        screen = BundleDetailScreen()
        screen.set_bundle(self._bundle())
        service_result = DeletionResult(
            results=[
                FileDeletionResult(
                    file_id="f1",
                    status=DeletionStatus.DELETED,
                    reason="Moved to system trash",
                    filename="setup.exe",
                )
            ]
        )

        with (
            patch("client.gui.bundle_detail_widget.delete_files_by_id") as delete_files,
            patch("client.gui.bundle_detail_widget.QMessageBox.question") as question,
            patch("client.gui.bundle_detail_widget.QMessageBox.information"),
        ):
            from PyQt6.QtWidgets import QMessageBox

            question.return_value = QMessageBox.StandardButton.Yes
            delete_files.return_value = service_result

            screen.confirm_delete()

        delete_files.assert_called_once_with(["f1"])
        self.assertEqual(screen.current_bundle["files"], [])

    def test_bundle_list_emits_back_request_for_new_scan(self):
        screen = BundleListScreen()
        emitted = []
        screen.back_requested.connect(lambda: emitted.append(True))

        screen.back_button.click()

        self.assertEqual(emitted, [True])

    def test_bundle_list_delete_all_removes_only_regular_recommendations(self):
        screen = BundleListScreen()
        regular_bundle = self._two_file_bundle()
        review_bundle = self._bundle()
        review_bundle["bundle_id"] = "review-protected"
        review_bundle["name"] = "Нужна проверка"
        review_bundle["review"] = True
        review_bundle["files"][0]["file_id"] = "review"
        screen.set_bundles([review_bundle, regular_bundle])
        service_result = DeletionResult(
            results=[
                FileDeletionResult(
                    file_id="setup",
                    status=DeletionStatus.DELETED,
                    reason="Moved to system trash",
                    filename="setup.exe",
                ),
                FileDeletionResult(
                    file_id="project",
                    status=DeletionStatus.DELETED,
                    reason="Moved to system trash",
                    filename="pyprojecttoml.py",
                ),
            ]
        )

        with (
            patch("client.gui.bundle_list_widget.delete_files_by_id") as delete_files,
            patch("client.gui.bundle_list_widget.QMessageBox.question") as question,
            patch("client.gui.bundle_list_widget.QMessageBox.information"),
        ):
            from PyQt6.QtWidgets import QMessageBox

            question.return_value = QMessageBox.StandardButton.Yes
            delete_files.return_value = service_result

            screen.confirm_delete_all_recommendations()

        delete_files.assert_called_once_with(["setup", "project"])
        self.assertEqual(len(screen.bundles), 1)
        self.assertTrue(screen.bundles[0]["review"])
        self.assertEqual(screen.bundles[0]["files"][0]["file_id"], "review")

    def test_bundle_list_skip_button_marks_regular_bundle_as_temporary_skip(self):
        screen = BundleListScreen()
        bundle = self._two_file_bundle()
        screen.set_bundles([bundle])
        resolved = []
        screen.all_bundles_resolved.connect(lambda: resolved.append(True))

        with (
            patch("client.gui.bundle_list_widget.mark_files") as mark_files,
            patch(
                "client.gui.bundle_list_widget.get_skip_expiration",
                return_value=("2026-05-25T12:01:00", "через 1 минуту"),
            ),
            patch("client.gui.bundle_list_widget.QMessageBox.question") as question,
            patch("client.gui.bundle_list_widget.QMessageBox.information"),
        ):
            from PyQt6.QtWidgets import QMessageBox

            question.return_value = QMessageBox.StandardButton.Yes

            screen.cards[0].skip_button.click()

        mark_files.assert_called_once()
        args, kwargs = mark_files.call_args
        self.assertEqual(args[0], {"setup", "project"})
        self.assertEqual(args[1], MARKER_SKIP)
        self.assertEqual(kwargs["expires_at"], "2026-05-25T12:01:00")
        self.assertEqual(screen.bundles, [])
        self.assertEqual(resolved, [True])

    def test_bundle_list_skip_button_marks_review_bundle_as_protected(self):
        screen = BundleListScreen()
        bundle = self._bundle()
        bundle["review"] = True
        screen.set_bundles([bundle])
        resolved = []
        screen.all_bundles_resolved.connect(lambda: resolved.append(True))

        with (
            patch("client.gui.bundle_list_widget.mark_files") as mark_files,
            patch("client.gui.bundle_list_widget.QMessageBox.question") as question,
            patch("client.gui.bundle_list_widget.QMessageBox.information"),
        ):
            from PyQt6.QtWidgets import QMessageBox

            question.return_value = QMessageBox.StandardButton.Yes

            screen.cards[0].skip_button.click()

        mark_files.assert_called_once()
        args, _kwargs = mark_files.call_args
        self.assertEqual(args[0], {"f1"})
        self.assertEqual(args[1], MARKER_PROTECTED)
        self.assertEqual(screen.bundles, [])
        self.assertEqual(resolved, [True])


if __name__ == "__main__":
    unittest.main()
