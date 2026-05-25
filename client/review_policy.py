from __future__ import annotations

from datetime import datetime, timedelta

from client import load_user_settings
from client.config import DEFAULT_SKIP_DURATION_DAYS, DEMO_SKIP_DURATION_MINUTES

REVIEW_MODE_DAYS = "days"
REVIEW_MODE_DEMO_MINUTE = "demo_minute"


def get_skip_expiration(
    settings: dict | None = None,
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Return the skip expiry timestamp and a user-facing interval label."""
    resolved_settings = settings if settings is not None else load_user_settings()
    now_dt = now or datetime.now()
    if resolved_settings.get("skip_review_mode") == REVIEW_MODE_DEMO_MINUTE:
        expires_at = now_dt + timedelta(minutes=DEMO_SKIP_DURATION_MINUTES)
        return expires_at.isoformat(), "через 1 минуту"

    days = _coerce_positive_int(
        resolved_settings.get("skip_duration_days"),
        DEFAULT_SKIP_DURATION_DAYS,
    )
    expires_at = now_dt + timedelta(days=days)
    return expires_at.isoformat(), _format_days(days)


def _coerce_positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _format_days(days: int) -> str:
    if days % 10 == 1 and days % 100 != 11:
        word = "день"
    elif days % 10 in {2, 3, 4} and days % 100 not in {12, 13, 14}:
        word = "дня"
    else:
        word = "дней"
    return f"через {days} {word}"
