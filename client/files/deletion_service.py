from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum

from client.config import DB_PATH
from client.database.local_db import (
    connect,
    get_deletion_excluded_file_ids,
    init_database,
    record_deletion_history,
)


class DeletionStatus(StrEnum):
    DELETED = "deleted"
    PROTECTED = "protected"
    OUT_OF_SCOPE = "out_of_scope"
    MISSING = "missing"
    NOT_FOUND = "not_found"
    FAILED = "failed"


@dataclass(frozen=True)
class FileDeletionResult:
    file_id: str
    status: DeletionStatus
    reason: str
    filename: str = ""


@dataclass(frozen=True)
class DeletionResult:
    results: list[FileDeletionResult]

    @property
    def deleted_count(self) -> int:
        return sum(1 for item in self.results if item.status == DeletionStatus.DELETED)

    @property
    def skipped_count(self) -> int:
        return len(self.results) - self.deleted_count


DeleteBackend = Callable[[str], None]


def delete_files_by_id(
    file_ids: Iterable[str],
    *,
    db_path: str = DB_PATH,
    delete_backend: DeleteBackend | None = None,
    allowed_roots: Iterable[str] | None = None,
) -> DeletionResult:
    init_database(db_path)
    backend = delete_backend or _send_to_trash
    excluded_ids = get_deletion_excluded_file_ids(db_path)
    roots = _normalize_roots(allowed_roots)
    results: list[FileDeletionResult] = []

    for file_id in dict.fromkeys(str(fid) for fid in file_ids if str(fid)):
        record = _load_scanned_file(file_id, db_path)
        if record is None:
            results.append(
                FileDeletionResult(
                    file_id=file_id,
                    status=DeletionStatus.NOT_FOUND,
                    reason="File id is not present in local scan database",
                )
            )
            continue

        if file_id in excluded_ids:
            result = FileDeletionResult(
                file_id=file_id,
                status=DeletionStatus.PROTECTED,
                reason="File is protected by a local marker",
                filename=record["filename"],
            )
            _record(record, result, db_path)
            results.append(result)
            continue

        path = record["path"]
        if roots and not _is_path_under_roots(path, roots):
            result = FileDeletionResult(
                file_id=file_id,
                status=DeletionStatus.OUT_OF_SCOPE,
                reason="File is outside the current scan selection",
                filename=record["filename"],
            )
            _record(record, result, db_path)
            results.append(result)
            continue

        if not path or not os.path.isfile(path):
            result = FileDeletionResult(
                file_id=file_id,
                status=DeletionStatus.MISSING,
                reason="Local file does not exist",
                filename=record["filename"],
            )
            _record(record, result, db_path)
            results.append(result)
            continue

        try:
            backend(path)
        except Exception:
            result = FileDeletionResult(
                file_id=file_id,
                status=DeletionStatus.FAILED,
                reason="OS deletion request failed",
                filename=record["filename"],
            )
            _record(record, result, db_path)
            results.append(result)
            continue

        _remove_scanned_file(file_id, db_path)
        result = FileDeletionResult(
            file_id=file_id,
            status=DeletionStatus.DELETED,
            reason="Moved to system trash",
            filename=record["filename"],
        )
        _record(record, result, db_path)
        results.append(result)

    return DeletionResult(results=results)


def _send_to_trash(path: str) -> None:
    from send2trash import send2trash

    send2trash(path)


def _normalize_roots(roots: Iterable[str] | None) -> list[str]:
    if roots is None:
        return []
    normalized = []
    for root in roots:
        value = str(root or "").strip()
        if not value:
            continue
        normalized.append(os.path.normcase(os.path.abspath(value)))
    return normalized


def _is_path_under_roots(path: str, roots: list[str]) -> bool:
    if not path:
        return False
    normalized_path = os.path.normcase(os.path.abspath(path))
    for root in roots:
        try:
            if os.path.commonpath([normalized_path, root]) == root:
                return True
        except ValueError:
            continue
    return False


def _load_scanned_file(file_id: str, db_path: str) -> sqlite3.Row | None:
    with closing(connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT file_id, path, filename, size_bytes
            FROM scanned_files
            WHERE file_id = ?
            """,
            (file_id,),
        ).fetchone()


def _remove_scanned_file(file_id: str, db_path: str) -> None:
    with closing(connect(db_path)) as conn:
        conn.execute("DELETE FROM scanned_files WHERE file_id = ?", (file_id,))
        conn.commit()


def _record(record: sqlite3.Row, result: FileDeletionResult, db_path: str) -> None:
    record_deletion_history(
        result.file_id,
        status=result.status.value,
        reason=result.reason,
        filename=record["filename"],
        size_bytes=int(record["size_bytes"] or 0),
        db_path=db_path,
    )
