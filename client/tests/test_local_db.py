import hashlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

from client.scanner.file_ids import generate_file_id
from client.scanner.incremental import IncrementalScanner


class LocalDbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "smartcleaner.db")

    def _fetchall(self, query, params=()):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(query, params).fetchall()

    def test_init_database_creates_required_tables_idempotently(self):
        from client.database.local_db import init_database

        init_database(self.db_path)
        init_database(self.db_path)

        tables = {
            row[0]
            for row in self._fetchall(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertIn("scanned_files", tables)
        self.assertIn("file_markers", tables)
        self.assertIn("analysis_cache", tables)
        self.assertIn("user_settings", tables)

    def test_incremental_scanner_initializes_and_persists_scanned_files(self):
        root = os.path.join(self.tmp.name, "scan-root")
        os.mkdir(root)
        file_path = os.path.join(root, "old-report.pdf")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("metadata only")

        stats = IncrementalScanner(db_path=self.db_path).scan(root, "test-disk")

        self.assertEqual(stats["new"], 1)
        rows = self._fetchall(
            "SELECT filename, extension, disk_label FROM scanned_files"
        )
        self.assertEqual(rows, [("old-report.pdf", ".pdf", "test-disk")])

    def test_incremental_scanner_keeps_installers_outside_system_dirs(self):
        root = os.path.join(self.tmp.name, "downloads")
        os.mkdir(root)
        file_path = os.path.join(root, "old-installer.exe")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("metadata only")

        stats = IncrementalScanner(db_path=self.db_path).scan(root, "test-disk")

        self.assertEqual(stats["new"], 1)
        rows = self._fetchall(
            "SELECT filename, extension FROM scanned_files WHERE file_id IS NOT NULL"
        )
        self.assertEqual(rows, [("old-installer.exe", ".exe")])

    def test_generated_file_ids_are_local_salted_not_plain_path_md5(self):
        path = os.path.join(self.tmp.name, "Downloads", "setup.exe")

        first = generate_file_id(path, data_dir=self.tmp.name)
        second = generate_file_id(path, data_dir=self.tmp.name)
        plain_md5_prefix = hashlib.md5(
            os.path.normcase(os.path.abspath(path)).encode("utf-8")
        ).hexdigest()[:20]

        self.assertEqual(first, second)
        self.assertEqual(len(first), 20)
        self.assertNotEqual(first, plain_md5_prefix)

    def test_incremental_scanner_throttles_progress_and_reports_final_count(self):
        root = os.path.join(self.tmp.name, "scan-root")
        os.mkdir(root)
        for index in range(3):
            with open(os.path.join(root, f"file-{index}.tmp"), "w", encoding="utf-8") as f:
                f.write("metadata only")

        updates = []
        scanner = IncrementalScanner(db_path=self.db_path)
        scanner.BATCH_SIZE = 2

        scanner.scan(root, "test-disk", progress_callback=updates.append)

        self.assertEqual(updates, [2, 3])

    def test_cancelled_incremental_scan_does_not_delete_unseen_existing_rows(self):
        root = os.path.join(self.tmp.name, "scan-root")
        os.mkdir(root)
        for filename in ("a.tmp", "b.tmp"):
            with open(os.path.join(root, filename), "w", encoding="utf-8") as f:
                f.write("metadata only")

        scanner = IncrementalScanner(db_path=self.db_path)
        scanner.scan(root, "test-disk")

        cancelled = False

        def progress_callback(_count):
            nonlocal cancelled
            cancelled = True

        scanner.BATCH_SIZE = 1
        stats = scanner.scan(
            root,
            "test-disk",
            progress_callback=progress_callback,
            cancel_requested=lambda: cancelled,
        )

        self.assertEqual(stats["deleted"], 0)
        rows = self._fetchall(
            "SELECT filename FROM scanned_files ORDER BY filename"
        )
        self.assertEqual(rows, [("a.tmp",), ("b.tmp",)])

    def test_markers_include_separate_ai_protected_type(self):
        from client.database.local_db import (
            init_database,
            mark_file,
            upsert_scanned_files,
        )

        init_database(self.db_path)
        upsert_scanned_files(
            [
                {
                    "file_id": "f1",
                    "path": "C:/Users/me/Documents/thesis.docx",
                    "filename": "thesis.docx",
                    "extension": ".docx",
                    "size_bytes": 123,
                    "created_at": "2026-01-01T00:00:00",
                    "modified_at": "2026-01-02T00:00:00",
                    "accessed_at": "2026-01-03T00:00:00",
                    "parent_dir": "Documents",
                    "disk_label": "C:",
                }
            ],
            db_path=self.db_path,
        )

        mark_file("f1", "ai_protected", db_path=self.db_path)

        rows = self._fetchall(
            "SELECT marker_type FROM file_markers WHERE file_id = ?",
            ("f1",),
        )
        self.assertEqual(rows, [("ai_protected",)])

    def test_deletion_exclusions_include_protected_ai_protected_and_active_skip(self):
        from client.database.local_db import (
            get_deletion_excluded_file_ids,
            init_database,
            mark_file,
            upsert_scanned_files,
        )

        init_database(self.db_path)
        upsert_scanned_files(
            [
                {
                    "file_id": fid,
                    "path": f"C:/tmp/{fid}.tmp",
                    "filename": f"{fid}.tmp",
                    "extension": ".tmp",
                    "size_bytes": 10,
                    "created_at": "2026-01-01T00:00:00",
                    "modified_at": "2026-01-02T00:00:00",
                    "accessed_at": "2026-01-03T00:00:00",
                    "parent_dir": "tmp",
                    "disk_label": "C:",
                }
                for fid in ("skip1", "protected1", "ai1", "normal1")
            ],
            db_path=self.db_path,
        )
        mark_file(
            "skip1",
            "skip",
            expires_at="2099-01-01T00:00:00",
            db_path=self.db_path,
        )
        mark_file("protected1", "protected", db_path=self.db_path)
        mark_file("ai1", "ai_protected", db_path=self.db_path)

        self.assertEqual(
            get_deletion_excluded_file_ids(db_path=self.db_path),
            {"skip1", "protected1", "ai1"},
        )

    def test_low_confidence_analysis_creates_ai_protected_marker(self):
        from client.database.local_db import (
            cache_analysis_results,
            get_deletion_excluded_file_ids,
            init_database,
            upsert_scanned_files,
        )

        init_database(self.db_path)
        upsert_scanned_files(
            [
                {
                    "file_id": "important",
                    "path": "C:/Users/me/Documents/contract.pdf",
                    "filename": "contract.pdf",
                    "extension": ".pdf",
                    "size_bytes": 1000,
                    "created_at": "2026-01-01T00:00:00",
                    "modified_at": "2026-01-02T00:00:00",
                    "accessed_at": "2026-01-03T00:00:00",
                    "parent_dir": "Documents",
                    "disk_label": "C:",
                }
            ],
            db_path=self.db_path,
        )

        cache_analysis_results(
            [
                {
                    "file_id": "important",
                    "confidence": 0.24,
                    "category": "document",
                    "reason": "Important user document",
                }
            ],
            db_path=self.db_path,
        )

        self.assertEqual(
            get_deletion_excluded_file_ids(db_path=self.db_path),
            {"important"},
        )

    def test_confident_analysis_clears_previous_ai_protected_marker(self):
        from client.database.local_db import (
            cache_analysis_results,
            get_deletion_excluded_file_ids,
            init_database,
            mark_file,
            upsert_scanned_files,
        )

        init_database(self.db_path)
        upsert_scanned_files(
            [
                {
                    "file_id": "installer",
                    "path": "C:/Users/me/Downloads/setup.exe",
                    "filename": "setup.exe",
                    "extension": ".exe",
                    "size_bytes": 1000,
                    "created_at": "2026-01-01T00:00:00",
                    "modified_at": "2026-01-02T00:00:00",
                    "accessed_at": "2026-01-03T00:00:00",
                    "parent_dir": "Downloads",
                    "disk_label": "C:",
                }
            ],
            db_path=self.db_path,
        )
        mark_file("installer", "ai_protected", db_path=self.db_path)

        cache_analysis_results(
            [
                {
                    "file_id": "installer",
                    "confidence": 0.94,
                    "category": "installer",
                    "reason": "Old installer",
                }
            ],
            db_path=self.db_path,
        )

        self.assertEqual(get_deletion_excluded_file_ids(db_path=self.db_path), set())

    def test_mark_files_sets_many_markers_in_one_call(self):
        from client.database.local_db import (
            MARKER_SKIP,
            init_database,
            mark_files,
            upsert_scanned_files,
        )

        init_database(self.db_path)
        upsert_scanned_files(
            [
                {
                    "file_id": fid,
                    "path": f"C:/tmp/{fid}.tmp",
                    "filename": f"{fid}.tmp",
                    "extension": ".tmp",
                    "size_bytes": 10,
                    "created_at": "2026-01-01T00:00:00",
                    "modified_at": "2026-01-02T00:00:00",
                    "accessed_at": "2026-01-03T00:00:00",
                    "parent_dir": "tmp",
                    "disk_label": "C:",
                }
                for fid in ("a", "b", "c")
            ],
            db_path=self.db_path,
        )

        mark_files(
            ["a", "b", "c"],
            MARKER_SKIP,
            expires_at="2099-01-01T00:00:00",
            db_path=self.db_path,
        )

        rows = self._fetchall(
            """
            SELECT file_id, marker_type, expires_at
            FROM file_markers
            ORDER BY file_id
            """
        )
        self.assertEqual(
            rows,
            [
                ("a", "skip", "2099-01-01T00:00:00"),
                ("b", "skip", "2099-01-01T00:00:00"),
                ("c", "skip", "2099-01-01T00:00:00"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
