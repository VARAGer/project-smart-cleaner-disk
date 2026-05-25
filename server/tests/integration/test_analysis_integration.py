"""
End-to-end analysis flow against Postgres-backed auth with synthetic file
batches. AI calls are stubbed — we verify the service plumbing, not the LLM.
"""

from httpx import AsyncClient

from routers import analysis as analysis_router
from tests.factories import analysis_payload, file_batch


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, username: str = "scan_owner") -> str:
    response = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "scanpassword1"},
    )
    return response.json()["access_token"]


def _stub_ai(monkeypatch, confidence: float = 0.75, category: str = "other"):
    async def fake_classify(files):
        return [
            {
                "file_id": f["file_id"],
                "confidence": confidence,
                "category": category,
                "reason": "stubbed",
            }
            for f in files
        ]

    monkeypatch.setattr(analysis_router, "classify_files", fake_classify)


async def test_full_round_trip_small_batch(pg_client: AsyncClient, monkeypatch):
    _stub_ai(monkeypatch, confidence=0.9, category="installer")
    token = await _register(pg_client, "round_trip_small")

    payload = analysis_payload(seed=10, file_count=5, scan_id="s-small")
    response = await pg_client.post(
        "/api/analyze", headers=_auth(token), json=payload
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == "s-small"
    assert len(body["classifications"]) == 5
    assert all(c["category"] == "installer" for c in body["classifications"])


async def test_analyze_200_file_batch(pg_client: AsyncClient, monkeypatch):
    _stub_ai(monkeypatch)
    token = await _register(pg_client, "batch_200")

    payload = analysis_payload(seed=11, file_count=200, scan_id="s-200")
    response = await pg_client.post(
        "/api/analyze", headers=_auth(token), json=payload
    )
    assert response.status_code == 200
    assert len(response.json()["classifications"]) == 200


async def test_analyze_201_file_batch_rejected(pg_client: AsyncClient, monkeypatch):
    _stub_ai(monkeypatch)
    token = await _register(pg_client, "batch_201")

    # Build 201 unique files — factory already dedupes.
    files = file_batch(seed=12, n=201)
    payload = {"scan_id": "s-201", "files": files}
    response = await pg_client.post(
        "/api/analyze", headers=_auth(token), json=payload
    )
    assert response.status_code == 422


async def test_missing_file_ids_filled_with_defaults(pg_client: AsyncClient, monkeypatch):
    """If the AI drops files from the response, server adds defaults.

    This patches the LOW-level `_call_gemini` call so the real
    `classify_files` + `_validate_classifications` runs end-to-end —
    patching `classify_files` itself would bypass the validation we're
    actually testing.
    """
    import json as _json

    from services import ai_service

    async def fake_gemini(user_prompt: str) -> str:
        # Extract the files from the prompt and classify only the first half.
        # Prompt format is "text\n\n...\n\n<json array>".
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

    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    token = await _register(pg_client, "partial_resp")

    payload = analysis_payload(seed=13, file_count=20, scan_id="s-partial")
    response = await pg_client.post(
        "/api/analyze", headers=_auth(token), json=payload
    )
    assert response.status_code == 200
    classifications = response.json()["classifications"]
    assert len(classifications) == 20
    # Every requested file_id must appear in the response.
    req_ids = {f["file_id"] for f in payload["files"]}
    resp_ids = {c["file_id"] for c in classifications}
    assert req_ids == resp_ids


async def test_ai_service_sees_correct_metadata(pg_client: AsyncClient, monkeypatch):
    captured: list[list[dict]] = []

    async def capturing_classify(files):
        captured.append(files)
        return [
            {"file_id": f["file_id"], "confidence": 0.5, "category": "other", "reason": "r"}
            for f in files
        ]

    monkeypatch.setattr(analysis_router, "classify_files", capturing_classify)
    token = await _register(pg_client, "capture_meta")

    payload = analysis_payload(seed=14, file_count=7, scan_id="s-capture")
    await pg_client.post("/api/analyze", headers=_auth(token), json=payload)

    assert len(captured) == 1
    sent = captured[0]
    assert len(sent) == 7
    for f in sent:
        assert set(f.keys()) >= {
            "file_id", "filename", "extension", "size_bytes",
            "modified_at", "accessed_at", "parent_dir",
        }
