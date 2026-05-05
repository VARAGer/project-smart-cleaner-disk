"""
Concurrency & race-condition tests.

These exercise Postgres-level guarantees: UNIQUE(username) under racing
inserts, parallel analysis requests, independent sessions per coroutine.
"""

import asyncio

from httpx import AsyncClient

from routers import analysis as analysis_router
from tests.factories import analysis_payload, user_batch


async def test_parallel_registrations_all_succeed(pg_client: AsyncClient):
    users = user_batch(seed=20, n=30)
    results = await asyncio.gather(
        *(pg_client.post("/api/auth/register", json=c) for c in users)
    )
    statuses = [r.status_code for r in results]
    assert statuses.count(201) == 30


async def test_racing_duplicate_registration(pg_client: AsyncClient):
    """
    20 concurrent POSTs with the same username — exactly one must win with
    201, the rest must land on clean 409. A 500 here would indicate the
    endpoint isn't catching DB-level UniqueViolation (TOCTOU fix in auth.py).
    """
    creds = {"username": "mass_racer", "password": "password_abc1"}
    responses = await asyncio.gather(
        *(pg_client.post("/api/auth/register", json=creds) for _ in range(20))
    )
    statuses = sorted(r.status_code for r in responses)
    assert statuses.count(201) == 1, f"Expected exactly one winner, got {statuses}"
    assert statuses.count(409) == 19, f"Expected 19 losers, got {statuses}"


async def test_parallel_logins_after_registration(pg_client: AsyncClient):
    users = user_batch(seed=21, n=20)
    for c in users:
        r = await pg_client.post("/api/auth/register", json=c)
        assert r.status_code == 201

    results = await asyncio.gather(
        *(pg_client.post("/api/auth/login", json=c) for c in users)
    )
    assert all(r.status_code == 200 for r in results)
    # Each login returns the user's own id.
    for c, r in zip(users, results):
        assert r.json()["username"] == c["username"]


async def test_parallel_analyze_requests(pg_client: AsyncClient, monkeypatch):
    async def fake_classify(files):
        await asyncio.sleep(0.01)  # simulate AI latency
        return [
            {"file_id": f["file_id"], "confidence": 0.5, "category": "other", "reason": "r"}
            for f in files
        ]

    monkeypatch.setattr(analysis_router, "classify_files", fake_classify)

    reg = await pg_client.post(
        "/api/auth/register",
        json={"username": "parallel_analyzer", "password": "password123"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payloads = [
        analysis_payload(seed=100 + i, file_count=10, scan_id=f"s-{i}")
        for i in range(15)
    ]
    responses = await asyncio.gather(
        *(pg_client.post("/api/analyze", headers=headers, json=p) for p in payloads)
    )

    assert all(r.status_code == 200 for r in responses)
    # Each response echoes its own scan_id — no response crossover.
    for p, r in zip(payloads, responses):
        assert r.json()["scan_id"] == p["scan_id"]
        assert len(r.json()["classifications"]) == 10
