import json
import os
import tempfile
import unittest
from contextlib import closing

import httpx

from client.api_client import (
    ApiClientError,
    AuthSession,
    SmartCleanerApiClient,
    analyze_and_cache_files,
    sanitize_file_metadata,
)


class SmartCleanerApiClientTestCase(unittest.TestCase):
    def _client(self, handler):
        transport = httpx.MockTransport(handler)
        return SmartCleanerApiClient(
            base_url="http://backend.test",
            transport=transport,
            timeout_seconds=5,
        )

    def test_login_stores_bearer_session(self):
        seen = {}

        def handler(request):
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["headers"] = request.headers
            seen["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "user_id": "u1",
                    "username": "alice",
                    "access_token": "token-123",
                    "token_type": "bearer",
                },
            )

        client = self._client(handler)

        session = client.login("alice", "Password123")

        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["path"], "/api/auth/login")
        self.assertNotIn("ngrok-skip-browser-warning", seen["headers"])
        self.assertEqual(
            seen["payload"],
            {"username": "alice", "password": "Password123"},
        )
        self.assertEqual(session.access_token, "token-123")
        self.assertEqual(client.session, session)

    def test_register_stores_bearer_session(self):
        def handler(request):
            self.assertEqual(request.url.path, "/api/auth/register")
            return httpx.Response(
                201,
                json={
                    "user_id": "u2",
                    "username": "bob",
                    "access_token": "token-456",
                    "token_type": "bearer",
                },
            )

        client = self._client(handler)

        session = client.register("bob", "Password123")

        self.assertEqual(session.user_id, "u2")
        self.assertEqual(client.session.access_token, "token-456")

    def test_request_falls_back_to_next_backend_url(self):
        seen_hosts = []

        def handler(request):
            seen_hosts.append(request.url.host)
            if request.url.host == "offline.test":
                raise httpx.ConnectError("offline", request=request)
            return httpx.Response(
                200,
                json={
                    "user_id": "u1",
                    "username": "alice",
                    "access_token": "token-123",
                    "token_type": "bearer",
                },
            )

        client = SmartCleanerApiClient(
            base_urls=["https://offline.test", "https://online.test"],
            transport=httpx.MockTransport(handler),
            timeout_seconds=5,
        )

        session = client.login("alice", "Password123")

        self.assertEqual(session.access_token, "token-123")
        self.assertEqual(seen_hosts, ["offline.test", "online.test"])
        self.assertEqual(client.base_url, "https://online.test")

    def test_analyze_requires_authentication(self):
        client = self._client(lambda _request: httpx.Response(500))

        with self.assertRaises(ApiClientError) as ctx:
            client.analyze_files("scan-1", [{"file_id": "f1"}])

        self.assertIn("Not authenticated", str(ctx.exception))

    def test_analyze_sends_authorization_and_metadata_only(self):
        seen_payloads = []
        seen_headers = []

        def handler(request):
            seen_headers.append(request.headers)
            seen_payloads.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "scan_id": "scan-1",
                    "classifications": [
                        {
                            "file_id": "f1",
                            "confidence": 0.9,
                            "category": "installer",
                            "reason": "ok",
                        }
                    ],
                },
            )

        client = self._client(handler)
        client.set_session(AuthSession("u1", "alice", "token-secret"))

        result = client.analyze_files(
            "scan-1",
            [
                {
                    "file_id": "f1",
                    "path": "C:/Users/Alice/Downloads/setup.exe",
                    "filename": "setup.exe",
                    "extension": ".exe",
                    "size_bytes": 1024,
                    "modified_at": "2026-01-01T00:00:00",
                    "accessed_at": "2026-01-02T00:00:00",
                    "parent_dir": "C:/Users/Alice/Downloads",
                    "content": "must-not-leave-device",
                }
            ],
        )

        self.assertEqual(seen_headers[0]["authorization"], "Bearer token-secret")
        self.assertNotIn("ngrok-skip-browser-warning", seen_headers[0])
        payload_text = json.dumps(seen_payloads[0], ensure_ascii=False)
        self.assertNotIn("C:/Users/Alice", payload_text)
        self.assertNotIn("must-not-leave-device", payload_text)
        self.assertEqual(seen_payloads[0]["files"][0]["parent_dir"], "Downloads")
        self.assertEqual(result.classifications[0]["file_id"], "f1")

    def test_analyze_chunks_large_requests_into_demo_safe_batches(self):
        request_sizes = []

        def handler(request):
            payload = json.loads(request.content)
            request_sizes.append(len(payload["files"]))
            return httpx.Response(
                200,
                json={
                    "scan_id": payload["scan_id"],
                    "classifications": [
                        {
                            "file_id": f["file_id"],
                            "confidence": 0.8,
                            "category": "other",
                            "reason": "ok",
                        }
                        for f in payload["files"]
                    ],
                },
            )

        client = self._client(handler)
        client.set_session(AuthSession("u1", "alice", "token"))
        files = [
            {
                "file_id": f"f{i}",
                "filename": f"f{i}.tmp",
                "extension": ".tmp",
                "size_bytes": i,
                "modified_at": "2026-01-01T00:00:00",
                "accessed_at": "",
                "parent_dir": "Temp",
            }
            for i in range(241)
        ]

        result = client.analyze_files("scan-large", files)

        self.assertEqual(request_sizes, [80, 80, 80, 1])
        self.assertEqual(len(result.classifications), 241)

    def test_analyze_rejects_malformed_success_response(self):
        def handler(_request):
            return httpx.Response(200, json={"scan_id": "scan-1"})

        client = self._client(handler)
        client.set_session(AuthSession("u1", "alice", "token"))

        with self.assertRaises(ApiClientError) as ctx:
            client.analyze_files(
                "scan-1",
                [
                    {
                        "file_id": "f1",
                        "filename": "f1.tmp",
                        "size_bytes": 1,
                        "modified_at": "2026-01-01T00:00:00",
                    }
                ],
            )

        self.assertIn("missing classifications", str(ctx.exception))

    def test_http_error_message_does_not_include_password_or_token(self):
        def handler(_request):
            return httpx.Response(401, json={"detail": "Invalid username or password"})

        client = self._client(handler)

        with self.assertRaises(ApiClientError) as ctx:
            client.login("alice", "Password123")

        message = str(ctx.exception)
        self.assertNotIn("Password123", message)
        self.assertIn("Invalid username or password", message)

    def test_sanitize_file_metadata_uses_safe_defaults(self):
        result = sanitize_file_metadata({"file_id": "x", "filename": "a.txt"})

        self.assertEqual(
            result,
            {
                "file_id": "x",
                "filename": "a.txt",
                "extension": "",
                "size_bytes": 0,
                "modified_at": "",
                "accessed_at": "",
                "parent_dir": "",
            },
        )

    def test_analyze_and_cache_files_writes_sqlite_cache(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = os.path.join(tmp.name, "smartcleaner.db")

        from client.database.local_db import (
            get_deletion_excluded_file_ids,
            upsert_scanned_files,
        )

        scanned_file = {
            "file_id": "important",
            "path": "C:/Users/Alice/Documents/contract.pdf",
            "filename": "contract.pdf",
            "extension": ".pdf",
            "size_bytes": 2048,
            "created_at": "2026-01-01T00:00:00",
            "modified_at": "2026-01-02T00:00:00",
            "accessed_at": "2026-01-03T00:00:00",
            "parent_dir": "C:/Users/Alice/Documents",
            "disk_label": "C:",
        }
        upsert_scanned_files([scanned_file], db_path=db_path)

        def handler(request):
            payload = json.loads(request.content)
            self.assertNotIn("C:/Users/Alice", json.dumps(payload))
            return httpx.Response(
                200,
                json={
                    "scan_id": "scan-cache",
                    "classifications": [
                        {
                            "file_id": "important",
                            "confidence": 0.2,
                            "category": "document",
                            "reason": "Important document",
                        }
                    ],
                },
            )

        client = self._client(handler)
        client.set_session(AuthSession("u1", "alice", "token"))

        result = analyze_and_cache_files(
            client,
            "scan-cache",
            [scanned_file],
            db_path=db_path,
        )

        self.assertEqual(len(result.classifications), 1)
        self.assertEqual(
            get_deletion_excluded_file_ids(db_path=db_path),
            {"important"},
        )

    def test_analyze_and_cache_files_applies_local_risk_downgrade(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = os.path.join(tmp.name, "smartcleaner.db")

        from client.database.local_db import (
            connect,
            get_deletion_excluded_file_ids,
            upsert_scanned_files,
        )
        from client.safety import REVIEW_CONFIDENCE_CAP

        scanned_file = {
            "file_id": "diploma",
            "path": "C:/Users/Alice/Documents/diploma-final.pdf",
            "filename": "diploma-final.pdf",
            "extension": ".pdf",
            "size_bytes": 4096,
            "created_at": "2025-01-01T00:00:00",
            "modified_at": "2025-01-02T00:00:00",
            "accessed_at": "2025-01-03T00:00:00",
            "parent_dir": "C:/Users/Alice/Documents",
            "disk_label": "C:",
        }
        upsert_scanned_files([scanned_file], db_path=db_path)

        def handler(request):
            payload = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "scan_id": payload["scan_id"],
                    "classifications": [
                        {
                            "file_id": "diploma",
                            "confidence": 0.95,
                            "category": "document",
                            "reason": "Старый документ",
                        }
                    ],
                },
            )

        client = self._client(handler)
        client.set_session(AuthSession("u1", "alice", "token"))

        result = analyze_and_cache_files(
            client,
            "scan-risk",
            [scanned_file],
            db_path=db_path,
        )

        self.assertEqual(result.classifications[0]["confidence"], REVIEW_CONFIDENCE_CAP)
        self.assertEqual(
            get_deletion_excluded_file_ids(db_path=db_path),
            {"diploma"},
        )
        with closing(connect(db_path)) as conn:
            row = conn.execute(
                "SELECT confidence, reason FROM analysis_cache WHERE file_id = ?",
                ("diploma",),
            ).fetchone()
        self.assertEqual(row[0], REVIEW_CONFIDENCE_CAP)
        self.assertIn("Локальная защита", row[1])


if __name__ == "__main__":
    unittest.main()
