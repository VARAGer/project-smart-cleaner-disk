"""Opt-in live Gemini smoke test.

Run manually:

    LIVE_GEMINI_TEST=1 GEMINI_API_KEY=... pytest tests/integration/test_gemini_live.py -q

This test intentionally skips by default so normal CI and local unit runs do
not depend on external network/API quota.
"""

import os

import pytest


pytestmark = pytest.mark.integration


async def test_live_gemini_classifies_metadata_batch(monkeypatch):
    if os.environ.get("LIVE_GEMINI_TEST") != "1":
        pytest.skip("Set LIVE_GEMINI_TEST=1 to run the live Gemini smoke test")
    if (
        not os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY") == "test-gemini-key"
    ):
        pytest.skip("GEMINI_API_KEY is required for the live Gemini smoke test")

    from services import ai_service

    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", os.environ["GEMINI_API_KEY"])
    monkeypatch.setattr(
        ai_service,
        "GEMINI_MODEL",
        os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"),
    )

    files = [
        {
            "file_id": "live001",
            "filename": "old_installer_setup.exe",
            "extension": ".exe",
            "size_bytes": 15_728_640,
            "modified_at": "2023-01-10T12:00:00",
            "accessed_at": "2023-02-01T12:00:00",
            "parent_dir": "Downloads",
            "path": "C:/Users/Example/Downloads/old_installer_setup.exe",
        },
        {
            "file_id": "live002",
            "filename": "family_contract_scan.pdf",
            "extension": ".pdf",
            "size_bytes": 872_000,
            "modified_at": "2024-06-01T12:00:00",
            "accessed_at": "2025-01-01T12:00:00",
            "parent_dir": "Documents",
            "path": "C:/Users/Example/Documents/family_contract_scan.pdf",
        },
    ]

    result = await ai_service.classify_files(files)

    assert {item["file_id"] for item in result} == {"live001", "live002"}
    fallback_reasons = {
        "Сервис анализа временно недоступен",
        "Не удалось классифицировать",
    }
    for item in result:
        assert 0.0 <= item["confidence"] <= 1.0
        assert item["category"]
        assert item["reason"]
        assert item["reason"] not in fallback_reasons
