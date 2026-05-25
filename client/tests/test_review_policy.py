from datetime import datetime

from client.review_policy import get_skip_expiration


def test_demo_review_mode_expires_in_one_minute():
    expires_at, label = get_skip_expiration(
        {"skip_review_mode": "demo_minute"},
        now=datetime(2026, 5, 25, 12, 0, 0),
    )

    assert expires_at == "2026-05-25T12:01:00"
    assert label == "через 1 минуту"


def test_regular_review_mode_uses_configured_days():
    expires_at, label = get_skip_expiration(
        {"skip_review_mode": "days", "skip_duration_days": 30},
        now=datetime(2026, 5, 25, 12, 0, 0),
    )

    assert expires_at == "2026-06-24T12:00:00"
    assert label == "через 30 дней"
