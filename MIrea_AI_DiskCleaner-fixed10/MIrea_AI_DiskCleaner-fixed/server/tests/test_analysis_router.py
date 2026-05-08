"""
Functional tests for POST /api/analyze.

The AI provider is stubbed at the module level (patch `classify_files`)
so no outbound HTTP is made.
"""

from httpx import AsyncClient

from routers import analysis as analysis_router


def _file_payload(file_id: str, filename: str = "test.txt") -> dict:
    return {
        "file_id": file_id,
        "filename": filename,
        "extension": ".txt",
        "size_bytes": 1024,
        "modified_at": "2024-01-01T00:00:00",
        "accessed_at": None,
        "parent_dir": "C:/Users/x",
    }


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAnalyzeAuth:
    async def test_missing_token_returns_401(self, client: AsyncClient):
        # 401 is the correct HTTP semantic for missing credentials (RFC 7235).
        response = await client.post(
            "/api/analyze",
            json={"scan_id": "s1", "files": [_file_payload("a")]},
        )
        assert response.status_code == 401

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/api/analyze",
            headers=_auth_headers("invalid.token.here"),
            json={"scan_id": "s1", "files": [_file_payload("a")]},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"


class TestAnalyzeHappyPath:
    async def test_echoes_scan_id_and_returns_classifications(
        self, client: AsyncClient, registered_user: dict, monkeypatch
    ):
        async def fake_classify(files):
            return [
                {
                    "file_id": f["file_id"],
                    "confidence": 0.9,
                    "category": "installer",
                    "reason": "mocked",
                }
                for f in files
            ]

        monkeypatch.setattr(analysis_router, "classify_files", fake_classify)

        response = await client.post(
            "/api/analyze",
            headers=_auth_headers(registered_user["access_token"]),
            json={
                "scan_id": "scan-xyz",
                "files": [_file_payload("id1"), _file_payload("id2")],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["scan_id"] == "scan-xyz"
        assert len(body["classifications"]) == 2
        ids = {c["file_id"] for c in body["classifications"]}
        assert ids == {"id1", "id2"}
        for c in body["classifications"]:
            assert c["category"] == "installer"
            assert c["confidence"] == 0.9

    async def test_ai_service_receives_all_metadata_fields(
        self, client: AsyncClient, registered_user: dict, monkeypatch
    ):
        captured: list[dict] = []

        async def fake_classify(files):
            captured.extend(files)
            return [
                {
                    "file_id": f["file_id"],
                    "confidence": 0.5,
                    "category": "other",
                    "reason": "r",
                }
                for f in files
            ]

        monkeypatch.setattr(analysis_router, "classify_files", fake_classify)

        await client.post(
            "/api/analyze",
            headers=_auth_headers(registered_user["access_token"]),
            json={
                "scan_id": "s",
                "files": [_file_payload("aaa", filename="cool_file.pdf")],
            },
        )

        assert len(captured) == 1
        f = captured[0]
        assert f["file_id"] == "aaa"
        assert f["filename"] == "cool_file.pdf"
        assert f["extension"] == ".txt"
        assert f["size_bytes"] == 1024
        # `accessed_at: None` from client is converted to empty string.
        assert f["accessed_at"] == ""
        assert f["parent_dir"] == "C:/Users/x"


class TestAnalyzeValidation:
    async def test_empty_files_returns_422(
        self, client: AsyncClient, registered_user: dict
    ):
        response = await client.post(
            "/api/analyze",
            headers=_auth_headers(registered_user["access_token"]),
            json={"scan_id": "s", "files": []},
        )
        assert response.status_code == 422

    async def test_over_200_files_returns_422(
        self, client: AsyncClient, registered_user: dict
    ):
        files = [_file_payload(f"id{i}") for i in range(201)]
        response = await client.post(
            "/api/analyze",
            headers=_auth_headers(registered_user["access_token"]),
            json={"scan_id": "s", "files": files},
        )
        assert response.status_code == 422

    async def test_exactly_200_files_accepted(
        self, client: AsyncClient, registered_user: dict, monkeypatch
    ):
        async def fake_classify(files):
            return [
                {
                    "file_id": f["file_id"],
                    "confidence": 0.5,
                    "category": "other",
                    "reason": "r",
                }
                for f in files
            ]

        monkeypatch.setattr(analysis_router, "classify_files", fake_classify)

        files = [_file_payload(f"id{i}") for i in range(200)]
        response = await client.post(
            "/api/analyze",
            headers=_auth_headers(registered_user["access_token"]),
            json={"scan_id": "s", "files": files},
        )
        assert response.status_code == 200
        assert len(response.json()["classifications"]) == 200

    async def test_negative_size_returns_422(
        self, client: AsyncClient, registered_user: dict
    ):
        bad = _file_payload("a")
        bad["size_bytes"] = -1
        response = await client.post(
            "/api/analyze",
            headers=_auth_headers(registered_user["access_token"]),
            json={"scan_id": "s", "files": [bad]},
        )
        assert response.status_code == 422

    async def test_file_id_too_long_returns_422(
        self, client: AsyncClient, registered_user: dict
    ):
        bad = _file_payload("x" * 21)  # max_length=20 in schema
        response = await client.post(
            "/api/analyze",
            headers=_auth_headers(registered_user["access_token"]),
            json={"scan_id": "s", "files": [bad]},
        )
        assert response.status_code == 422


class TestAnalyzeErrorRecovery:
    async def test_ai_exception_still_returns_200_with_defaults(
        self, client: AsyncClient, registered_user: dict, monkeypatch
    ):
        """Even if the AI service errors internally, the endpoint returns 200."""

        async def exploding(files):
            # This simulates classify_files returning defaults on its own.
            # (classify_files catches all exceptions and returns defaults.)
            return [
                {
                    "file_id": f["file_id"],
                    "confidence": 0.5,
                    "category": "other",
                    "reason": "Сервис анализа временно недоступен",
                }
                for f in files
            ]

        monkeypatch.setattr(analysis_router, "classify_files", exploding)

        response = await client.post(
            "/api/analyze",
            headers=_auth_headers(registered_user["access_token"]),
            json={"scan_id": "s", "files": [_file_payload("a")]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["classifications"][0]["confidence"] == 0.5
        assert "недоступен" in body["classifications"][0]["reason"]
