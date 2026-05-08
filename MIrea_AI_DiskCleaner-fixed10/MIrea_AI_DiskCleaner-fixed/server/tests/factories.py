"""
Synthetic data factories for tests.

No external dep (avoiding Faker) — deterministic seeded generation so failures
reproduce. Use `random.Random(seed)` instances, never the module-level RNG.
"""

from __future__ import annotations

import hashlib
import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

_USERNAME_POOL = string.ascii_lowercase + string.digits + "_"


def username(rng: random.Random, length: int | None = None) -> str:
    length = length or rng.randint(3, 20)
    # Ensure first char is a letter — some validators reject leading digit/underscore.
    head = rng.choice(string.ascii_lowercase)
    tail = "".join(rng.choice(_USERNAME_POOL) for _ in range(length - 1))
    return head + tail


def password(rng: random.Random, length: int | None = None) -> str:
    # Schema requires min_length=10 and at least one letter + one digit.
    length = length or rng.randint(10, 24)
    if length < 10:
        length = 10
    alphabet = string.ascii_letters + string.digits + "_!@#$"
    body = [rng.choice(string.ascii_letters), rng.choice(string.digits)]
    body += [rng.choice(alphabet) for _ in range(length - 2)]
    rng.shuffle(body)
    return "".join(body)


def user_credentials(rng: random.Random) -> dict:
    return {"username": username(rng), "password": password(rng)}


def user_batch(seed: int, n: int) -> list[dict]:
    """Return `n` deterministic, unique credential pairs."""
    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[dict] = []
    while len(out) < n:
        c = user_credentials(rng)
        if c["username"] in seen:
            continue
        seen.add(c["username"])
        out.append(c)
    return out


# ============================================================
# Files
# ============================================================

# Categories mirror the AI service prompt for realistic distribution.
_FILE_PROFILES = [
    # (extension, category, size_range_bytes, filename_words)
    (".exe", "installer", (5_000_000, 500_000_000), ["setup", "install", "app"]),
    (".msi", "installer", (1_000_000, 200_000_000), ["setup", "install"]),
    (".docx", "document", (10_000, 5_000_000), ["report", "thesis", "contract"]),
    (".pdf", "document", (50_000, 30_000_000), ["paper", "invoice", "book"]),
    (".txt", "document", (100, 500_000), ["notes", "readme", "todo"]),
    (".xlsx", "document", (10_000, 10_000_000), ["budget", "sales", "data"]),
    (".jpg", "media", (100_000, 15_000_000), ["photo", "img", "wedding"]),
    (".mp4", "media", (5_000_000, 2_000_000_000), ["video", "clip"]),
    (".mp3", "media", (1_000_000, 50_000_000), ["song", "track"]),
    (".log", "log", (1_000, 100_000_000), ["app", "debug", "trace"]),
    (".tmp", "temp", (100, 10_000_000), ["cache", "~$doc", "tempfile"]),
    (".bak", "backup", (10_000, 1_000_000_000), ["backup", "dump"]),
    (".zip", "archive", (100_000, 500_000_000), ["archive", "setup"]),
    (".rar", "archive", (100_000, 500_000_000), ["archive", "backup"]),
    (".db", "database", (10_000, 100_000_000), ["app", "users", "data"]),
    (".sqlite", "database", (10_000, 100_000_000), ["app", "cache"]),
    (".py", "code", (100, 500_000), ["main", "utils", "test"]),
    (".js", "code", (100, 500_000), ["index", "app", "bundle"]),
    (".env", "config", (50, 5_000), [".env", "settings"]),
    ("", "other", (1, 1_000_000), ["file", "data"]),
]

_PARENT_DIRS = [
    "C:/Users/x/Downloads",
    "C:/Users/x/Documents",
    "C:/Users/x/Desktop",
    "C:/Users/x/Pictures",
    "C:/Users/x/Videos",
    "C:/Users/x/AppData/Local/Temp",
    "C:/Users/x/AppData/Roaming/Cache",
    "C:/ProgramData/Logs",
    "C:/Projects/app",
    "C:/Projects/app/.git",
]


@dataclass
class FileMetadataSynthetic:
    file_id: str
    filename: str
    extension: str
    size_bytes: int
    modified_at: str
    accessed_at: str | None
    parent_dir: str

    def to_payload(self) -> dict:
        d = {
            "file_id": self.file_id,
            "filename": self.filename,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
            "parent_dir": self.parent_dir,
        }
        if self.accessed_at is not None:
            d["accessed_at"] = self.accessed_at
        return d


def _file_id(path: str) -> str:
    # Spec: MD5 hash of path, truncated to fit `max_length=20`.
    return hashlib.md5(path.encode()).hexdigest()[:16]


def file_metadata(
    rng: random.Random,
    *,
    base_date: datetime | None = None,
) -> FileMetadataSynthetic:
    base = base_date or datetime(2024, 1, 1, tzinfo=timezone.utc)
    ext, _category, (size_lo, size_hi), words = rng.choice(_FILE_PROFILES)
    word = rng.choice(words)
    stem = f"{word}_{rng.randint(1, 9999)}"
    filename = stem + ext
    parent = rng.choice(_PARENT_DIRS)
    path = f"{parent}/{filename}"
    age_days = rng.randint(0, 365 * 3)
    modified = base - timedelta(days=age_days, seconds=rng.randint(0, 86399))
    # Accessed can lag a bit behind modified, sometimes missing.
    if rng.random() < 0.1:
        accessed: str | None = None
    else:
        accessed = (modified + timedelta(days=rng.randint(0, age_days))).isoformat()
    return FileMetadataSynthetic(
        file_id=_file_id(path),
        filename=filename,
        extension=ext,
        size_bytes=rng.randint(size_lo, size_hi),
        modified_at=modified.isoformat(),
        accessed_at=accessed,
        parent_dir=parent,
    )


def file_batch(seed: int, n: int) -> list[dict]:
    """Return `n` file payload dicts with unique file_ids."""
    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[dict] = []
    while len(out) < n:
        fm = file_metadata(rng)
        if fm.file_id in seen:
            # Tweak to force a different hash.
            fm.filename = f"{len(out)}_{fm.filename}"
            fm.file_id = _file_id(f"{fm.parent_dir}/{fm.filename}")
        if fm.file_id in seen:
            continue
        seen.add(fm.file_id)
        out.append(fm.to_payload())
    return out


# ============================================================
# Analysis request builders
# ============================================================

@dataclass
class AnalysisPayload:
    scan_id: str
    files: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"scan_id": self.scan_id, "files": self.files}


def analysis_payload(seed: int, file_count: int, scan_id: str = "scan-test") -> dict:
    return AnalysisPayload(scan_id=scan_id, files=file_batch(seed, file_count)).to_json()
