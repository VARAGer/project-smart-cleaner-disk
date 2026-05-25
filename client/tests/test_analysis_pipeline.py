import os
import tempfile
import unittest

from client.api_client import AnalysisResult, ApiClientError
from client.database.local_db import (
    cache_analysis_results,
    get_deletion_excluded_file_ids,
    mark_file,
    upsert_scanned_files,
)
from client.pipeline.analysis_pipeline import (
    build_bundles_from_database,
    load_analysis_candidates,
    run_scan_analysis_pipeline,
)


class AnalysisPipelineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "smartcleaner.db")

    def _file(
        self,
        file_id: str,
        *,
        filename: str = "old.tmp",
        size_bytes: int = 2048,
        modified_at: str = "2025-01-01T00:00:00",
        disk_label: str = "C:",
        extension: str = ".tmp",
    ) -> dict:
        return {
            "file_id": file_id,
            "path": f"C:/Users/Alice/Downloads/{filename}",
            "filename": filename,
            "extension": extension,
            "size_bytes": size_bytes,
            "created_at": "2024-12-01T00:00:00",
            "modified_at": modified_at,
            "accessed_at": "2025-01-02T00:00:00",
            "parent_dir": "C:/Users/Alice/Downloads",
            "disk_label": disk_label,
        }

    def test_load_analysis_candidates_filters_by_age_size_disk_and_markers(self):
        files = [
            self._file("old-large", filename="setup.exe", extension=".exe"),
            self._file("small", filename="tiny.tmp", size_bytes=100),
            self._file("new", filename="new.zip", modified_at="2026-05-01T00:00:00"),
            self._file("protected", filename="contract.pdf", extension=".pdf"),
            self._file("other-disk", filename="other.tmp", disk_label="D:"),
        ]
        upsert_scanned_files(files, db_path=self.db_path)
        mark_file("protected", "protected", db_path=self.db_path)

        candidates = load_analysis_candidates(
            db_path=self.db_path,
            disk_labels=["C:"],
            min_size_bytes=1024,
            min_age_months=6,
            now="2026-05-23T00:00:00",
        )

        self.assertEqual([item["file_id"] for item in candidates], ["old-large"])
        self.assertEqual(candidates[0]["path"], files[0]["path"])

    def test_load_analysis_candidates_retries_ai_protected_files(self):
        files = [
            self._file("ai-protected", filename="old-cache.tmp", extension=".tmp"),
            self._file("user-protected", filename="contract.pdf", extension=".pdf"),
        ]
        upsert_scanned_files(files, db_path=self.db_path)
        mark_file("ai-protected", "ai_protected", db_path=self.db_path)
        mark_file("user-protected", "protected", db_path=self.db_path)

        candidates = load_analysis_candidates(
            db_path=self.db_path,
            disk_labels=["C:"],
            min_size_bytes=1024,
            min_age_months=6,
            now="2026-05-23T00:00:00",
        )

        self.assertEqual([item["file_id"] for item in candidates], ["ai-protected"])

    def test_build_bundles_groups_analyzed_files_and_places_protected_in_review(self):
        files = [
            self._file("installer", filename="setup.exe", extension=".exe"),
            self._file("archive", filename="backup.zip", extension=".zip"),
            self._file("important", filename="contract.pdf", extension=".pdf"),
        ]
        upsert_scanned_files(files, db_path=self.db_path)
        cache_analysis_results(
            [
                {
                    "file_id": "installer",
                    "confidence": 0.92,
                    "category": "installer",
                    "reason": "Old installer",
                },
                {
                    "file_id": "archive",
                    "confidence": 0.81,
                    "category": "archive",
                    "reason": "Old archive",
                },
                {
                    "file_id": "important",
                    "confidence": 0.2,
                    "category": "document",
                    "reason": "Important document",
                },
            ],
            db_path=self.db_path,
        )

        bundles = build_bundles_from_database(db_path=self.db_path)

        self.assertEqual(bundles[0]["bundle_id"], "review-protected")
        self.assertTrue(bundles[0]["review"])
        self.assertEqual(
            [item["file_id"] for item in bundles[0]["files"]],
            ["important"],
        )
        normal_bundle_ids = {bundle["bundle_id"] for bundle in bundles[1:]}
        self.assertEqual(normal_bundle_ids, {"category-installer", "category-archive"})

    def test_build_bundles_can_filter_to_current_scan_target(self):
        files = [
            self._file(
                "demo-installer",
                filename="demo-setup.exe",
                extension=".exe",
                disk_label="D:/demo-folder",
            ),
            self._file(
                "stale-installer",
                filename="setup.exe",
                extension=".exe",
                disk_label="E:/",
            ),
        ]
        upsert_scanned_files(files, db_path=self.db_path)
        cache_analysis_results(
            [
                {
                    "file_id": "demo-installer",
                    "confidence": 0.92,
                    "category": "installer",
                    "reason": "Demo installer",
                },
                {
                    "file_id": "stale-installer",
                    "confidence": 0.92,
                    "category": "installer",
                    "reason": "Old result from another disk",
                },
            ],
            db_path=self.db_path,
        )

        bundles = build_bundles_from_database(
            db_path=self.db_path,
            disk_labels=["D:/demo-folder"],
        )

        files_in_result = [
            file_info["file_id"]
            for bundle in bundles
            for file_info in bundle["files"]
        ]
        self.assertEqual(files_in_result, ["demo-installer"])

    def test_build_bundles_places_expired_skip_in_review_and_hides_active_skip(self):
        files = [
            self._file("expired-skip", filename="old-report.pdf", extension=".pdf"),
            self._file("active-skip", filename="old-cache.tmp", extension=".tmp"),
            self._file("normal", filename="old-archive.zip", extension=".zip"),
        ]
        upsert_scanned_files(files, db_path=self.db_path)
        cache_analysis_results(
            [
                {
                    "file_id": file_info["file_id"],
                    "confidence": 0.91,
                    "category": "archive",
                    "reason": "Old candidate",
                }
                for file_info in files
            ],
            db_path=self.db_path,
        )
        mark_file(
            "expired-skip",
            "skip",
            expires_at="2000-01-01T00:00:00",
            db_path=self.db_path,
        )
        mark_file(
            "active-skip",
            "skip",
            expires_at="2099-01-01T00:00:00",
            db_path=self.db_path,
        )

        bundles = build_bundles_from_database(db_path=self.db_path)

        self.assertEqual(bundles[0]["bundle_id"], "review-protected")
        self.assertEqual(
            [file_info["file_id"] for file_info in bundles[0]["files"]],
            ["expired-skip"],
        )
        files_in_normal_bundles = [
            file_info["file_id"]
            for bundle in bundles[1:]
            for file_info in bundle["files"]
        ]
        self.assertEqual(files_in_normal_bundles, ["normal"])

    def test_build_bundles_hides_user_protected_files(self):
        files = [
            self._file("protected", filename="contract.pdf", extension=".pdf"),
            self._file("normal", filename="old-archive.zip", extension=".zip"),
        ]
        upsert_scanned_files(files, db_path=self.db_path)
        cache_analysis_results(
            [
                {
                    "file_id": file_info["file_id"],
                    "confidence": 0.91,
                    "category": "archive",
                    "reason": "Old candidate",
                }
                for file_info in files
            ],
            db_path=self.db_path,
        )
        mark_file("protected", "protected", db_path=self.db_path)

        bundles = build_bundles_from_database(db_path=self.db_path)

        files_in_result = [
            file_info["file_id"]
            for bundle in bundles
            for file_info in bundle["files"]
        ]
        self.assertEqual(files_in_result, ["normal"])

    def test_unavailable_ai_defaults_are_review_protected_not_deletable(self):
        upsert_scanned_files(
            [self._file("fallback", filename="maybe-important.pdf", extension=".pdf")],
            db_path=self.db_path,
        )
        cache_analysis_results(
            [
                {
                    "file_id": "fallback",
                    "confidence": 0.5,
                    "category": "other",
                    "reason": "Сервис анализа временно недоступен",
                }
            ],
            db_path=self.db_path,
        )

        bundles = build_bundles_from_database(db_path=self.db_path)

        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0]["bundle_id"], "review-protected")
        self.assertEqual(bundles[0]["files"][0]["file_id"], "fallback")

    def test_run_scan_analysis_pipeline_scans_analyzes_caches_and_returns_bundles(self):
        class FakeScanner:
            def __init__(self, db_path):
                self.db_path = db_path

            def scan(
                self,
                root_path,
                disk_label,
                progress_callback=None,
                cancel_requested=None,
            ):
                upsert_scanned_files(
                    [
                        {
                            "file_id": "scanned",
                            "path": f"{root_path}/old-installer.exe",
                            "filename": "old-installer.exe",
                            "extension": ".exe",
                            "size_bytes": 4096,
                            "created_at": "2024-12-01T00:00:00",
                            "modified_at": "2025-01-01T00:00:00",
                            "accessed_at": "2025-01-02T00:00:00",
                            "parent_dir": root_path,
                            "disk_label": disk_label,
                        }
                    ],
                    db_path=self.db_path,
                )
                if progress_callback:
                    progress_callback(1)
                return {"new": 1, "update": 0, "deleted": 0, "unchanged": 0, "total": 1}

        class FakeApiClient:
            def __init__(self):
                self.received_files = []

            def analyze_files(self, scan_id, files):
                self.received_files.extend(files)
                return AnalysisResult(
                    scan_id=scan_id,
                    classifications=[
                        {
                            "file_id": item["file_id"],
                            "confidence": 0.93,
                            "category": "installer",
                            "reason": "Old installer",
                        }
                        for item in files
                    ],
                )

        upsert_scanned_files(
            [
                self._file(
                    "stale",
                    filename="setup.exe",
                    extension=".exe",
                    disk_label="E:/",
                )
            ],
            db_path=self.db_path,
        )
        cache_analysis_results(
            [
                {
                    "file_id": "stale",
                    "confidence": 0.93,
                    "category": "installer",
                    "reason": "Previous scan",
                }
            ],
            db_path=self.db_path,
        )
        api_client = FakeApiClient()

        result = run_scan_analysis_pipeline(
            api_client,
            ["C:/scan-root"],
            db_path=self.db_path,
            scanner_factory=FakeScanner,
            min_age_months=6,
            min_size_bytes=1024,
            now="2026-05-23T00:00:00",
        )

        self.assertEqual(result.scanned_disks, 1)
        self.assertEqual(result.candidates_analyzed, 1)
        self.assertEqual(api_client.received_files[0]["file_id"], "scanned")
        self.assertEqual(result.bundles[0]["bundle_id"], "category-installer")
        self.assertEqual(result.bundles[0]["files"][0]["file_id"], "scanned")
        self.assertEqual(get_deletion_excluded_file_ids(self.db_path), set())

    def test_run_scan_analysis_pipeline_protects_unavailable_ai_defaults(self):
        class FakeScanner:
            def __init__(self, db_path):
                self.db_path = db_path

            def scan(
                self,
                root_path,
                disk_label,
                progress_callback=None,
                cancel_requested=None,
            ):
                upsert_scanned_files(
                    [
                        {
                            "file_id": "fallback",
                            "path": f"{root_path}/maybe-important.pdf",
                            "filename": "maybe-important.pdf",
                            "extension": ".pdf",
                            "size_bytes": 4096,
                            "created_at": "2024-12-01T00:00:00",
                            "modified_at": "2025-01-01T00:00:00",
                            "accessed_at": "2025-01-02T00:00:00",
                            "parent_dir": root_path,
                            "disk_label": disk_label,
                        }
                    ],
                    db_path=self.db_path,
                )
                return {"new": 1, "update": 0, "deleted": 0, "unchanged": 0, "total": 1}

        class UnavailableApiClient:
            def analyze_files(self, scan_id, files):
                return AnalysisResult(
                    scan_id=scan_id,
                    classifications=[
                        {
                            "file_id": item["file_id"],
                            "confidence": 0.5,
                            "category": "other",
                            "reason": "Сервис анализа временно недоступен",
                        }
                        for item in files
                    ],
                )

        result = run_scan_analysis_pipeline(
            UnavailableApiClient(),
            ["C:/scan-root"],
            db_path=self.db_path,
            scanner_factory=FakeScanner,
            min_age_months=6,
            min_size_bytes=1024,
            now="2026-05-23T00:00:00",
        )

        self.assertEqual(result.candidates_analyzed, 1)
        self.assertEqual(result.bundles[0]["bundle_id"], "review-protected")
        self.assertEqual(
            get_deletion_excluded_file_ids(self.db_path),
            {"fallback"},
        )

    def test_run_scan_analysis_pipeline_falls_back_when_backend_unavailable(self):
        class FakeScanner:
            def __init__(self, db_path):
                self.db_path = db_path

            def scan(
                self,
                root_path,
                disk_label,
                progress_callback=None,
                cancel_requested=None,
            ):
                upsert_scanned_files(
                    [
                        {
                            "file_id": "offline",
                            "path": f"{root_path}/old-download.tmp",
                            "filename": "old-download.tmp",
                            "extension": ".tmp",
                            "size_bytes": 4096,
                            "created_at": "2024-12-01T00:00:00",
                            "modified_at": "2025-01-01T00:00:00",
                            "accessed_at": "2025-01-02T00:00:00",
                            "parent_dir": root_path,
                            "disk_label": disk_label,
                        }
                    ],
                    db_path=self.db_path,
                )
                return {"new": 1, "update": 0, "deleted": 0, "unchanged": 0, "total": 1}

        class OfflineApiClient:
            def analyze_files(self, scan_id, files):
                raise ApiClientError("Backend is unavailable")

        progress_messages = []
        result = run_scan_analysis_pipeline(
            OfflineApiClient(),
            ["C:/scan-root"],
            db_path=self.db_path,
            scanner_factory=FakeScanner,
            progress_callback=progress_messages.append,
            min_age_months=6,
            min_size_bytes=1024,
            now="2026-05-23T00:00:00",
        )

        self.assertEqual(result.candidates_analyzed, 1)
        self.assertEqual(result.bundles[0]["bundle_id"], "review-protected")
        self.assertEqual(result.bundles[0]["files"][0]["file_id"], "offline")
        self.assertEqual(
            get_deletion_excluded_file_ids(self.db_path),
            {"offline"},
        )
        self.assertIn(
            "Сервис анализа недоступен, файлы отправлены на ручную проверку",
            progress_messages,
        )


if __name__ == "__main__":
    unittest.main()
