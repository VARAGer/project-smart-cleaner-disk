"""
Tests for services.ai_service.

Unit-tests cover the pure helpers (_parse_response, _validate_classifications,
_default_classifications). Integration-tests cover classify_files with mocked
httpx to avoid real API calls.
"""

import json

import httpx
import pytest

from services import ai_service
from services.ai_service import (
    _default_classifications,
    _parse_response,
    _validate_classifications,
    classify_files,
)


# ===== _parse_response =====

class TestParseResponse:
    def test_wrapped_in_classifications_key(self):
        raw = json.dumps(
            {
                "classifications": [
                    {"file_id": "a", "confidence": 0.9,
                     "category": "cache", "reason": "r"}
                ]
            }
        )
        result = _parse_response(raw)
        assert len(result) == 1
        assert result[0]["file_id"] == "a"

    def test_bare_array(self):
        raw = json.dumps(
            [{"file_id": "a", "confidence": 0.9,
              "category": "cache", "reason": "r"}]
        )
        result = _parse_response(raw)
        assert len(result) == 1

    def test_markdown_fenced_json(self):
        raw = '```json\n{"classifications": [{"file_id": "x", "confidence": 0.5, "category": "other", "reason": "r"}]}\n```'
        result = _parse_response(raw)
        assert result[0]["file_id"] == "x"

    def test_other_key_with_list_inside(self):
        raw = json.dumps(
            {
                "results": [
                    {"file_id": "y", "confidence": 0.3,
                     "category": "code", "reason": "r"}
                ]
            }
        )
        result = _parse_response(raw)
        assert result[0]["file_id"] == "y"

    def test_raises_on_garbage(self):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            _parse_response("not json at all")

    def test_raises_on_empty_dict(self):
        with pytest.raises(ValueError):
            _parse_response(json.dumps({}))


# ===== _validate_classifications =====

class TestValidateClassifications:
    def test_keeps_only_requested_file_ids(self):
        requested = [{"file_id": "a"}, {"file_id": "b"}]
        got = [
            {"file_id": "a", "confidence": 0.9, "category": "cache", "reason": "r"},
            {"file_id": "b", "confidence": 0.5, "category": "other", "reason": "r"},
            {"file_id": "ghost", "confidence": 1.0, "category": "spam", "reason": "r"},
        ]
        result = _validate_classifications(requested, got)
        ids = {c["file_id"] for c in result}
        assert ids == {"a", "b"}

    def test_fills_missing_with_defaults(self):
        requested = [{"file_id": "a"}, {"file_id": "b"}]
        got = [
            {"file_id": "a", "confidence": 0.9, "category": "cache", "reason": "r"}
        ]
        result = _validate_classifications(requested, got)
        by_id = {c["file_id"]: c for c in result}
        assert by_id["b"]["confidence"] == 0.5
        assert by_id["b"]["category"] == "other"
        assert by_id["b"]["reason"] == "Не удалось классифицировать"

    def test_clamps_confidence_above_one(self):
        requested = [{"file_id": "a"}]
        got = [
            {"file_id": "a", "confidence": 1.7,
             "category": "cache", "reason": "r"}
        ]
        result = _validate_classifications(requested, got)
        assert result[0]["confidence"] == 1.0

    def test_clamps_confidence_below_zero(self):
        requested = [{"file_id": "a"}]
        got = [
            {"file_id": "a", "confidence": -0.5,
             "category": "cache", "reason": "r"}
        ]
        result = _validate_classifications(requested, got)
        assert result[0]["confidence"] == 0.0

    def test_coerces_non_string_fields(self):
        requested = [{"file_id": "a"}]
        got = [
            {"file_id": "a", "confidence": "0.7",
             "category": 123, "reason": None}
        ]
        result = _validate_classifications(requested, got)
        assert result[0]["confidence"] == 0.7
        assert result[0]["category"] == "123"
        assert isinstance(result[0]["reason"], str)

    def test_missing_confidence_uses_default(self):
        requested = [{"file_id": "a"}]
        got = [{"file_id": "a", "category": "cache", "reason": "r"}]
        result = _validate_classifications(requested, got)
        assert result[0]["confidence"] == 0.5

    def test_empty_response_returns_all_defaults(self):
        requested = [{"file_id": "a"}, {"file_id": "b"}]
        result = _validate_classifications(requested, [])
        assert len(result) == 2
        assert all(c["confidence"] == 0.5 for c in result)


# ===== _default_classifications =====

class TestDefaultClassifications:
    def test_returns_one_per_file(self):
        files = [{"file_id": "a"}, {"file_id": "b"}, {"file_id": "c"}]
        result = _default_classifications(files)
        assert len(result) == 3
        assert {c["file_id"] for c in result} == {"a", "b", "c"}

    def test_uses_unavailable_reason(self):
        result = _default_classifications([{"file_id": "a"}])
        assert "недоступен" in result[0]["reason"]
        assert result[0]["confidence"] == 0.5
        assert result[0]["category"] == "other"


# ===== classify_files (end-to-end with mocked HTTP) =====

def _sample_files():
    return [
        {
            "file_id": "abc123",
            "filename": "setup.exe",
            "extension": ".exe",
            "size_bytes": 5_000_000,
            "modified_at": "2024-01-01T00:00:00",
            "accessed_at": "",
            "parent_dir": "C:/Downloads",
        }
    ]


class _MockHttpResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err", request=None, response=None  # type: ignore[arg-type]
            )

    def json(self):
        return self._payload


class _MockAsyncClient:
    def __init__(self, response: _MockHttpResponse):
        self._response = response

    def __call__(self, *_args, **_kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, *_args, **_kwargs):
        return self._response


class TestClassifyFilesMocked:
    async def test_gemini_happy_path(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_PROVIDER", "gemini")
        gemini_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "classifications": [
                                        {
                                            "file_id": "abc123",
                                            "confidence": 0.95,
                                            "category": "installer",
                                            "reason": "Installer in Downloads",
                                        }
                                    ]
                                })
                            }
                        ]
                    }
                }
            ]
        }
        mock = _MockAsyncClient(_MockHttpResponse(gemini_payload))
        monkeypatch.setattr(httpx, "AsyncClient", mock)

        result = await classify_files(_sample_files())
        assert len(result) == 1
        assert result[0]["file_id"] == "abc123"
        assert result[0]["confidence"] == 0.95
        assert result[0]["category"] == "installer"

    async def test_groq_happy_path(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_PROVIDER", "groq")
        groq_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "classifications": [
                                {
                                    "file_id": "abc123",
                                    "confidence": 0.88,
                                    "category": "installer",
                                    "reason": "ok",
                                }
                            ]
                        })
                    }
                }
            ]
        }
        mock = _MockAsyncClient(_MockHttpResponse(groq_payload))
        monkeypatch.setattr(httpx, "AsyncClient", mock)

        result = await classify_files(_sample_files())
        assert result[0]["confidence"] == 0.88

    async def test_http_error_returns_defaults(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_PROVIDER", "gemini")
        mock = _MockAsyncClient(_MockHttpResponse({}, status=500))
        monkeypatch.setattr(httpx, "AsyncClient", mock)

        result = await classify_files(_sample_files())
        assert result[0]["confidence"] == 0.5
        assert result[0]["category"] == "other"
        assert "недоступен" in result[0]["reason"]

    async def test_unknown_provider_returns_defaults(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_PROVIDER", "wizard-ai")
        result = await classify_files(_sample_files())
        assert result[0]["confidence"] == 0.5
        assert result[0]["category"] == "other"

    async def test_missing_files_in_response_get_defaults(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_PROVIDER", "gemini")
        # Model only classifies one of two files.
        gemini_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "classifications": [
                                        {
                                            "file_id": "a",
                                            "confidence": 0.9,
                                            "category": "cache",
                                            "reason": "r",
                                        }
                                    ]
                                })
                            }
                        ]
                    }
                }
            ]
        }
        mock = _MockAsyncClient(_MockHttpResponse(gemini_payload))
        monkeypatch.setattr(httpx, "AsyncClient", mock)

        files = [
            {"file_id": "a", "filename": "f1", "extension": "",
             "size_bytes": 1, "modified_at": "", "accessed_at": "", "parent_dir": ""},
            {"file_id": "b", "filename": "f2", "extension": "",
             "size_bytes": 1, "modified_at": "", "accessed_at": "", "parent_dir": ""},
        ]
        result = await classify_files(files)
        by_id = {c["file_id"]: c for c in result}
        assert by_id["a"]["confidence"] == 0.9
        assert by_id["b"]["confidence"] == 0.5
        assert by_id["b"]["reason"] == "Не удалось классифицировать"
