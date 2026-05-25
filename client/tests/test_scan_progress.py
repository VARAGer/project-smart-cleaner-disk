import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from client.gui.scan_progress import (  # noqa: E402
    _ScanPipelineWorker,
    load_scan_filter_settings,
    RoundedIndeterminateProgressBar,
    ScanProgressScreen,
)


class ScanProgressScreenTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_failure_stops_progress_and_labels_elapsed_as_stopped(self):
        screen = ScanProgressScreen(api_client=object())
        screen.elapsed_seconds = 67
        screen.timer.start()
        screen.progress.start()

        screen._handle_pipeline_failure("Ошибка")

        self.assertFalse(screen.timer.isActive())
        self.assertFalse(screen.progress.is_running)
        self.assertEqual(screen.elapsed.text(), "Остановлено: 01:07")
        self.assertEqual(screen.status.text(), "Ошибка")

    def test_progress_widget_uses_custom_rounded_runner(self):
        progress = RoundedIndeterminateProgressBar()

        progress.start()
        self.assertTrue(progress.is_running)

        progress.stop()
        self.assertFalse(progress.is_running)

    def test_back_button_emits_back_requested_when_idle(self):
        screen = ScanProgressScreen(api_client=object())
        calls = []
        screen.back_requested.connect(lambda: calls.append("back"))

        screen.back_button.click()

        self.assertEqual(calls, ["back"])

    def test_start_scan_reports_busy_without_replacing_active_worker(self):
        class FakeWorker:
            pass

        class FakeApiClient:
            session = object()

        screen = ScanProgressScreen(api_client=FakeApiClient())
        worker = FakeWorker()
        screen._worker = worker

        started = screen.start_scan(["C:/demo"])

        self.assertFalse(started)
        self.assertIs(screen._worker, worker)
        self.assertEqual(screen.status.text(), "Предыдущее сканирование еще завершается.")

    def test_cancel_scan_stops_active_worker_and_emits_back_requested(self):
        class FakeWorker:
            def __init__(self):
                self.interrupted = False

            def isRunning(self):
                return True

            def requestInterruption(self):
                self.interrupted = True

        screen = ScanProgressScreen(api_client=object())
        worker = FakeWorker()
        screen._worker = worker
        calls = []
        screen.back_requested.connect(lambda: calls.append("back"))

        screen._handle_back_requested()

        self.assertTrue(worker.interrupted)
        self.assertEqual(calls, ["back"])

    def test_load_scan_filter_settings_uses_saved_values(self):
        with patch(
            "client.gui.scan_progress.load_user_settings",
            return_value={"min_age_months": "3", "min_size_bytes": "4096"},
        ):
            settings = load_scan_filter_settings()

        self.assertEqual(settings, (3, 4096))

    def test_scan_worker_passes_saved_filters_to_pipeline(self):
        api_client = object()
        worker = _ScanPipelineWorker(api_client, ["C:/demo"])
        result = SimpleNamespace(bundles=[], candidates_analyzed=0)

        with (
            patch(
                "client.gui.scan_progress.load_scan_filter_settings",
                return_value=(2, 8192),
            ),
            patch(
                "client.gui.scan_progress.run_scan_analysis_pipeline",
                return_value=result,
            ) as pipeline,
        ):
            worker.run()

        pipeline.assert_called_once()
        _args, kwargs = pipeline.call_args
        self.assertEqual(kwargs["min_age_months"], 2)
        self.assertEqual(kwargs["min_size_bytes"], 8192)


if __name__ == "__main__":
    unittest.main()
