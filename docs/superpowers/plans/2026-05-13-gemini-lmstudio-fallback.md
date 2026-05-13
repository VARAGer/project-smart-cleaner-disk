# Gemini Primary With LM Studio Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Gemini 1.5 Flash as the primary backend AI provider, add LM Studio with `Qwen3.5-9B` as a fallback when Gemini returns no usable result, and add opt-in real-provider evaluation tooling.

**Architecture:** The backend remains the sole AI proxy. `classify_files()` builds one prompt, attempts Gemini first, falls back to LM Studio on technical or structural failure, and only then returns backend defaults. Deterministic tests verify the provider chain; a separate developer-invoked harness reuses seeded synthetic batches to evaluate real Gemini and LM Studio outputs.

**Tech Stack:** FastAPI, Python 3.12, httpx, Pydantic v2, pytest, pytest-asyncio, existing seeded factories in `server/tests/factories.py`, Gemini REST API, LM Studio OpenAI-compatible API.

---

## File Map

- Modify `server/config.py`
  - Remove Groq from the active provider path.
  - Add LM Studio configuration and local fallback toggle.
- Modify `.env.example`
  - Replace Groq examples with LM Studio examples.
- Modify `server/docker-compose.yml`
  - Pass LM Studio fallback settings into the backend container.
- Modify `server/services/ai_service.py`
  - Implement Gemini-first / LM-Studio-second / defaults-third orchestration.
  - Add structured-output LM Studio request payload.
  - Add strict provider-success validation separate from result normalization.
- Modify `server/tests/conftest.py`
  - Seed test-only LM Studio settings instead of Groq settings.
- Modify `server/tests/test_ai_service.py`
  - Replace Groq tests with LM Studio provider tests.
  - Add fallback-chain tests for malformed and incomplete Gemini responses.
- Modify `server/tests/integration/test_analysis_integration.py`
  - Preserve API-level round-trip coverage while adapting comments or setup if needed.
- Create `server/tests/evals/__init__.py`
  - Mark eval package.
- Create `server/tests/evals/test_real_provider_batches.py`
  - Opt-in provider evaluation tests that call Gemini and LM Studio only when explicitly enabled.
- Create `server/tests/evals/eval_utils.py`
  - Shared helpers for provider invocation, validation, and artifact persistence.
- Create `docs/ai-provider-evals.md`
  - How to run real-provider checks and how to hand results off for semantic review.

---

### Task 1: Replace Groq configuration with LM Studio fallback settings

**Files:**
- Modify: `server/config.py`
- Modify: `.env.example`
- Modify: `server/docker-compose.yml`
- Modify: `server/tests/conftest.py`

- [ ] **Step 1: Write the failing expectations into tests/import setup**

Update `server/tests/conftest.py` so tests seed LM Studio settings and no longer seed Groq:

```python
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-longer-than-32-characters")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("AI_PROVIDER", "gemini")
os.environ.setdefault("AI_ENABLE_LOCAL_FALLBACK", "true")
os.environ.setdefault("LM_STUDIO_BASE_URL", "http://lmstudio.test/v1")
os.environ.setdefault("LM_STUDIO_MODEL", "qwen/qwen3.5-9b")
os.environ.setdefault("LM_STUDIO_TIMEOUT_SECONDS", "60")
os.environ.setdefault("BCRYPT_ROUNDS", "4")
```

- [ ] **Step 2: Run one AI test file to verify imports still reveal missing config support**

Run:

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: existing tests still reference Groq or config imports do not yet expose the LM Studio settings needed by later tasks.

- [ ] **Step 3: Update `server/config.py` with LM Studio settings and remove Groq active-path requirements**

Use this shape:

```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-1.5-flash:generateContent"
)

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")

AI_ENABLE_LOCAL_FALLBACK = (
    os.getenv("AI_ENABLE_LOCAL_FALLBACK", "true").lower() == "true"
)
LM_STUDIO_BASE_URL = os.getenv(
    "LM_STUDIO_BASE_URL",
    "http://127.0.0.1:1234/v1",
).rstrip("/")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3.5-9b")
LM_STUDIO_TIMEOUT_SECONDS = int(
    os.getenv("LM_STUDIO_TIMEOUT_SECONDS", str(AI_TIMEOUT_SECONDS))
)
```

Then update the production fail-fast checks:

```python
if IS_PROD:
    ...
    if not GEMINI_API_KEY and AI_PROVIDER == "gemini":
        _fatal("GEMINI_API_KEY is required when AI_PROVIDER=gemini in production")
```

Remove the Groq production key check entirely.

- [ ] **Step 4: Update `.env.example`**

Replace the provider section with:

```env
# Backend AI provider settings
GEMINI_API_KEY=
AI_PROVIDER=gemini

# Optional local fallback through LM Studio.
AI_ENABLE_LOCAL_FALLBACK=true
LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1
LM_STUDIO_MODEL=qwen/qwen3.5-9b
LM_STUDIO_TIMEOUT_SECONDS=60
```

- [ ] **Step 5: Update `server/docker-compose.yml`**

Replace the backend AI environment block with:

```yaml
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - AI_PROVIDER=${AI_PROVIDER:-gemini}
      - AI_ENABLE_LOCAL_FALLBACK=${AI_ENABLE_LOCAL_FALLBACK:-true}
      - LM_STUDIO_BASE_URL=${LM_STUDIO_BASE_URL:-http://host.docker.internal:1234/v1}
      - LM_STUDIO_MODEL=${LM_STUDIO_MODEL:-qwen/qwen3.5-9b}
      - LM_STUDIO_TIMEOUT_SECONDS=${LM_STUDIO_TIMEOUT_SECONDS:-60}
```

- [ ] **Step 6: Re-run focused config/import tests**

Run:

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: imports succeed; any remaining failures should now be behavioral tests still aimed at Groq and will be handled in Task 2.

- [ ] **Step 7: Commit**

```powershell
git add server/config.py .env.example server/docker-compose.yml server/tests/conftest.py
git commit -m "feat: configure lm studio fallback provider"
```

---

### Task 2: Implement provider orchestration and strict Gemini fallback behavior

**Files:**
- Modify: `server/services/ai_service.py`
- Modify: `server/tests/test_ai_service.py`

- [ ] **Step 1: Replace the Groq happy-path test with an LM Studio happy-path test**

In `server/tests/test_ai_service.py`, replace `test_groq_happy_path` with:

```python
async def test_lm_studio_happy_path(self, monkeypatch):
    monkeypatch.setattr(ai_service, "AI_PROVIDER", "gemini")

    async def fake_gemini(_prompt: str) -> str:
        raise httpx.TimeoutException("gemini down")

    lm_payload = {
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

    mock = _MockAsyncClient(_MockHttpResponse(lm_payload))
    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    monkeypatch.setattr(httpx, "AsyncClient", mock)

    result = await classify_files(_sample_files())
    assert result[0]["confidence"] == 0.88
```

- [ ] **Step 2: Add tests for malformed and incomplete Gemini output triggering LM Studio**

Add:

```python
async def test_gemini_malformed_json_falls_back_to_lm_studio(self, monkeypatch):
    monkeypatch.setattr(ai_service, "AI_PROVIDER", "gemini")

    async def fake_gemini(_prompt: str) -> str:
        return "not-json"

    async def fake_lm_studio(_prompt: str) -> str:
        return json.dumps({
            "classifications": [
                {
                    "file_id": "abc123",
                    "confidence": 0.91,
                    "category": "installer",
                    "reason": "fallback",
                }
            ]
        })

    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    monkeypatch.setattr(ai_service, "_call_lm_studio", fake_lm_studio)

    result = await classify_files(_sample_files())
    assert result[0]["confidence"] == 0.91
    assert result[0]["reason"] == "fallback"


async def test_gemini_incomplete_batch_falls_back_to_lm_studio(self, monkeypatch):
    monkeypatch.setattr(ai_service, "AI_PROVIDER", "gemini")
    files = [
        {"file_id": "a", "filename": "f1", "extension": "", "size_bytes": 1,
         "modified_at": "", "accessed_at": "", "parent_dir": ""},
        {"file_id": "b", "filename": "f2", "extension": "", "size_bytes": 1,
         "modified_at": "", "accessed_at": "", "parent_dir": ""},
    ]

    async def fake_gemini(_prompt: str) -> str:
        return json.dumps({
            "classifications": [
                {"file_id": "a", "confidence": 0.9, "category": "cache", "reason": "r"}
            ]
        })

    async def fake_lm_studio(_prompt: str) -> str:
        return json.dumps({
            "classifications": [
                {"file_id": "a", "confidence": 0.6, "category": "cache", "reason": "lm-a"},
                {"file_id": "b", "confidence": 0.7, "category": "document", "reason": "lm-b"},
            ]
        })

    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    monkeypatch.setattr(ai_service, "_call_lm_studio", fake_lm_studio)

    result = await classify_files(files)
    by_id = {item["file_id"]: item for item in result}
    assert by_id["a"]["reason"] == "lm-a"
    assert by_id["b"]["reason"] == "lm-b"
```

- [ ] **Step 3: Run the new fallback tests and confirm they fail before implementation**

Run:

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: failures because `_call_lm_studio()` and strict “provider success” validation do not exist yet.

- [ ] **Step 4: Add LM Studio imports/config and helper constants in `server/services/ai_service.py`**

Update imports:

```python
from config import (
    AI_ENABLE_LOCAL_FALLBACK,
    AI_PROVIDER,
    AI_TEMPERATURE,
    AI_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
    GEMINI_API_URL,
    LM_STUDIO_BASE_URL,
    LM_STUDIO_MODEL,
    LM_STUDIO_TIMEOUT_SECONDS,
)
```

Add allowed categories and JSON schema:

```python
ALLOWED_CATEGORIES = {
    "document", "media", "installer", "cache", "temp", "archive",
    "backup", "database", "code", "config", "log", "other",
}

LM_STUDIO_RESPONSE_SCHEMA = {
    "name": "file_classifications",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "classifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "file_id": {"type": "string"},
                        "confidence": {"type": "number"},
                        "category": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["file_id", "confidence", "category", "reason"],
                },
            }
        },
        "required": ["classifications"],
    },
}
```

- [ ] **Step 5: Implement strict provider-success validation**

Add:

```python
def _provider_response_is_complete(
    original_files: list[dict],
    classifications: list[dict],
) -> bool:
    requested_ids = [f["file_id"] for f in original_files]
    response_ids = [c.get("file_id") for c in classifications]

    if len(classifications) != len(original_files):
        return False
    if set(response_ids) != set(requested_ids):
        return False
    if len(response_ids) != len(set(response_ids)):
        return False

    for item in classifications:
        if not isinstance(item, dict):
            return False
        if not isinstance(item.get("file_id"), str):
            return False
        try:
            confidence = float(item["confidence"])
        except (KeyError, TypeError, ValueError):
            return False
        if not 0.0 <= confidence <= 1.0:
            return False
        if str(item.get("category", "")) not in ALLOWED_CATEGORIES:
            return False
        if not str(item.get("reason", "")).strip():
            return False
    return True
```

- [ ] **Step 6: Add `_call_lm_studio()`**

```python
async def _call_lm_studio(user_prompt: str) -> str:
    payload = {
        "model": LM_STUDIO_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": AI_TEMPERATURE,
        "response_format": {
            "type": "json_schema",
            "json_schema": LM_STUDIO_RESPONSE_SCHEMA,
        },
        "chat_template_kwargs": {
            "enable_thinking": False,
        },
    }

    async with httpx.AsyncClient(timeout=LM_STUDIO_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{LM_STUDIO_BASE_URL}/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"]
```

- [ ] **Step 7: Rewrite `classify_files()` orchestration**

Replace the current single-provider `try/except` with:

```python
async def classify_files(files: list[dict]) -> list[dict]:
    current_date = datetime.now().strftime("%Y-%m-%d")
    user_prompt = (
        f"Текущая дата: {current_date}\n\n"
        f"Классифицируй следующие файлы:\n\n"
        f"{json.dumps(files, ensure_ascii=False, indent=2)}"
    )

    if AI_PROVIDER != "gemini":
        logger.warning(
            "Unsupported primary provider requested: %s; using Gemini flow",
            AI_PROVIDER,
        )

    try:
        raw_gemini = await _call_gemini(user_prompt)
        gemini_items = _parse_response(raw_gemini)
        if _provider_response_is_complete(files, gemini_items):
            return _validate_classifications(files, gemini_items)
        logger.warning(
            "Gemini response rejected as unusable (n_files=%d)",
            len(files),
        )
    except Exception as exc:
        logger.error(
            "Gemini classification failed: %s (n_files=%d)",
            type(exc).__name__,
            len(files),
        )

    if AI_ENABLE_LOCAL_FALLBACK:
        logger.info("Starting LM Studio fallback (n_files=%d)", len(files))
        try:
            raw_local = await _call_lm_studio(user_prompt)
            local_items = _parse_response(raw_local)
            if _provider_response_is_complete(files, local_items):
                return _validate_classifications(files, local_items)
            logger.warning(
                "LM Studio response rejected as unusable (n_files=%d)",
                len(files),
            )
        except Exception as exc:
            logger.error(
                "LM Studio fallback failed: %s (n_files=%d)",
                type(exc).__name__,
                len(files),
            )

    logger.warning(
        "Returning default classifications after provider failures (n_files=%d)",
        len(files),
    )
    return _default_classifications(files)
```

- [ ] **Step 8: Update or remove stale Groq test cases**

Delete direct Groq provider assertions from `server/tests/test_ai_service.py`. Keep or adapt any generic default-path tests so they verify defaults after Gemini and LM Studio both fail.

- [ ] **Step 9: Run focused unit tests**

Run:

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add server/services/ai_service.py server/tests/test_ai_service.py
git commit -m "feat: add lm studio fallback orchestration"
```

---

### Task 3: Preserve API-level behavior and prove fallback semantics at the route boundary

**Files:**
- Modify: `server/tests/integration/test_analysis_integration.py`
- Optional Modify: `server/tests/test_analysis_router.py`

- [ ] **Step 1: Add an integration-style route test for Gemini malformed JSON -> LM Studio recovery**

Append to `server/tests/integration/test_analysis_integration.py`:

```python
async def test_route_recovers_via_lm_studio_when_gemini_json_is_broken(
    pg_client: AsyncClient,
    monkeypatch,
):
    import json as _json
    from services import ai_service

    token = await _register(pg_client, "lm_fallback_json")
    payload = analysis_payload(seed=15, file_count=5, scan_id="s-lm-json")

    async def fake_gemini(_prompt: str) -> str:
        return "{not valid json"

    async def fake_lm_studio(user_prompt: str) -> str:
        json_start = user_prompt.index("[")
        files = _json.loads(user_prompt[json_start:])
        return _json.dumps({
            "classifications": [
                {
                    "file_id": f["file_id"],
                    "confidence": 0.77,
                    "category": "other",
                    "reason": "local fallback",
                }
                for f in files
            ]
        })

    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    monkeypatch.setattr(ai_service, "_call_lm_studio", fake_lm_studio)

    response = await pg_client.post(
        "/api/analyze",
        headers=_auth(token),
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == "s-lm-json"
    assert len(body["classifications"]) == 5
    assert all(c["reason"] == "local fallback" for c in body["classifications"])
```

- [ ] **Step 2: Run the new integration test and confirm expected failure before behavior lands**

Run:

```powershell
cd server
pytest tests/integration/test_analysis_integration.py -q
```

Expected: this test should fail before Task 2 is merged; after Task 2 it should pass.

- [ ] **Step 3: Keep the existing partial-response test aligned with the new semantics**

Update `test_missing_file_ids_filled_with_defaults` so it no longer models the provider as “successful but incomplete”. Under the new design, incomplete Gemini output is a fallback trigger. Change it to stub both Gemini and LM Studio as incomplete and assert defaults are ultimately returned:

```python
async def test_incomplete_ai_responses_fall_through_to_defaults(
    pg_client: AsyncClient,
    monkeypatch,
):
    import json as _json
    from services import ai_service

    token = await _register(pg_client, "partial_resp")
    payload = analysis_payload(seed=13, file_count=20, scan_id="s-partial")

    async def incomplete_response(user_prompt: str) -> str:
        json_start = user_prompt.index("[")
        files = _json.loads(user_prompt[json_start:])
        half = files[: len(files) // 2]
        return _json.dumps({
            "classifications": [
                {
                    "file_id": f["file_id"],
                    "confidence": 0.8,
                    "category": "temp",
                    "reason": "r",
                }
                for f in half
            ]
        })

    monkeypatch.setattr(ai_service, "_call_gemini", incomplete_response)
    monkeypatch.setattr(ai_service, "_call_lm_studio", incomplete_response)

    response = await pg_client.post(
        "/api/analyze",
        headers=_auth(token),
        json=payload,
    )
    assert response.status_code == 200
    classifications = response.json()["classifications"]
    assert len(classifications) == 20
    assert all(c["confidence"] == 0.5 for c in classifications)
    assert all(c["category"] == "other" for c in classifications)
```

- [ ] **Step 4: Run route and integration analysis coverage**

Run:

```powershell
cd server
pytest tests/test_analysis_router.py tests/integration/test_analysis_integration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/tests/integration/test_analysis_integration.py server/tests/test_analysis_router.py
git commit -m "test: cover analysis fallback route behavior"
```

---

### Task 4: Add opt-in real-provider evaluation harness

**Files:**
- Create: `server/tests/evals/__init__.py`
- Create: `server/tests/evals/eval_utils.py`
- Create: `server/tests/evals/test_real_provider_batches.py`

- [ ] **Step 1: Add the eval package marker**

Create `server/tests/evals/__init__.py` as an empty file.

- [ ] **Step 2: Write the eval helper module**

Create `server/tests/evals/eval_utils.py`:

```python
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services import ai_service


ALLOWED_CATEGORIES = ai_service.ALLOWED_CATEGORIES
ARTIFACT_ROOT = Path(os.getenv("AI_EVAL_ARTIFACT_DIR", "artifacts/ai-evals"))


def validate_provider_payload(
    files: list[dict],
    raw_text: str,
) -> tuple[bool, list[str], list[dict]]:
    errors: list[str] = []
    try:
        parsed = ai_service._parse_response(raw_text)
    except Exception as exc:
        return False, [f"parse_error:{type(exc).__name__}"], []

    requested_ids = [f["file_id"] for f in files]
    response_ids = [item.get("file_id") for item in parsed]

    if len(parsed) != len(files):
        errors.append("length_mismatch")
    if set(response_ids) != set(requested_ids):
        errors.append("id_set_mismatch")
    if len(response_ids) != len(set(response_ids)):
        errors.append("duplicate_file_ids")

    for item in parsed:
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            errors.append(f"bad_confidence:{item.get('file_id')}")
            continue
        if not 0.0 <= confidence <= 1.0:
            errors.append(f"confidence_out_of_range:{item.get('file_id')}")
        if str(item.get("category", "")) not in ALLOWED_CATEGORIES:
            errors.append(f"bad_category:{item.get('file_id')}")
        if not str(item.get("reason", "")).strip():
            errors.append(f"empty_reason:{item.get('file_id')}")

    return not errors, errors, parsed


def write_eval_artifacts(
    provider: str,
    seed: int,
    files: list[dict],
    raw_text: str,
    ok: bool,
    errors: list[str],
    parsed: list[dict],
) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = ARTIFACT_ROOT / provider / f"seed-{seed}-{timestamp}"
    target.mkdir(parents=True, exist_ok=True)

    (target / "input-files.json").write_text(
        json.dumps(files, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "raw-response.txt").write_text(raw_text, encoding="utf-8")
    (target / "parsed-classifications.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "summary.json").write_text(
        json.dumps({"ok": ok, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 3: Write the opt-in provider eval tests**

Create `server/tests/evals/test_real_provider_batches.py`:

```python
from __future__ import annotations

import os

import pytest

from services import ai_service
from tests.evals.eval_utils import validate_provider_payload, write_eval_artifacts
from tests.factories import file_batch


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_AI_EVALS") != "1",
    reason="Set RUN_REAL_AI_EVALS=1 to call real Gemini and LM Studio providers.",
)


@pytest.mark.parametrize("seed", [501, 902])
async def test_real_gemini_batches_are_structurally_valid(seed: int):
    files = file_batch(seed=seed, n=200)
    prompt = ai_service._build_user_prompt_for_evals(files)
    raw = await ai_service._call_gemini(prompt)
    ok, errors, parsed = validate_provider_payload(files, raw)
    write_eval_artifacts("gemini", seed, files, raw, ok, errors, parsed)
    assert ok, errors


@pytest.mark.parametrize("seed", [501, 902])
async def test_real_lm_studio_batches_are_structurally_valid(seed: int):
    files = file_batch(seed=seed, n=200)
    prompt = ai_service._build_user_prompt_for_evals(files)
    raw = await ai_service._call_lm_studio(prompt)
    ok, errors, parsed = validate_provider_payload(files, raw)
    write_eval_artifacts("lmstudio", seed, files, raw, ok, errors, parsed)
    assert ok, errors
```

- [ ] **Step 4: Extract a small reusable prompt builder from `classify_files()`**

Add this helper to `server/services/ai_service.py`:

```python
def _build_user_prompt(files: list[dict]) -> str:
    current_date = datetime.now().strftime("%Y-%m-%d")
    return (
        f"Текущая дата: {current_date}\n\n"
        f"Классифицируй следующие файлы:\n\n"
        f"{json.dumps(files, ensure_ascii=False, indent=2)}"
    )


def _build_user_prompt_for_evals(files: list[dict]) -> str:
    return _build_user_prompt(files)
```

Then change `classify_files()` to call:

```python
user_prompt = _build_user_prompt(files)
```

- [ ] **Step 5: Run eval tests in skipped mode**

Run:

```powershell
cd server
pytest tests/evals/test_real_provider_batches.py -q
```

Expected: all eval tests are skipped because `RUN_REAL_AI_EVALS` is not set.

- [ ] **Step 6: Run the new eval tests against real providers when credentials/services are available**

Run:

```powershell
cd server
$env:RUN_REAL_AI_EVALS="1"
pytest tests/evals/test_real_provider_batches.py -q
```

Expected:

- Gemini tests call the live Gemini API.
- LM Studio tests call the local LM Studio server.
- Failures preserve artifacts under `server/artifacts/ai-evals/...` or the configured `AI_EVAL_ARTIFACT_DIR`.

- [ ] **Step 7: Commit**

```powershell
git add server/services/ai_service.py server/tests/evals
git commit -m "test: add real provider evaluation harness"
```

---

### Task 5: Document provider setup and manual semantic review workflow

**Files:**
- Create: `docs/ai-provider-evals.md`

- [ ] **Step 1: Write the provider eval guide**

Create `docs/ai-provider-evals.md`:

```markdown
# AI Provider Evaluation Guide

## Purpose

Use this workflow to compare real Gemini and LM Studio responses on the same
deterministic file metadata batches without making those checks part of normal CI.

## Prerequisites

- `GEMINI_API_KEY` is configured.
- LM Studio is running locally with `Qwen3.5-9B`.
- The LM Studio OpenAI-compatible server is enabled.
- Backend/container callers use:
  - native process: `http://127.0.0.1:1234/v1`
  - Docker backend on Windows/macOS: `http://host.docker.internal:1234/v1`

## Run Structural Provider Checks

```powershell
cd server
$env:RUN_REAL_AI_EVALS="1"
pytest tests/evals/test_real_provider_batches.py -q
```

## Outputs

Artifacts are written to:

```text
server/artifacts/ai-evals/<provider>/seed-<seed>-<timestamp>/
```

Each run captures:

- `input-files.json`
- `raw-response.txt`
- `parsed-classifications.json`
- `summary.json`

## Manual Semantic Review

Structural checks do not prove that a model made sound deletion recommendations.
For manual review, compare Gemini and LM Studio outputs on the same seed and look for:

- Overconfident deletion recommendations on risky files.
- Incorrect or weak categories.
- Reasons that are technically valid but not useful to the user.
- Instability around borderline cases such as documents, backups, projects, and unique media.
```

- [ ] **Step 2: Add the documentation file forcefully if root `.gitignore` still ignores Markdown**

Run:

```powershell
git add -f docs/ai-provider-evals.md
```

Expected: the file is staged despite the repo-wide `*.md` ignore rule.

- [ ] **Step 3: Commit**

```powershell
git commit -m "docs: describe ai provider eval workflow"
```

---

### Task 6: Run full verification for the backend slice

**Files:**
- No new files unless verification exposes failures that must be fixed.

- [ ] **Step 1: Run focused unit and route tests**

```powershell
cd server
pytest tests/test_ai_service.py tests/test_analysis_router.py -q
```

Expected: PASS.

- [ ] **Step 2: Run integration analysis coverage**

```powershell
cd server
pytest tests/integration/test_analysis_integration.py -q
```

Expected: PASS.

- [ ] **Step 3: Run the entire backend suite**

```powershell
cd server
pytest -q
```

Expected: PASS, except any explicitly environment-dependent integration markers already documented by the repository.

- [ ] **Step 4: Run eval tests in skipped mode**

```powershell
cd server
pytest tests/evals/test_real_provider_batches.py -q
```

Expected: SKIPPED when `RUN_REAL_AI_EVALS` is not set.

- [ ] **Step 5: Optionally run real-provider evals**

```powershell
cd server
$env:RUN_REAL_AI_EVALS="1"
pytest tests/evals/test_real_provider_batches.py -q
```

Expected: PASS only when Gemini credentials are valid and LM Studio is running with the expected model/configuration. Preserve artifacts for semantic review.

- [ ] **Step 6: Final commit if verification-driven fixes were needed**

```powershell
git add <files-fixed-during-verification>
git commit -m "test: stabilize lm studio fallback verification"
```

---

## Self-Review

- Spec coverage:
  - Gemini remains primary: Tasks 1-2.
  - LM Studio fallback on technical and structural Gemini failure: Tasks 2-3.
  - Defaults only after both providers fail: Tasks 2-3.
  - Docker and env updates: Task 1.
  - Opt-in real-provider batch evaluation: Task 4.
  - Manual semantic review workflow: Task 5.
- Placeholder scan:
  - No `TBD`, `TODO`, or “implement later” placeholders remain.
- Type consistency:
  - `classify_files()`, `_call_gemini()`, `_call_lm_studio()`, `_parse_response()`,
    `_provider_response_is_complete()`, and `_build_user_prompt()` names remain consistent throughout the plan.
