"""Unit tests for services.auth_service (bcrypt + JWT)."""

from datetime import datetime, timedelta, timezone

from jose import jwt

from config import JWT_ALGORITHM, JWT_SECRET
from services.auth_service import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_produces_non_plaintext(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_is_salted(self):
        # Same plaintext must yield different hashes (bcrypt salts).
        h1 = hash_password("secret123")
        h2 = hash_password("secret123")
        assert h1 != h2

    def test_verify_correct_password(self):
        hashed = hash_password("correcthorsebattery")
        assert verify_password("correcthorsebattery", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correcthorsebattery")
        assert verify_password("wrong", hashed) is False

    def test_verify_empty_string(self):
        hashed = hash_password("real_password")
        assert verify_password("", hashed) is False


class TestJWT:
    def test_token_round_trip(self):
        token = create_access_token("user-uuid-123")
        assert decode_token(token) == "user-uuid-123"

    def test_token_payload_contains_sub_and_exp(self):
        token = create_access_token("abc")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "abc"
        assert "exp" in payload

    def test_decode_invalid_token_returns_none(self):
        assert decode_token("not.a.jwt") is None

    def test_decode_tampered_token_returns_none(self):
        token = create_access_token("u1")
        tampered = token[:-4] + "XXXX"
        assert decode_token(tampered) is None

    def test_decode_wrong_secret_returns_none(self):
        expire = datetime.now(timezone.utc) + timedelta(minutes=5)
        token = jwt.encode(
            {"sub": "u1", "exp": expire},
            "different-secret",
            algorithm=JWT_ALGORITHM,
        )
        assert decode_token(token) is None

    def test_decode_expired_token_returns_none(self):
        expired = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = jwt.encode(
            {"sub": "u1", "exp": expired},
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        assert decode_token(token) is None

    def test_decode_token_missing_sub_returns_none(self):
        # jose's decode returns the payload; .get("sub") is None -> None.
        expire = datetime.now(timezone.utc) + timedelta(minutes=5)
        token = jwt.encode(
            {"exp": expire},
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        assert decode_token(token) is None
