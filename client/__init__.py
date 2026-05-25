"""SmartCleaner client package."""

import json
import os

from client.config import (
    DATA_DIR,
    DEFAULT_MIN_AGE_MONTHS,
    DEFAULT_MIN_SIZE_BYTES,
    DEFAULT_SKIP_DURATION_DAYS,
)

_SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

_DEFAULTS: dict = {
    "theme": "light",
    "min_age_months": DEFAULT_MIN_AGE_MONTHS,
    "min_size_bytes": DEFAULT_MIN_SIZE_BYTES,
    "skip_duration_days": DEFAULT_SKIP_DURATION_DAYS,
    "skip_review_mode": "days",
}


def load_user_settings() -> dict:
    """Load user settings from disk. Returns defaults on any error."""
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Fill missing keys with defaults
            return {**_DEFAULTS, **data}
    except Exception:
        pass
    return _DEFAULTS.copy()


def save_user_settings(settings: dict) -> None:
    """Persist user settings to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
