"""SQLite storage for local scan metadata, markers, settings, and AI cache."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import datetime

from client.config import (
    DB_PATH,
    DEFAULT_MIN_AGE_MONTHS,
    DEFAULT_MIN_SIZE_BYTES,
    DEFAULT_SKIP_DURATION_DAYS,
)

MARKER_SKIP = "skip"
MARKER_PROTECTED = "protected"
MARKER_AI_PROTECTED = "ai_protected"

VALID_MARKER_TYPES = {
    MARKER_SKIP,
    MARKER_PROTECTED,
    MARKER_AI_PROTECTED,
}

AI_PROTECTION_CONFIDENCE_THRESHOLD = 0.5
AI_UNAVAILABLE_REASON = "Сервис анализа временно недоступен"


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with project-required safety pragmas."""
    data_dir = os.path.dirname(db_path)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_database(db_path: str = DB_PATH) -> None:
    """Create the local database schema. Safe to call repeatedly."""
    with closing(connect(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scanned_files (
                file_id       TEXT PRIMARY KEY,
                path          TEXT UNIQUE NOT NULL,
                filename      TEXT NOT NULL,
                extension     TEXT,
                size_bytes    INTEGER NOT NULL,
                created_at    TEXT,
                modified_at   TEXT,
                accessed_at   TEXT,
                parent_dir    TEXT,
                disk_label    TEXT,
                scan_date     TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_scanned_files_modified
                ON scanned_files(modified_at);
            CREATE INDEX IF NOT EXISTS idx_scanned_files_size
                ON scanned_files(size_bytes DESC);
            CREATE INDEX IF NOT EXISTS idx_scanned_files_disk
                ON scanned_files(disk_label);
            CREATE INDEX IF NOT EXISTS idx_scanned_files_extension
                ON scanned_files(extension);

            CREATE TABLE IF NOT EXISTS file_markers (
                file_id       TEXT PRIMARY KEY
                              REFERENCES scanned_files(file_id) ON DELETE CASCADE,
                marker_type   TEXT NOT NULL
                              CHECK(marker_type IN ('skip', 'protected', 'ai_protected')),
                created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at    TEXT,
                skip_count    INTEGER DEFAULT 1,
                reason        TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_file_markers_type
                ON file_markers(marker_type);
            CREATE INDEX IF NOT EXISTS idx_file_markers_expires
                ON file_markers(expires_at);

            CREATE TABLE IF NOT EXISTS analysis_cache (
                file_id       TEXT PRIMARY KEY
                              REFERENCES scanned_files(file_id) ON DELETE CASCADE,
                confidence    REAL,
                category      TEXT,
                reason        TEXT,
                analyzed_at   TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                key           TEXT PRIMARY KEY,
                value         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS deletion_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id       TEXT NOT NULL,
                filename      TEXT,
                size_bytes    INTEGER,
                status        TEXT NOT NULL,
                reason        TEXT,
                deleted_at    TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_deletion_history_file_id
                ON deletion_history(file_id);
            """
        )
        conn.executemany(
            "INSERT OR IGNORE INTO user_settings (key, value) VALUES (?, ?)",
            [
                ("min_age_months", str(DEFAULT_MIN_AGE_MONTHS)),
                ("min_size_bytes", str(DEFAULT_MIN_SIZE_BYTES)),
                ("skip_duration_days", str(DEFAULT_SKIP_DURATION_DAYS)),
                ("last_scan_date", ""),
                ("selected_disks", "[]"),
            ],
        )
        conn.commit()


def upsert_scanned_files(
    files: Iterable[dict],
    db_path: str = DB_PATH,
) -> None:
    """Insert or update scanned file metadata in one transaction."""
    init_database(db_path)
    with closing(connect(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO scanned_files (
                file_id, path, filename, extension, size_bytes,
                created_at, modified_at, accessed_at, parent_dir, disk_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                path=excluded.path,
                filename=excluded.filename,
                extension=excluded.extension,
                size_bytes=excluded.size_bytes,
                created_at=excluded.created_at,
                modified_at=excluded.modified_at,
                accessed_at=excluded.accessed_at,
                parent_dir=excluded.parent_dir,
                disk_label=excluded.disk_label,
                scan_date=CURRENT_TIMESTAMP
            """,
            [
                (
                    f["file_id"],
                    f["path"],
                    f["filename"],
                    f.get("extension", ""),
                    int(f["size_bytes"]),
                    f.get("created_at"),
                    f.get("modified_at"),
                    f.get("accessed_at"),
                    f.get("parent_dir", ""),
                    f.get("disk_label", ""),
                )
                for f in files
            ],
        )
        conn.commit()


def mark_file(
    file_id: str,
    marker_type: str,
    *,
    expires_at: str | None = None,
    reason: str | None = None,
    db_path: str = DB_PATH,
) -> None:
    """Set the deletion marker for a scanned file."""
    mark_files(
        [file_id],
        marker_type,
        expires_at=expires_at,
        reason=reason,
        db_path=db_path,
    )


def mark_files(
    file_ids: Iterable[str],
    marker_type: str,
    *,
    expires_at: str | None = None,
    reason: str | None = None,
    db_path: str = DB_PATH,
) -> None:
    """Set the same deletion marker for many scanned files in one transaction."""
    if marker_type not in VALID_MARKER_TYPES:
        raise ValueError(f"Unsupported marker_type: {marker_type}")

    ids = list(dict.fromkeys(str(file_id) for file_id in file_ids if str(file_id)))
    if not ids:
        return

    init_database(db_path)
    with closing(connect(db_path)) as conn:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"""
            SELECT file_id, marker_type, skip_count
            FROM file_markers
            WHERE file_id IN ({placeholders})
            """,
            ids,
        ).fetchall()
        existing_by_id = {
            row[0]: (row[1], int(row[2] or 1))
            for row in rows
        }
        now = datetime.now().isoformat()
        records = []
        for file_id in ids:
            existing = existing_by_id.get(file_id)
            skip_count = 1
            if existing and marker_type in {MARKER_SKIP, MARKER_PROTECTED}:
                skip_count = existing[1] + 1
            records.append(
                (
                    file_id,
                    marker_type,
                    now,
                    expires_at,
                    skip_count,
                    reason,
                )
            )

        conn.executemany(
            """
            INSERT INTO file_markers (
                file_id, marker_type, created_at, expires_at, skip_count, reason
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                marker_type=excluded.marker_type,
                created_at=excluded.created_at,
                expires_at=excluded.expires_at,
                skip_count=excluded.skip_count,
                reason=excluded.reason
            """,
            records,
        )
        conn.commit()

def cache_analysis_results(
    classifications: Iterable[dict],
    *,
    db_path: str = DB_PATH,
    protect_threshold: float = AI_PROTECTION_CONFIDENCE_THRESHOLD,
) -> None:
    """Cache Gemini classifications and protect low-confidence files."""
    init_database(db_path)
    with closing(connect(db_path)) as conn:
        for item in classifications:
            file_id = item["file_id"]
            confidence = float(item.get("confidence", 0.5))
            category = str(item.get("category", "other"))
            reason = str(item.get("reason", ""))
            conn.execute(
                """
                INSERT INTO analysis_cache (
                    file_id, confidence, category, reason, analyzed_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    confidence=excluded.confidence,
                    category=excluded.category,
                    reason=excluded.reason,
                    analyzed_at=excluded.analyzed_at
                """,
                (file_id, confidence, category, reason, datetime.now().isoformat()),
            )
            if confidence <= protect_threshold or reason == AI_UNAVAILABLE_REASON:
                conn.execute(
                    """
                    INSERT INTO file_markers (
                        file_id, marker_type, created_at, expires_at,
                        skip_count, reason
                    )
                    VALUES (?, ?, ?, NULL, 1, ?)
                    ON CONFLICT(file_id) DO UPDATE SET
                        marker_type=excluded.marker_type,
                        created_at=excluded.created_at,
                        expires_at=NULL,
                        skip_count=1,
                        reason=excluded.reason
                    """,
                    (
                        file_id,
                        MARKER_AI_PROTECTED,
                        datetime.now().isoformat(),
                        reason,
                    ),
                )
            else:
                conn.execute(
                    """
                    DELETE FROM file_markers
                    WHERE file_id = ?
                      AND marker_type = ?
                    """,
                    (file_id, MARKER_AI_PROTECTED),
                )
        conn.commit()


def get_deletion_excluded_file_ids(db_path: str = DB_PATH) -> set[str]:
    """Return files that must not be proposed for deletion."""
    init_database(db_path)
    now = datetime.now().isoformat()
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT file_id
            FROM file_markers
            WHERE marker_type IN ('protected', 'ai_protected')
               OR (
                    marker_type = 'skip'
                    AND (expires_at IS NULL OR expires_at > ?)
               )
            """,
            (now,),
        ).fetchall()
    return {row[0] for row in rows}


def get_analysis_candidate_excluded_file_ids(db_path: str = DB_PATH) -> set[str]:
    """Return user-controlled markers that should not be re-sent to AI."""
    init_database(db_path)
    now = datetime.now().isoformat()
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT file_id
            FROM file_markers
            WHERE marker_type = 'protected'
               OR (
                    marker_type = 'skip'
                    AND (expires_at IS NULL OR expires_at > ?)
               )
            """,
            (now,),
        ).fetchall()
    return {row[0] for row in rows}


def record_deletion_history(
    file_id: str,
    *,
    status: str,
    reason: str,
    filename: str = "",
    size_bytes: int = 0,
    db_path: str = DB_PATH,
) -> None:
    init_database(db_path)
    with closing(connect(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO deletion_history (
                file_id, filename, size_bytes, status, reason, deleted_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                filename,
                int(size_bytes or 0),
                status,
                reason,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
