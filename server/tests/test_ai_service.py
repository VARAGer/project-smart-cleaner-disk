"""
Tests for services.ai_service.

Unit-tests cover the pure helpers (_parse_response, _validate_classifications,
_default_classifications). Integration-tests cover classify_files with mocked
httpx to avoid real API calls.
"""

import asyncio
import json

import httpx
import pytest

from services import ai_service
from services.ai_service import (
    _default_classifications,
    _sanitize_files_for_ai,
    _parse_response,
    _validate_classifications,
    classify_files,
)


def test_ai_service_has_no_legacy_provider_switch():
    legacy_provider_symbol = "AI" + "_" + "PROVIDER"

    assert legacy_provider_symbol not in ai_service.__dict__


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


class TestSanitizeFilesForAi:
    def test_drops_full_path_and_unexpected_fields(self):
        files = [
            {
                "file_id": "abc",
                "filename": "report.pdf",
                "extension": ".pdf",
                "size_bytes": 1234,
                "modified_at": "2025-01-01T00:00:00",
                "accessed_at": "2025-01-02T00:00:00",
                "parent_dir": "Documents",
                "path": "C:/Users/Alice/Documents/report.pdf",
                "secret_note": "must not leave client",
            }
        ]

        result = _sanitize_files_for_ai(files)

        assert result == [
            {
                "file_id": "abc",
                "filename": "report.pdf",
                "extension": ".pdf",
                "size_bytes": 1234,
                "modified_at": "2025-01-01T00:00:00",
                "accessed_at": "2025-01-02T00:00:00",
                "parent_dir": "Documents",
            }
        ]

    def test_missing_optional_accessed_at_becomes_empty_string(self):
        result = _sanitize_files_for_ai(
            [
                {
                    "file_id": "abc",
                    "filename": "x.tmp",
                    "extension": ".tmp",
                    "size_bytes": 1,
                    "modified_at": "2025-01-01T00:00:00",
                    "parent_dir": "Temp",
                }
            ]
        )

        assert result[0]["accessed_at"] == ""


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
    def __init__(
        self,
        payload: dict,
        status: int = 200,
        headers: dict | None = None,
    ):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

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


class _SequenceAsyncClient:
    def __init__(self, responses: list[_MockHttpResponse]):
        self._responses = list(responses)
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, *_args, **_kwargs):
        self.calls += 1
        return self._responses.pop(0)


class _CapturingAsyncClient:
    calls: list[dict] = []

    def __init__(self, response: _MockHttpResponse):
        self._response = response

    def __call__(self, *_args, **_kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self._response


class TestClassifyFilesMocked:
    async def test_gemini_happy_path(self, monkeypatch):
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

    async def test_gemini_request_uses_header_key_model_url_and_sanitized_prompt(
        self, monkeypatch
    ):
        monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(ai_service, "GEMINI_MODEL", "gemini-test-model")
        monkeypatch.setattr(
            ai_service,
            "GEMINI_API_BASE_URL",
            "https://gemini.example.test/v1beta",
        )
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
                                            "confidence": 0.8,
                                            "category": "other",
                                            "reason": "ok",
                                        }
                                    ]
                                })
                            }
                        ]
                    }
                }
            ]
        }
        capturing_client = _CapturingAsyncClient(_MockHttpResponse(gemini_payload))
        capturing_client.calls = []
        monkeypatch.setattr(httpx, "AsyncClient", capturing_client)

        files = _sample_files()
        files[0]["path"] = "C:/Users/Alice/Downloads/setup.exe"
        files[0]["secret_note"] = "private"

        await classify_files(files)

        assert len(capturing_client.calls) == 1
        call = capturing_client.calls[0]
        assert call["url"] == (
            "https://gemini.example.test/v1beta/"
            "models/gemini-test-model:generateContent"
        )
        assert call["headers"]["x-goog-api-key"] == "test-key"
        assert "test-key" not in call["url"]
        prompt_text = call["json"]["contents"][0]["parts"][0]["text"]
        assert "C:/Users/Alice" not in prompt_text
        assert "secret_note" not in prompt_text
        assert "setup.exe" in prompt_text
        generation_config = call["json"]["generationConfig"]
        assert generation_config["responseMimeType"] == "application/json"

    async def test_http_error_returns_defaults(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_MAX_RETRIES", 0)
        monkeypatch.setattr(ai_service, "XAI_API_KEY", "")
        monkeypatch.setattr(ai_service, "GROQ_API_KEY", "")
        mock = _MockAsyncClient(_MockHttpResponse({}, status=500))
        monkeypatch.setattr(httpx, "AsyncClient", mock)

        result = await classify_files(_sample_files())
        assert result[0]["confidence"] == 0.5
        assert result[0]["category"] == "other"
        assert "недоступен" in result[0]["reason"]

    async def test_total_gemini_timeout_returns_defaults(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_TOTAL_TIMEOUT_SECONDS", 0.001)

        async def slow_gemini_call(_prompt):
            await asyncio.sleep(0.05)
            return json.dumps({
                "classifications": [
                    {
                        "file_id": "abc123",
                        "confidence": 0.91,
                        "category": "installer",
                        "reason": "late success",
                    }
                ]
            })

        monkeypatch.setattr(ai_service, "_call_gemini", slow_gemini_call)

        result = await classify_files(_sample_files())

        assert result[0]["confidence"] == 0.5
        assert result[0]["reason"] == "Сервис анализа временно недоступен"

    async def test_retryable_503_is_retried_before_defaulting(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_MAX_RETRIES", 2)
        monkeypatch.setattr(ai_service, "AI_RETRY_BASE_SECONDS", 0)
        monkeypatch.setattr(ai_service, "AI_RETRY_MAX_SECONDS", 0)
        monkeypatch.setattr(ai_service.random, "uniform", lambda *_: 0)
        sleeps: list[float] = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        monkeypatch.setattr(ai_service.asyncio, "sleep", fake_sleep)
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
                                            "confidence": 0.91,
                                            "category": "installer",
                                            "reason": "retry succeeded",
                                        }
                                    ]
                                })
                            }
                        ]
                    }
                }
            ]
        }
        sequence = _SequenceAsyncClient(
            [
                _MockHttpResponse({}, status=503),
                _MockHttpResponse({}, status=503),
                _MockHttpResponse(gemini_payload),
            ]
        )
        monkeypatch.setattr(httpx, "AsyncClient", sequence)

        result = await classify_files(_sample_files())

        assert sequence.calls == 3
        assert sleeps == [0, 0]
        assert result[0]["confidence"] == 0.91
        assert result[0]["reason"] == "retry succeeded"

    async def test_non_retryable_400_is_not_retried(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_MAX_RETRIES", 3)
        monkeypatch.setattr(ai_service, "XAI_API_KEY", "")
        monkeypatch.setattr(ai_service, "GROQ_API_KEY", "")
        sequence = _SequenceAsyncClient([_MockHttpResponse({}, status=400)])
        monkeypatch.setattr(httpx, "AsyncClient", sequence)

        result = await classify_files(_sample_files())

        assert sequence.calls == 1
        assert result[0]["confidence"] == 0.5

    async def test_rate_limited_429_tries_fallback_model_without_retry_after(
        self, monkeypatch
    ):
        monkeypatch.setattr(ai_service, "AI_MAX_RETRIES", 3)
        monkeypatch.setattr(ai_service, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(ai_service, "GEMINI_FALLBACK_MODELS", ["gemini-fallback"])
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
                                            "confidence": 0.88,
                                            "category": "installer",
                                            "reason": "fallback model succeeded",
                                        }
                                    ]
                                })
                            }
                        ]
                    }
                }
            ]
        }
        sequence = _SequenceAsyncClient(
            [
                _MockHttpResponse({}, status=429),
                _MockHttpResponse(gemini_payload),
            ]
        )
        monkeypatch.setattr(httpx, "AsyncClient", sequence)

        result = await classify_files(_sample_files())

        assert sequence.calls == 2
        assert result[0]["confidence"] == 0.88
        assert result[0]["reason"] == "fallback model succeeded"

    async def test_rate_limited_429_on_all_models_returns_defaults(
        self, monkeypatch
    ):
        monkeypatch.setattr(ai_service, "AI_MAX_RETRIES", 0)
        monkeypatch.setattr(ai_service, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(ai_service, "GEMINI_FALLBACK_MODELS", ["gemini-fallback"])
        monkeypatch.setattr(ai_service, "XAI_API_KEY", "")
        monkeypatch.setattr(ai_service, "GROQ_API_KEY", "")
        sequence = _SequenceAsyncClient(
            [
                _MockHttpResponse({}, status=429),
                _MockHttpResponse({}, status=429),
            ]
        )
        monkeypatch.setattr(httpx, "AsyncClient", sequence)

        result = await classify_files(_sample_files())

        assert sequence.calls == 2
        assert result[0]["confidence"] == 0.5
        assert result[0]["reason"] == "Сервис анализа временно недоступен"

    async def test_gemini_failure_uses_xai_fallback(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_MAX_RETRIES", 0)
        monkeypatch.setattr(ai_service, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(ai_service, "GEMINI_FALLBACK_MODELS", [])
        monkeypatch.setattr(ai_service, "XAI_API_KEY", "xai-key")
        monkeypatch.setattr(ai_service, "GROQ_API_KEY", "")
        xai_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "classifications": [
                                {
                                    "file_id": "abc123",
                                    "confidence": 0.87,
                                    "category": "installer",
                                    "reason": "xAI fallback succeeded",
                                }
                            ]
                        })
                    }
                }
            ]
        }
        sequence = _SequenceAsyncClient(
            [
                _MockHttpResponse({}, status=429),
                _MockHttpResponse(xai_payload),
            ]
        )
        monkeypatch.setattr(httpx, "AsyncClient", sequence)

        result = await classify_files(_sample_files())

        assert sequence.calls == 2
        assert result[0]["confidence"] == 0.87
        assert result[0]["reason"] == "xAI fallback succeeded"

    async def test_gemini_failure_uses_groq_fallback(self, monkeypatch):
        monkeypatch.setattr(ai_service, "AI_MAX_RETRIES", 0)
        monkeypatch.setattr(ai_service, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(ai_service, "GEMINI_FALLBACK_MODELS", [])
        monkeypatch.setattr(ai_service, "XAI_API_KEY", "")
        monkeypatch.setattr(ai_service, "GROQ_API_KEY", "groq-key")
        groq_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "classifications": [
                                {
                                    "file_id": "abc123",
                                    "confidence": 0.86,
                                    "category": "installer",
                                    "reason": "Groq fallback succeeded",
                                }
                            ]
                        })
                    }
                }
            ]
        }
        sequence = _SequenceAsyncClient(
            [
                _MockHttpResponse({}, status=429),
                _MockHttpResponse(groq_payload),
            ]
        )
        monkeypatch.setattr(httpx, "AsyncClient", sequence)

        result = await classify_files(_sample_files())

        assert sequence.calls == 2
        assert result[0]["confidence"] == 0.86
        assert result[0]["reason"] == "Groq fallback succeeded"

    async def test_xai_request_uses_bearer_key_and_json_response_format(
        self, monkeypatch
    ):
        monkeypatch.setattr(ai_service, "XAI_API_KEY", "xai-key")
        monkeypatch.setattr(ai_service, "XAI_MODEL", "grok-test")
        monkeypatch.setattr(ai_service, "XAI_API_BASE_URL", "https://api.x.ai/v1")
        xai_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "classifications": [
                                {
                                    "file_id": "abc123",
                                    "confidence": 0.8,
                                    "category": "other",
                                    "reason": "ok",
                                }
                            ]
                        })
                    }
                }
            ]
        }
        capturing_client = _CapturingAsyncClient(_MockHttpResponse(xai_payload))
        capturing_client.calls = []
        monkeypatch.setattr(httpx, "AsyncClient", capturing_client)

        raw = await ai_service._call_xai("classify me")

        assert json.loads(raw)["classifications"][0]["file_id"] == "abc123"
        assert len(capturing_client.calls) == 1
        call = capturing_client.calls[0]
        assert call["url"] == "https://api.x.ai/v1/chat/completions"
        assert call["headers"]["Authorization"] == "Bearer xai-key"
        assert call["headers"]["Content-Type"] == "application/json"
        assert call["json"]["model"] == "grok-test"
        assert call["json"]["response_format"] == {"type": "json_object"}
        assert call["json"]["messages"][0]["role"] == "system"
        assert call["json"]["messages"][1]["content"] == "classify me"

    async def test_groq_request_uses_bearer_key_and_json_response_format(
        self, monkeypatch
    ):
        monkeypatch.setattr(ai_service, "GROQ_API_KEY", "groq-key")
        monkeypatch.setattr(ai_service, "GROQ_MODEL", "groq-test")
        monkeypatch.setattr(
            ai_service,
            "GROQ_API_BASE_URL",
            "https://api.groq.com/openai/v1",
        )
        groq_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "classifications": [
                                {
                                    "file_id": "abc123",
                                    "confidence": 0.8,
                                    "category": "other",
                                    "reason": "ok",
                                }
                            ]
                        })
                    }
                }
            ]
        }
        capturing_client = _CapturingAsyncClient(_MockHttpResponse(groq_payload))
        capturing_client.calls = []
        monkeypatch.setattr(httpx, "AsyncClient", capturing_client)

        raw = await ai_service._call_groq("classify me")

        assert json.loads(raw)["classifications"][0]["file_id"] == "abc123"
        assert len(capturing_client.calls) == 1
        call = capturing_client.calls[0]
        assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
        assert call["headers"]["Authorization"] == "Bearer groq-key"
        assert call["headers"]["Content-Type"] == "application/json"
        assert call["json"]["model"] == "groq-test"
        assert call["json"]["response_format"] == {"type": "json_object"}
        assert call["json"]["messages"][0]["role"] == "system"
        assert call["json"]["messages"][1]["content"] == "classify me"

    async def test_missing_files_in_response_get_defaults(self, monkeypatch):
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
