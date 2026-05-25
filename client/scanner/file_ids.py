from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from client.config import DATA_DIR


SALT_FILE_NAME = "file_id_salt"
_SALT_CACHE: dict[str, str] = {}


def generate_file_id(file_path: str, *, data_dir: str | None = None) -> str:
    """Generate a stable local opaque id without exposing a hash of the raw path."""
    salt = _load_or_create_salt(data_dir or DATA_DIR)
    normalized_path = os.path.normcase(os.path.abspath(file_path))
    digest = hmac.new(
        salt.encode("ascii"),
        normalized_path.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:20]


def _load_or_create_salt(data_dir: str) -> str:
    cached = _SALT_CACHE.get(data_dir)
    if cached:
        return cached

    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, SALT_FILE_NAME)
    try:
        with open(path, "r", encoding="ascii") as f:
            value = f.read().strip()
        if len(value) >= 32:
            _SALT_CACHE[data_dir] = value
            return value
    except OSError:
        pass

    value = secrets.token_hex(32)
    with open(path, "w", encoding="ascii") as f:
        f.write(value)
    _SALT_CACHE[data_dir] = value
    return value
