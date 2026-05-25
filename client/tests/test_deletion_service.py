import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

from client.database.local_db import (
    MARKER_AI_PROTECTED,
    MARKER_PROTECTED,
    MARKER_SKIP,
    mark_file,
    upsert_scanned_files,
)
from client.files.deletion_service import (
    DeletionStatus,
    delete_files_by_id,
)


class DeletionServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "smartcleaner.db")
        self.root = os.path.join(self.tmp.name, "files")
        os.mkdir(self.root)
        self.deleted_paths: list[str] = []

    def _create_file(self, filename: str, *, file_id: str | None = None) -> dict:
        path = os.path.join(self.root, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write("delete candidate")
        stat = os.stat(path)
        item = {
            "file_id": file_id or filename.replace(".", "-"),
            "path": path,
            "filename": filename,
            "extension": os.path.splitext(filename)[1],
            "size_bytes": stat.st_size,
            "created_at": "2025-01-01T00:00:00",
            "modified_at": "2025-01-01T00:00:00",
            "accessed_at": "2025-01-01T00:00:00",
            "parent_dir": self.root,
            "disk_label": "test-disk",
        }
        upsert_scanned_files([item], db_path=self.db_path)
        return item

    def _delete_backend(self, path: str) -> None:
        self.deleted_paths.append(path)
        os.remove(path)

    def _history(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                """
                SELECT file_id, status, reason
                FROM deletion_history
                ORDER BY id
                """
            ).fetchall()

    def test_delete_files_by_id_deletes_allowed_file_and_removes_scan_rows(self):
        item = self._create_file("old-installer.exe", file_id="allowed")

        result = delete_files_by_id(
            ["allowed"],
            db_path=self.db_path,
            delete_backend=self._delete_backend,
        )

        self.assertEqual(result.deleted_count, 1)
        self.assertEqual(result.results[0].status, DeletionStatus.DELETED)
        self.assertEqual(self.deleted_paths, [item["path"]])
        self.assertFalse(os.path.exists(item["path"]))
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute("SELECT file_id FROM scanned_files").fetchall()
        self.assertEqual(rows, [])
        self.assertEqual(
            self._history(),
            [("allowed", "deleted", "Moved to system trash")],
        )

    def test_delete_files_by_id_skips_protected_markers(self):
        protected = self._create_file("protected.pdf", file_id="protected")
        ai = self._create_file("ai.pdf", file_id="ai")
        skipped = self._create_file("skipped.zip", file_id="skipped")
        mark_file("protected", MARKER_PROTECTED, db_path=self.db_path)
        mark_file("ai", MARKER_AI_PROTECTED, db_path=self.db_path)
        mark_file(
            "skipped",
            MARKER_SKIP,
            expires_at="2099-01-01T00:00:00",
            db_path=self.db_path,
        )

        result = delete_files_by_id(
            ["protected", "ai", "skipped"],
            db_path=self.db_path,
            delete_backend=self._delete_backend,
        )

        self.assertEqual(result.deleted_count, 0)
        self.assertEqual(self.deleted_paths, [])
        self.assertTrue(os.path.exists(protected["path"]))
        self.assertTrue(os.path.exists(ai["path"]))
        self.assertTrue(os.path.exists(skipped["path"]))
        self.assertEqual(
            [item.status for item in result.results],
            [
                DeletionStatus.PROTECTED,
                DeletionStatus.PROTECTED,
                DeletionStatus.PROTECTED,
            ],
        )

    def test_delete_files_by_id_reports_missing_file_without_db_delete(self):
        item = self._create_file("missing.tmp", file_id="missing")
        os.remove(item["path"])

        result = delete_files_by_id(
            ["missing"],
            db_path=self.db_path,
            delete_backend=self._delete_backend,
        )

        self.assertEqual(result.deleted_count, 0)
        self.assertEqual(result.results[0].status, DeletionStatus.MISSING)
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute("SELECT file_id FROM scanned_files").fetchall()
        self.assertEqual(rows, [("missing",)])

    def test_delete_files_by_id_does_not_use_ui_path(self):
        item = self._create_file("real.tmp", file_id="real")
        malicious_ui_file = {
            "file_id": "real",
            "path": os.path.join(self.root, "other-user-file.txt"),
        }

        result = delete_files_by_id(
            [malicious_ui_file["file_id"]],
            db_path=self.db_path,
            delete_backend=self._delete_backend,
        )

        self.assertEqual(result.deleted_count, 1)
        self.assertEqual(self.deleted_paths, [item["path"]])
        self.assertNotEqual(self.deleted_paths[0], malicious_ui_file["path"])

    def test_delete_files_by_id_skips_files_outside_allowed_roots(self):
        item = self._create_file("real.tmp", file_id="real")
        allowed_root = os.path.join(self.tmp.name, "demo")
        os.mkdir(allowed_root)

        result = delete_files_by_id(
            ["real"],
            db_path=self.db_path,
            delete_backend=self._delete_backend,
            allowed_roots=[allowed_root],
        )

        self.assertEqual(result.deleted_count, 0)
        self.assertEqual(result.results[0].status, DeletionStatus.OUT_OF_SCOPE)
        self.assertEqual(self.deleted_paths, [])
        self.assertTrue(os.path.exists(item["path"]))

    def test_delete_files_by_id_reports_unknown_file_id(self):
        result = delete_files_by_id(
            ["unknown"],
            db_path=self.db_path,
            delete_backend=self._delete_backend,
        )

        self.assertEqual(result.deleted_count, 0)
        self.assertEqual(result.results[0].status, DeletionStatus.NOT_FOUND)
        self.assertEqual(self.deleted_paths, [])


if __name__ == "__main__":
    unittest.main()
