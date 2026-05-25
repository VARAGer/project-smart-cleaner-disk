from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections.abc import Callable, Iterable

from client.api_client import ApiClientError, analyze_and_cache_files
from client.config import DB_PATH, DEFAULT_MIN_AGE_MONTHS, DEFAULT_MIN_SIZE_BYTES
from client.database.local_db import (
    AI_UNAVAILABLE_REASON,
    MARKER_AI_PROTECTED,
    MARKER_PROTECTED,
    MARKER_SKIP,
    cache_analysis_results,
    connect,
    get_analysis_candidate_excluded_file_ids,
    get_deletion_excluded_file_ids,
    init_database,
)
from client.scanner.incremental import IncrementalScanner


@dataclass(frozen=True)
class PipelineResult:
    scanned_disks: int
    scan_stats: dict[str, int]
    candidates_analyzed: int
    bundles: list[dict]


ProgressCallback = Callable[[str], None]


def run_scan_analysis_pipeline(
    api_client,
    selected_disks: Iterable[str],
    *,
    db_path: str = DB_PATH,
    scanner_factory=IncrementalScanner,
    progress_callback: ProgressCallback | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    min_age_months: int = DEFAULT_MIN_AGE_MONTHS,
    min_size_bytes: int = DEFAULT_MIN_SIZE_BYTES,
    now: str | datetime | None = None,
) -> PipelineResult:
    init_database(db_path)
    disks = list(selected_disks)
    merged_stats = {"new": 0, "update": 0, "deleted": 0, "unchanged": 0, "total": 0}

    for disk_path in disks:
        if cancel_requested and cancel_requested():
            break
        _notify(progress_callback, f"Сканирование {disk_path}")
        scanner = scanner_factory(db_path)
        stats = scanner.scan(
            disk_path,
            disk_path,
            progress_callback=lambda count: _notify(
                progress_callback,
                f"Найдено файлов: {count}",
            ),
            cancel_requested=cancel_requested,
        )
        for key in merged_stats:
            merged_stats[key] += int(stats.get(key, 0))

    _notify(progress_callback, "Отбор кандидатов для анализа")
    if cancel_requested and cancel_requested():
        return PipelineResult(
            scanned_disks=len(disks),
            scan_stats=merged_stats,
            candidates_analyzed=0,
            bundles=[],
        )
    candidates = load_analysis_candidates(
        db_path=db_path,
        disk_labels=disks,
        min_size_bytes=min_size_bytes,
        min_age_months=min_age_months,
        now=now,
    )

    if candidates and not (cancel_requested and cancel_requested()):
        _notify(progress_callback, f"Отправка на анализ: {len(candidates)} файлов")
        scan_id = f"scan-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            analyze_and_cache_files(api_client, scan_id, candidates, db_path=db_path)
        except ApiClientError:
            _notify(
                progress_callback,
                "Сервис анализа недоступен, файлы отправлены на ручную проверку",
            )
            cache_analysis_results(
                _build_unavailable_ai_classifications(candidates),
                db_path=db_path,
            )

    _notify(progress_callback, "Сборка бандлов")
    bundles = build_bundles_from_database(db_path=db_path, disk_labels=disks)
    return PipelineResult(
        scanned_disks=len(disks),
        scan_stats=merged_stats,
        candidates_analyzed=len(candidates),
        bundles=bundles,
    )


def load_analysis_candidates(
    *,
    db_path: str = DB_PATH,
    disk_labels: Iterable[str] | None = None,
    min_size_bytes: int = DEFAULT_MIN_SIZE_BYTES,
    min_age_months: int = DEFAULT_MIN_AGE_MONTHS,
    now: str | datetime | None = None,
) -> list[dict]:
    init_database(db_path)
    excluded_ids = get_analysis_candidate_excluded_file_ids(db_path)
    cutoff = _age_cutoff(now, min_age_months)
    disk_filter = set(disk_labels or [])

    rows = _fetch_scanned_files(db_path)
    candidates = []
    for row in rows:
        item = dict(row)
        if disk_filter and item["disk_label"] not in disk_filter:
            continue
        if item["file_id"] in excluded_ids:
            continue
        if int(item["size_bytes"] or 0) < min_size_bytes:
            continue
        modified_at = _parse_datetime(item.get("modified_at"))
        if modified_at is None or modified_at > cutoff:
            continue
        candidates.append(
            {
                "file_id": item["file_id"],
                "path": item["path"],
                "filename": item["filename"],
                "extension": item.get("extension") or "",
                "size_bytes": int(item["size_bytes"] or 0),
                "modified_at": item.get("modified_at") or "",
                "accessed_at": item.get("accessed_at") or "",
                "parent_dir": item.get("parent_dir") or "",
            }
        )
    return candidates


def build_bundles_from_database(
    *,
    db_path: str = DB_PATH,
    disk_labels: Iterable[str] | None = None,
) -> list[dict]:
    init_database(db_path)
    excluded_ids = get_deletion_excluded_file_ids(db_path)
    disk_filter = set(disk_labels or [])
    rows = _fetch_analyzed_files(db_path)
    now_dt = datetime.now()

    review_files: list[dict] = []
    grouped: dict[str, list[dict]] = {}

    for row in rows:
        item = dict(row)
        if disk_filter and item["disk_label"] not in disk_filter:
            continue
        file_info = _bundle_file(item)
        marker_type = item.get("marker_type") or ""
        if marker_type == MARKER_SKIP:
            if _is_expired_skip(item.get("expires_at"), now_dt):
                review_files.append(file_info)
            continue
        if marker_type == MARKER_PROTECTED:
            continue
        if marker_type == MARKER_AI_PROTECTED:
            review_files.append(file_info)
            continue
        if item["file_id"] in excluded_ids:
            continue
        grouped.setdefault(file_info["category"], []).append(file_info)

    bundles: list[dict] = []
    if review_files:
        bundles.append(_make_bundle(
            "review-protected",
            "Нужна проверка",
            "Файлы, которые нужно вручную пересмотреть перед удалением.",
            True,
            review_files,
        ))

    for category in sorted(grouped):
        files = grouped[category]
        bundles.append(_make_bundle(
            f"category-{_slug(category)}",
            _category_title(category),
            "Кандидаты на удаление после анализа Gemini.",
            False,
            files,
        ))

    return bundles


def _fetch_scanned_files(db_path: str) -> list[sqlite3.Row]:
    with closing(connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT file_id, path, filename, extension, size_bytes,
                   modified_at, accessed_at, parent_dir, disk_label
            FROM scanned_files
            ORDER BY modified_at ASC, filename ASC
            """
        ).fetchall()


def _fetch_analyzed_files(db_path: str) -> list[sqlite3.Row]:
    with closing(connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT sf.file_id, sf.path, sf.filename, sf.extension, sf.size_bytes,
                   sf.modified_at, sf.accessed_at, sf.parent_dir, sf.disk_label,
                   ac.confidence, ac.category, ac.reason,
                   fm.marker_type, fm.expires_at
            FROM scanned_files sf
            JOIN analysis_cache ac ON ac.file_id = sf.file_id
            LEFT JOIN file_markers fm ON fm.file_id = sf.file_id
            ORDER BY ac.confidence DESC, sf.size_bytes DESC, sf.filename ASC
            """
        ).fetchall()


def _bundle_file(row: dict) -> dict:
    return {
        "file_id": row["file_id"],
        "path": row["path"],
        "filename": row["filename"],
        "extension": row.get("extension") or "",
        "size_bytes": int(row.get("size_bytes") or 0),
        "modified_at": row.get("modified_at") or "",
        "accessed_at": row.get("accessed_at") or "",
        "parent_dir": row.get("parent_dir") or "",
        "disk_label": row.get("disk_label") or "",
        "category": str(row.get("category") or "other"),
        "confidence": float(row.get("confidence") or 0.5),
        "reason": str(row.get("reason") or ""),
        "marker_type": row.get("marker_type") or "",
        "expires_at": row.get("expires_at") or "",
    }


def _make_bundle(
    bundle_id: str,
    name: str,
    description: str,
    review: bool,
    files: list[dict],
) -> dict:
    return {
        "bundle_id": bundle_id,
        "name": name,
        "description": description,
        "review": review,
        "files": files,
        "total_size_bytes": sum(file_info["size_bytes"] for file_info in files),
    }


def _build_unavailable_ai_classifications(files: Iterable[dict]) -> list[dict]:
    return [
        {
            "file_id": file_info["file_id"],
            "confidence": 0.5,
            "category": "other",
            "reason": AI_UNAVAILABLE_REASON,
        }
        for file_info in files
    ]


def _age_cutoff(now: str | datetime | None, min_age_months: int) -> datetime:
    if isinstance(now, str):
        now_dt = datetime.fromisoformat(now)
    elif now is None:
        now_dt = datetime.now()
    else:
        now_dt = now
    return now_dt - timedelta(days=30 * min_age_months)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _is_expired_skip(expires_at: str | None, now_dt: datetime) -> bool:
    expires_dt = _parse_datetime(expires_at)
    return expires_dt is not None and expires_dt <= now_dt


def _category_title(category: str) -> str:
    return {
        "archive": "Архивы",
        "backup": "Бэкапы",
        "cache": "Кэш",
        "code": "Код",
        "config": "Конфигурации",
        "database": "Базы данных",
        "document": "Документы",
        "installer": "Установщики",
        "log": "Логи",
        "media": "Медиа",
        "temp": "Временные файлы",
        "other": "Прочее",
    }.get(category, category)


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")


def _notify(callback: ProgressCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)
