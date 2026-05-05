"""
Edge-case & fuzzing tests focused on reliability.

These exist to catch regressions when someone loosens validation or changes
auth handling. A failure here usually means the API accepted something it
shouldn't have.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt

from config import JWT_ALGORITHM, JWT_SECRET
from routers import analysis as analysis_router
from tests.factories import analysis_payload, file_batch


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _token(client: AsyncClient, username: str = "edge_u") -> str:
    response = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "password1234"},
    )
    return response.json()["access_token"]


def _stub_ai(monkeypatch):
    async def fake(files):
        return [
            {"file_id": f["file_id"], "confidence": 0.5, "category": "other", "reason": "r"}
            for f in files
        ]

    monkeypatch.setattr(analysis_router, "classify_files", fake)


# ============================================================
# Auth input validation
# ============================================================

@pytest.mark.parametrize(
    "bad",
    [
        {"username": "", "password": "password1234"},
        {"username": "a", "password": "password1234"},   # < 3
        {"username": "ab", "password": "password1234"},  # < 3
        {"username": "x" * 51, "password": "password1234"},  # > 50
        {"username": "has space", "password": "password1234"},
        {"username": "has!bang", "password": "password1234"},
        # Note: `str.isalnum()` accepts Cyrillic letters, so "валидный" is
        # *accepted* by the spec's validator — we don't include it here.
        {"username": "ok_user", "password": "short1"},        # < 10
        {"username": "ok_user", "password": "abcdefghij"},    # >=10 but no digit
        {"username": "ok_user", "password": "1234567890"},    # >=10 but no letter
        {"username": "ok_user", "password": "x1" + "y" * 127},  # > 128
    ],
)
async def test_register_rejects_invalid_credentials(
    pg_client: AsyncClient, bad: dict
):
    response = await pg_client.post("/api/auth/register", json=bad)
    assert response.status_code == 422, bad


@pytest.mark.parametrize(
    "ok",
    [
        {"username": "abc", "password": "abcdefghi1"},       # lower bounds (10 chars)
        {"username": "a" * 50, "password": "x" * 127 + "1"},  # upper bounds (128 chars)
        {"username": "with_under_score", "password": "Mixed123_pass!"},
        {"username": "123digits", "password": "onlydigits0123"},
    ],
)
async def test_register_accepts_boundary_credentials(
    pg_client: AsyncClient, ok: dict
):
    response = await pg_client.post("/api/auth/register", json=ok)
    assert response.status_code == 201, ok


# ============================================================
# JWT edge cases
# ============================================================

@pytest.mark.parametrize(
    "header",
    [
        "",                                # no header at all
        "Bearer",                          # missing value
        "Bearer ",                         # empty token
        "Basic dXNlcjpwYXNz",              # wrong scheme
        "Bearer not.a.jwt",
        "Bearer a.b.c",                    # malformed
    ],
)
async def test_analyze_rejects_bad_auth_header(
    pg_client: AsyncClient, header: str
):
    payload = {"scan_id": "s", "files": file_batch(seed=30, n=1)}
    headers = {"Authorization": header} if header else {}
    response = await pg_client.post("/api/analyze", headers=headers, json=payload)
    assert response.status_code in (401, 403)


async def test_analyze_expired_jwt_is_rejected(pg_client: AsyncClient):
    expired = jwt.encode(
        {
            "sub": "anything",
            "exp": datetime.now(timezone.utc) - timedelta(days=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    payload = {"scan_id": "s", "files": file_batch(seed=31, n=1)}
    response = await pg_client.post(
        "/api/analyze", headers=_auth(expired), json=payload
    )
    assert response.status_code == 401


async def test_analyze_jwt_signed_with_wrong_secret_is_rejected(pg_client: AsyncClient):
    foreign = jwt.encode(
        {
            "sub": "whoever",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "different-secret-entirely",
        algorithm=JWT_ALGORITHM,
    )
    payload = {"scan_id": "s", "files": file_batch(seed=32, n=1)}
    response = await pg_client.post(
        "/api/analyze", headers=_auth(foreign), json=payload
    )
    assert response.status_code == 401


async def test_analyze_with_none_algorithm_attack_is_rejected(pg_client: AsyncClient):
    """
    Classic JWT vuln: token signed with alg=none. python-jose rejects this
    by default because we pin `algorithms=[HS256]` in decode_token, but we
    assert it here to prevent regressions.
    """
    # python-jose refuses to encode with 'none' out of the box, so we
    # build the token manually.
    import base64
    import json

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(
        json.dumps({"sub": "attacker", "exp": 9999999999}).encode()
    ).rstrip(b"=").decode()
    malicious = f"{header}.{body}."

    payload = {"scan_id": "s", "files": file_batch(seed=33, n=1)}
    response = await pg_client.post(
        "/api/analyze", headers=_auth(malicious), json=payload
    )
    assert response.status_code == 401


# ============================================================
# Analysis payload validation
# ============================================================

async def test_analyze_rejects_empty_file_list(pg_client: AsyncClient):
    token = await _token(pg_client, "empty_files")
    response = await pg_client.post(
        "/api/analyze",
        headers=_auth(token),
        json={"scan_id": "s", "files": []},
    )
    assert response.status_code == 422


async def test_analyze_rejects_missing_required_fields(pg_client: AsyncClient):
    token = await _token(pg_client, "missing_fields")
    bad_file = {"file_id": "abc", "filename": "x.txt"}  # missing size/date
    response = await pg_client.post(
        "/api/analyze",
        headers=_auth(token),
        json={"scan_id": "s", "files": [bad_file]},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "override",
    [
        {"size_bytes": -1},                      # negative
        {"file_id": ""},                         # empty
        {"file_id": "x" * 21},                   # > max_length=20
        {"filename": "x" * 501},                 # > max_length=500
        {"extension": "x" * 21},                 # > max_length=20
        {"parent_dir": "x" * 1001},              # > max_length=1000
    ],
)
async def test_analyze_per_file_field_limits(
    pg_client: AsyncClient, override: dict, monkeypatch
):
    _stub_ai(monkeypatch)
    token = await _token(pg_client, f"field_limit_{abs(hash(str(override))) % 10_000}")
    base = file_batch(seed=40, n=1)[0]
    base.update(override)
    response = await pg_client.post(
        "/api/analyze",
        headers=_auth(token),
        json={"scan_id": "s", "files": [base]},
    )
    assert response.status_code == 422, override


async def test_analyze_allows_missing_optional_accessed_at(
    pg_client: AsyncClient, monkeypatch
):
    _stub_ai(monkeypatch)
    token = await _token(pg_client, "no_accessed_at")
    payload = {
        "scan_id": "s",
        "files": [
            {
                "file_id": "abc123",
                "filename": "test.txt",
                "extension": ".txt",
                "size_bytes": 10,
                "modified_at": "2024-01-01T00:00:00",
                "parent_dir": "C:/x",
            }
        ],
    }
    response = await pg_client.post(
        "/api/analyze", headers=_auth(token), json=payload
    )
    assert response.status_code == 200


# ============================================================
# Sensitive data leakage
# ============================================================

async def test_login_error_does_not_leak_whether_user_exists(pg_client: AsyncClient):
    """Both 'unknown user' and 'wrong password' must return the same body."""
    await pg_client.post(
        "/api/auth/register",
        json={"username": "exists", "password": "correctpw1"},
    )
    unknown = await pg_client.post(
        "/api/auth/login",
        json={"username": "ghost_user", "password": "whatever12"},
    )
    wrongpw = await pg_client.post(
        "/api/auth/login",
        json={"username": "exists", "password": "wrongpassword1"},
    )
    assert unknown.status_code == wrongpw.status_code == 401
    assert unknown.json() == wrongpw.json()


async def test_password_hash_never_appears_in_responses(pg_client: AsyncClient):
    reg = await pg_client.post(
        "/api/auth/register",
        json={"username": "secret_seeker", "password": "myRealPass123"},
    )
    text = reg.text
    assert "myRealPass123" not in text
    assert "password_hash" not in text
    assert "$2b$" not in text and "$2a$" not in text


# ============================================================
# SQL-injection hardening
# ============================================================

async def test_direct_sql_parameterization_neutralizes_injection(pg_session):
    """
    Proves SQLAlchemy text() parameterization (what the router uses via
    select()) treats injection payloads as literal values, not SQL.
    Any future route that bypasses ORM should do the same.
    """
    from sqlalchemy import text

    malicious = "'; DROP TABLE users; --"
    # If parameterization leaked, this would DROP the table. Instead the
    # string is passed as a bind parameter and treated as a literal.
    result = await pg_session.execute(
        text("SELECT :payload AS x"), {"payload": malicious}
    )
    assert result.scalar_one() == malicious

    # Table still exists.
    check = await pg_session.execute(
        text("SELECT count(*) FROM information_schema.tables WHERE table_name='users'")
    )
    assert check.scalar_one() == 1


async def test_sql_injection_attempt_in_username(pg_client: AsyncClient):
    """
    Parameter binding via SQLAlchemy's select() should neutralize injection.
    We verify by checking the server still responds correctly *and* the
    users table is not dropped.
    """
    payload = {
        "username": "robert",
        "password": "valid_password1",
    }
    await pg_client.post("/api/auth/register", json=payload)

    # An injection attempt that would be catastrophic with string concat.
    malicious_login = {
        "username": "robert'; DROP TABLE users; --",
        "password": "anything_goes1",
    }
    response = await pg_client.post("/api/auth/login", json=malicious_login)
    # The Pydantic validator should reject the non-alphanumeric username
    # (422). If somehow it reached the DB layer, it would 401 (no such user)
    # but NEVER drop the table.
    assert response.status_code in (401, 422)

    # Table is still there: legitimate user can still log in.
    ok = await pg_client.post("/api/auth/login", json=payload)
    assert ok.status_code == 200
