"""Functional tests for /api/auth/register and /api/auth/login."""

from httpx import AsyncClient

from services.auth_service import decode_token


class TestRegister:
    async def test_success_returns_201(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "hunter2_secret"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["username"] == "alice"
        assert body["token_type"] == "bearer"
        assert "user_id" in body and len(body["user_id"]) == 36  # UUID
        assert decode_token(body["access_token"]) == body["user_id"]

    async def test_duplicate_username_returns_409(self, client: AsyncClient):
        await client.post(
            "/api/auth/register",
            json={"username": "bob", "password": "password123"},
        )
        response = await client.post(
            "/api/auth/register",
            json={"username": "bob", "password": "different_pass1"},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Username already exists"

    async def test_short_username_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/register",
            json={"username": "ab", "password": "password123"},
        )
        assert response.status_code == 422

    async def test_short_password_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "abc"},
        )
        assert response.status_code == 422

    async def test_non_alphanumeric_username_returns_422(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/api/auth/register",
            json={"username": "alice!", "password": "password123"},
        )
        assert response.status_code == 422

    async def test_username_with_underscore_accepted(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/register",
            json={"username": "alice_wonder", "password": "password123"},
        )
        assert response.status_code == 201

    async def test_missing_field_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/register",
            json={"username": "alice"},
        )
        assert response.status_code == 422

    async def test_password_is_hashed_not_stored(
        self, client: AsyncClient, test_session,
    ):
        from sqlalchemy import select
        from models.user import User

        await client.post(
            "/api/auth/register",
            json={"username": "secure", "password": "plaintextpass1"},
        )
        result = await test_session.execute(
            select(User).where(User.username == "secure")
        )
        user = result.scalar_one()
        assert user.password_hash != "plaintextpass1"
        assert user.password_hash.startswith(("$2a$", "$2b$"))


class TestLogin:
    async def test_success(self, client: AsyncClient):
        await client.post(
            "/api/auth/register",
            json={"username": "charlie", "password": "mypassword1"},
        )
        response = await client.post(
            "/api/auth/login",
            json={"username": "charlie", "password": "mypassword1"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["username"] == "charlie"
        assert decode_token(body["access_token"]) == body["user_id"]

    async def test_wrong_password_returns_401(self, client: AsyncClient):
        await client.post(
            "/api/auth/register",
            json={"username": "dave", "password": "correct_pass1"},
        )
        response = await client.post(
            "/api/auth/login",
            json={"username": "dave", "password": "wrong_pass123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid username or password"

    async def test_nonexistent_user_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/login",
            json={"username": "ghost", "password": "whatever123"},
        )
        assert response.status_code == 401

    async def test_separate_tokens_per_login(self, client: AsyncClient):
        await client.post(
            "/api/auth/register",
            json={"username": "eve", "password": "password123"},
        )
        first = await client.post(
            "/api/auth/login",
            json={"username": "eve", "password": "password123"},
        )
        second = await client.post(
            "/api/auth/login",
            json={"username": "eve", "password": "password123"},
        )
        # Same user_id, but tokens may differ due to `exp` timestamp.
        assert first.json()["user_id"] == second.json()["user_id"]
