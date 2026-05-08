"""End-to-end auth flow against real Postgres with synthetic user data."""

from httpx import AsyncClient

from services.auth_service import decode_token
from tests.factories import user_batch


async def test_register_100_unique_users(pg_client: AsyncClient):
    """Registering many distinct users succeeds without collision."""
    users = user_batch(seed=1, n=100)
    for creds in users:
        response = await pg_client.post("/api/auth/register", json=creds)
        assert response.status_code == 201, (creds, response.text)
        body = response.json()
        assert decode_token(body["access_token"]) == body["user_id"]


async def test_register_login_round_trip_for_batch(pg_client: AsyncClient):
    users = user_batch(seed=2, n=25)
    for creds in users:
        reg = await pg_client.post("/api/auth/register", json=creds)
        assert reg.status_code == 201, creds
    for creds in users:
        login = await pg_client.post("/api/auth/login", json=creds)
        assert login.status_code == 200, creds


async def test_duplicate_registration_is_rejected(pg_client: AsyncClient):
    creds = {"username": "twin", "password": "password_xyz1"}
    first = await pg_client.post("/api/auth/register", json=creds)
    assert first.status_code == 201
    second = await pg_client.post("/api/auth/register", json=creds)
    assert second.status_code == 409


async def test_wrong_password_per_user(pg_client: AsyncClient):
    users = user_batch(seed=3, n=10)
    for creds in users:
        await pg_client.post("/api/auth/register", json=creds)

    for creds in users:
        bad = {"username": creds["username"], "password": creds["password"] + "x"}
        response = await pg_client.post("/api/auth/login", json=bad)
        assert response.status_code == 401, bad


async def test_cross_user_password_does_not_authenticate(pg_client: AsyncClient):
    """User A's password must not work for User B (defence against hash collisions)."""
    a = {"username": "alpha", "password": "AlphaPassword1"}
    b = {"username": "beta", "password": "BetaPassword2"}
    await pg_client.post("/api/auth/register", json=a)
    await pg_client.post("/api/auth/register", json=b)

    swapped = {"username": a["username"], "password": b["password"]}
    response = await pg_client.post("/api/auth/login", json=swapped)
    assert response.status_code == 401


async def test_token_from_one_user_decodes_to_their_id(pg_client: AsyncClient):
    reg = await pg_client.post(
        "/api/auth/register",
        json={"username": "token_owner", "password": "password_aaa1"},
    )
    assert decode_token(reg.json()["access_token"]) == reg.json()["user_id"]
