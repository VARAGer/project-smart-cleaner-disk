# Gemini 2.5 Flash With Policy Caps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old multi-provider AI path with Gemini 2.5 Flash only, harden the prompt and structured output request, and add deterministic backend policy caps for risky deletion recommendations.

**Architecture:** The backend keeps a single provider call in `services/ai_service.py`. Gemini 2.5 Flash must return structured JSON that is parsed and validated as a complete batch; invalid output falls back to default classifications. Valid output then passes through deterministic confidence caps before it reaches the client.

**Tech Stack:** FastAPI, Python 3.12, httpx, Pydantic v2, pytest, pytest-asyncio, Gemini API structured output, existing seeded file factories in `server/tests/factories.py`.

---

## File Map

- Modify `server/config.py`
  - Remove Groq runtime configuration from the production path.
  - Point the Gemini URL at Gemini 2.5 Flash.
  - Add explicit structured-output-related constants if useful.
- Modify `.env.example`
  - Remove Groq examples.
- Modify `server/docker-compose.yml`
  - Stop passing Groq settings.
- Modify `server/tests/conftest.py`
  - Stop seeding Groq test variables.
- Modify `server/services/ai_service.py`
  - Tighten the system prompt.
  - Add Gemini structured-output schema.
  - Add strict provider-response validation.
  - Add deterministic policy cap helpers.
  - Preserve default classifications on unusable Gemini output.
- Modify `server/tests/test_ai_service.py`
  - Replace Groq coverage with Gemini 2.5 Flash structured-output and policy-cap coverage.
- Modify `server/tests/integration/test_analysis_integration.py`
  - Align route-level tests with "Gemini only, defaults on invalid output".
- Create `docs/gemini-policy-review.md`
  - Manual seeded-batch review checklist for future Gemini prompt iterations.

---

### Task 1: Make Gemini 2.5 Flash the only configured provider

**Files:**
- Modify: `server/config.py`
- Modify: `.env.example`
- Modify: `server/docker-compose.yml`
- Modify: `server/tests/conftest.py`

- [ ] **Step 1: Write the failing import expectations**

Update `server/tests/conftest.py` so tests seed only Gemini:

```python
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-longer-than-32-characters")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("AI_PROVIDER", "gemini")
os.environ.setdefault("BCRYPT_ROUNDS", "4")
```

Delete:

```python
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
```

- [ ] **Step 2: Run the AI unit tests before config edits**

Run:

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: existing Groq-specific tests remain and will be revised in later tasks.

- [ ] **Step 3: Update `server/config.py`**

Replace the provider constants with:

```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash:generateContent"
)

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
```

Delete:

```python
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
```

Keep the production Gemini key fail-fast check and delete the Groq fail-fast check.

- [ ] **Step 4: Update `.env.example`**

Use:

```env
# Backend AI provider settings
GEMINI_API_KEY=
AI_PROVIDER=gemini
```

Remove Groq-related lines.

- [ ] **Step 5: Update `server/docker-compose.yml`**

The backend service should pass:

```yaml
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - AI_PROVIDER=${AI_PROVIDER:-gemini}
```

Remove Groq-related environment lines.

- [ ] **Step 6: Re-run focused config/import coverage**

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: imports succeed; behavior-specific tests will be updated next.

- [ ] **Step 7: Commit**

```powershell
git add server/config.py .env.example server/docker-compose.yml server/tests/conftest.py
git commit -m "feat: standardize backend on gemini 2.5 flash"
```

---

### Task 2: Harden Gemini response format with structured output schema

**Files:**
- Modify: `server/services/ai_service.py`
- Modify: `server/tests/test_ai_service.py`

- [ ] **Step 1: Replace Groq tests with a structured-output payload test**

Add this test in `server/tests/test_ai_service.py`:

```python
async def test_gemini_request_uses_structured_output_schema(monkeypatch):
    captured: dict = {}

    class _CaptureClient(_MockAsyncClient):
        async def post(self, *_args, **kwargs):
            captured.update(kwargs["json"])
            return _MockHttpResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps({
                                            "classifications": [
                                                {
                                                    "file_id": "abc123",
                                                    "confidence": 0.4,
                                                    "category": "installer",
                                                    "reason": "structured",
                                                }
                                            ]
                                        })
                                    }
                                ]
                            }
                        }
                    ]
                }
            )

    monkeypatch.setattr(httpx, "AsyncClient", _CaptureClient(_MockHttpResponse({})))
    await ai_service._call_gemini("prompt")

    config = captured["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in config
    assert "classifications" in config["responseJsonSchema"]["properties"]
```

- [ ] **Step 2: Run the new test and confirm it fails**

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: FAIL because `responseJsonSchema` is not yet emitted.

- [ ] **Step 3: Add category constants and Gemini schema**

In `server/services/ai_service.py`, add:

```python
ALLOWED_CATEGORIES = {
    "document", "media", "installer", "cache", "temp", "archive",
    "backup", "database", "code", "config", "log", "other",
}

GEMINI_RESPONSE_SCHEMA = {
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
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "category": {"type": "string", "enum": sorted(ALLOWED_CATEGORIES)},
                    "reason": {"type": "string"},
                },
                "required": ["file_id", "confidence", "category", "reason"],
            },
        }
    },
    "required": ["classifications"],
}
```

- [ ] **Step 4: Update `_call_gemini()`**

Change `generationConfig` to:

```python
"generationConfig": {
    "responseMimeType": "application/json",
    "responseJsonSchema": GEMINI_RESPONSE_SCHEMA,
    "temperature": AI_TEMPERATURE,
},
```

- [ ] **Step 5: Run the focused test**

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: the structured-output request assertion passes.

- [ ] **Step 6: Commit**

```powershell
git add server/services/ai_service.py server/tests/test_ai_service.py
git commit -m "feat: request structured gemini classifications"
```

---

### Task 3: Rewrite the prompt around correct confidence semantics

**Files:**
- Modify: `server/services/ai_service.py`
- Modify: `server/tests/test_ai_service.py`

- [ ] **Step 1: Add prompt-content assertions**

Add a test that verifies the critical instructions exist:

```python
def test_system_prompt_defines_confidence_and_category_rules():
    assert "confidence = вероятность того, что файл безопасно удалить" in ai_service.SYSTEM_PROMPT
    assert "0.0 = удалять опасно" in ai_service.SYSTEM_PROMPT
    assert "1.0 = почти наверняка безопасно удалить" in ai_service.SYSTEM_PROMPT
    assert "Категория определяется типом файла, а не папкой" in ai_service.SYSTEM_PROMPT
```

- [ ] **Step 2: Run the test and confirm it fails**

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: FAIL because the current prompt does not contain the stricter wording.

- [ ] **Step 3: Update the system prompt**

Revise the prompt so it includes at least these exact semantic rules:

```text
confidence = вероятность того, что файл безопасно удалить.
0.0 = удалять опасно.
1.0 = почти наверняка безопасно удалить.
Возраст файла сам по себе НЕ является достаточным основанием для высокой confidence.
Категория определяется типом файла, а не папкой.
Расположение файла влияет на уверенность удаления, но не меняет category.
Desktop, Documents, Projects и .git — контексты повышенного риска.
```

Also narrow high-confidence examples and clarify that archives, backups, configs,
databases, code, personal media, and unknown files should default toward caution.

- [ ] **Step 4: Run the prompt test**

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/services/ai_service.py server/tests/test_ai_service.py
git commit -m "feat: harden gemini confidence prompt"
```

---

### Task 4: Reject unusable Gemini responses before applying policy caps

**Files:**
- Modify: `server/services/ai_service.py`
- Modify: `server/tests/test_ai_service.py`
- Modify: `server/tests/integration/test_analysis_integration.py`

- [ ] **Step 1: Add strict response-validation tests**

Add unit tests for:

```python
def test_provider_response_rejects_duplicate_file_ids():
    files = [{"file_id": "a"}, {"file_id": "b"}]
    items = [
        {"file_id": "a", "confidence": 0.2, "category": "other", "reason": "r"},
        {"file_id": "a", "confidence": 0.3, "category": "other", "reason": "r"},
    ]
    assert ai_service._provider_response_is_complete(files, items) is False


def test_provider_response_rejects_bad_category():
    files = [{"file_id": "a"}]
    items = [
        {"file_id": "a", "confidence": 0.2, "category": "mystery", "reason": "r"}
    ]
    assert ai_service._provider_response_is_complete(files, items) is False


def test_provider_response_rejects_empty_reason():
    files = [{"file_id": "a"}]
    items = [
        {"file_id": "a", "confidence": 0.2, "category": "other", "reason": ""}
    ]
    assert ai_service._provider_response_is_complete(files, items) is False
```

- [ ] **Step 2: Update the incomplete-response integration test**

Replace the old “fill missing IDs from partial AI output” expectation with:

```python
async def test_incomplete_gemini_response_returns_defaults(
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

- [ ] **Step 3: Run tests and confirm failures**

```powershell
cd server
pytest tests/test_ai_service.py tests/integration/test_analysis_integration.py -q
```

Expected: FAIL until strict validation and classify behavior are updated.

- [ ] **Step 4: Add `_provider_response_is_complete()`**

Implement:

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
        if str(item.get("category", "")) not in ALLOWED_CATEGORIES:
            return False
        if not str(item.get("reason", "")).strip():
            return False
        try:
            confidence = float(item["confidence"])
        except (KeyError, TypeError, ValueError):
            return False
        if not 0.0 <= confidence <= 1.0:
            return False
    return True
```

- [ ] **Step 5: Rewrite `classify_files()`**

Use:

```python
raw_response = await _call_gemini(user_prompt)
classifications = _parse_response(raw_response)
if not _provider_response_is_complete(files, classifications):
    raise ValueError("Gemini response is incomplete or invalid")
normalized = _validate_classifications(files, classifications)
return _apply_policy_caps(files, normalized)
```

Keep the existing exception path to `_default_classifications(files)`.

- [ ] **Step 6: Run the affected tests**

```powershell
cd server
pytest tests/test_ai_service.py tests/integration/test_analysis_integration.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/services/ai_service.py server/tests/test_ai_service.py server/tests/integration/test_analysis_integration.py
git commit -m "feat: reject unusable gemini classification batches"
```

---

### Task 5: Add deterministic policy caps for risky delete recommendations

**Files:**
- Modify: `server/services/ai_service.py`
- Modify: `server/tests/test_ai_service.py`

- [ ] **Step 1: Add failing unit tests for caps**

Add representative tests:

```python
def test_archive_in_documents_is_capped():
    files = [{
        "file_id": "a",
        "filename": "archive_5603.zip",
        "extension": ".zip",
        "parent_dir": "C:/Users/x/Documents",
    }]
    items = [{
        "file_id": "a",
        "confidence": 0.95,
        "category": "archive",
        "reason": "model",
    }]
    capped = ai_service._apply_policy_caps(files, items)
    assert capped[0]["confidence"] == 0.40


def test_backup_on_desktop_is_capped():
    files = [{
        "file_id": "a",
        "filename": "dump_4198.bak",
        "extension": ".bak",
        "parent_dir": "C:/Users/x/Desktop",
    }]
    items = [{
        "file_id": "a",
        "confidence": 0.90,
        "category": "backup",
        "reason": "model",
    }]
    capped = ai_service._apply_policy_caps(files, items)
    assert capped[0]["confidence"] == 0.40


def test_temp_file_in_documents_keeps_high_temp_confidence():
    files = [{
        "file_id": "a",
        "filename": "tempfile_5156.tmp",
        "extension": ".tmp",
        "parent_dir": "C:/Users/x/Documents",
    }]
    items = [{
        "file_id": "a",
        "confidence": 1.0,
        "category": "temp",
        "reason": "model",
    }]
    capped = ai_service._apply_policy_caps(files, items)
    assert capped[0]["confidence"] == 0.60
```

- [ ] **Step 2: Run focused tests and confirm they fail**

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: FAIL because `_apply_policy_caps()` does not exist.

- [ ] **Step 3: Add reusable cap helpers**

Implement:

```python
RISKY_DIR_MARKERS = ("desktop", "documents", "projects", "/.git", "\\.git")
PERSONAL_MEDIA_WORDS = ("wedding", "family", "birthday", "photo")
PROTECTED_DOC_WORDS = (
    "thesis", "diploma", "contract", "report", "project", "work",
    "диплом", "курсов", "договор", "проект", "работ",
)


def _lower_text(value: str) -> str:
    return value.casefold()


def _in_risky_dir(parent_dir: str) -> bool:
    normalized = _lower_text(parent_dir.replace("\\", "/"))
    return any(marker in normalized for marker in RISKY_DIR_MARKERS)
```

- [ ] **Step 4: Implement `_confidence_cap_for()`**

```python
def _confidence_cap_for(file_meta: dict, classification: dict) -> float:
    category = classification["category"]
    parent_dir = _lower_text(str(file_meta.get("parent_dir", "")))
    filename = _lower_text(str(file_meta.get("filename", "")))

    caps = [1.0]

    if _in_risky_dir(parent_dir):
        caps.append(0.60)

    if category == "document":
        caps.append(0.80)
        if any(word in filename for word in PROTECTED_DOC_WORDS):
            caps.append(0.35)
    elif category == "archive":
        caps.append(0.70)
        if _in_risky_dir(parent_dir):
            caps.append(0.40)
    elif category == "backup":
        if not any(marker in parent_dir for marker in ("temp", "cache", "logs")):
            caps.append(0.60)
        if _in_risky_dir(parent_dir):
            caps.append(0.40)
    elif category == "config":
        caps.append(0.40)
    elif category == "database":
        caps.append(0.30)
    elif category == "code":
        caps.append(0.30)
    elif category == "media":
        caps.append(0.30)
        if any(word in filename for word in PERSONAL_MEDIA_WORDS):
            caps.append(0.15)
    elif category == "other":
        caps.append(0.20)

    return min(caps)
```

- [ ] **Step 5: Implement `_apply_policy_caps()`**

```python
def _apply_policy_caps(
    original_files: list[dict],
    classifications: list[dict],
) -> list[dict]:
    files_by_id = {item["file_id"]: item for item in original_files}
    capped: list[dict] = []
    for classification in classifications:
        file_meta = files_by_id[classification["file_id"]]
        cap = _confidence_cap_for(file_meta, classification)
        confidence = min(float(classification["confidence"]), cap)
        capped.append({**classification, "confidence": confidence})
    return capped
```

- [ ] **Step 6: Run focused tests**

```powershell
cd server
pytest tests/test_ai_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/services/ai_service.py server/tests/test_ai_service.py
git commit -m "feat: cap risky gemini deletion confidence"
```

---

### Task 6: Add route-level coverage and manual Gemini review notes

**Files:**
- Modify: `server/tests/integration/test_analysis_integration.py`
- Create: `docs/gemini-policy-review.md`

- [ ] **Step 1: Add an integration test that proves capped scores reach the API response**

Add:

```python
async def test_policy_caps_are_visible_in_route_response(
    pg_client: AsyncClient,
    monkeypatch,
):
    import json as _json
    from services import ai_service

    token = await _register(pg_client, "policy_caps")
    payload = {
        "scan_id": "s-policy",
        "files": [
            {
                "file_id": "archive-docs",
                "filename": "archive_5603.zip",
                "extension": ".zip",
                "size_bytes": 100,
                "modified_at": "2023-01-01T00:00:00",
                "accessed_at": "2023-02-01T00:00:00",
                "parent_dir": "C:/Users/x/Documents",
            }
        ],
    }

    async def fake_gemini(_prompt: str) -> str:
        return _json.dumps({
            "classifications": [
                {
                    "file_id": "archive-docs",
                    "confidence": 0.95,
                    "category": "archive",
                    "reason": "model",
                }
            ]
        })

    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    response = await pg_client.post(
        "/api/analyze",
        headers=_auth(token),
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["classifications"][0]["confidence"] == 0.40
```

- [ ] **Step 2: Create `docs/gemini-policy-review.md`**

Use:

```markdown
# Gemini Policy Review Checklist

## Purpose

Use the seeded synthetic file batches to compare Gemini outputs before and after
prompt or policy-cap changes.

## Review Focus

- Did Gemini keep one classification per requested `file_id`?
- Did it preserve the allowed category set?
- Did policy caps reduce overconfident risky recommendations?
- Did risky cases stay conservative?
  - archives on Desktop / Documents / Projects
  - backups on Desktop / Documents / Projects
  - configs, databases, code, personal media
- Did obvious temp/installer/log cases remain actionable?

## Suggested Manual Batch

Reuse the existing seeded `200`-file batch generated from `server/tests/factories.py`
with `seed=501`.
```

- [ ] **Step 3: Run affected integration coverage**

```powershell
cd server
pytest tests/integration/test_analysis_integration.py -q
```

Expected: PASS.

- [ ] **Step 4: Force-add the markdown doc if the repo-wide ignore rule still excludes `*.md`**

```powershell
git add -f docs/gemini-policy-review.md
```

- [ ] **Step 5: Commit**

```powershell
git add server/tests/integration/test_analysis_integration.py
git commit -m "test: expose gemini policy caps through analyze route"
```

---

### Task 7: Run backend verification

**Files:**
- No new files unless verification finds issues that need correction.

- [ ] **Step 1: Run focused AI and route tests**

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

- [ ] **Step 3: Run the full backend suite**

```powershell
cd server
pytest -q
```

Expected: PASS, excluding only environment-specific tests already marked or documented by the repository.

- [ ] **Step 4: Run one manual Gemini seeded-batch review outside CI**

Generate or reuse the `seed=501`, `200`-file batch and inspect whether:

- structured output remains complete
- the revised prompt produces better raw confidence semantics
- backend caps would catch the remaining risky overconfidence

- [ ] **Step 5: Commit verification-driven fixes if any were required**

```powershell
git add <verification-fix-files>
git commit -m "test: stabilize gemini policy cap behavior"
```

---

## Self-Review

- Spec coverage:
  - Gemini 2.5 Flash only: Task 1.
  - Structured output: Task 2.
  - Prompt hardening: Task 3.
  - Reject malformed or incomplete provider output: Task 4.
  - Policy caps: Task 5.
  - Route-level cap visibility and manual review checklist: Task 6.
  - Verification: Task 7.
- Placeholder scan:
  - No `TBD`, `TODO`, or deferred implementation placeholders remain.
- Type consistency:
  - `GEMINI_RESPONSE_SCHEMA`, `_provider_response_is_complete()`,
    `_confidence_cap_for()`, `_apply_policy_caps()`, and `classify_files()`
    remain consistent throughout the plan.
