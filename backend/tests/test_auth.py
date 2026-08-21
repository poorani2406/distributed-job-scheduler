# backend/tests/test_auth.py
import pytest

pytestmark = pytest.mark.asyncio


async def test_register_and_login(client):
    r = await client.post("/api/auth/register", json={
        "email": "a@a.com", "password": "password123", "org_name": "Acme"
    })
    assert r.status_code == 200
    assert "access_token" in r.json()

    r = await client.post("/api/auth/login", data={"username": "a@a.com", "password": "password123"})
    assert r.status_code == 200


async def test_duplicate_email_rejected(client):
    payload = {"email": "dup@a.com", "password": "password123", "org_name": "Acme"}
    await client.post("/api/auth/register", json=payload)
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 400


async def test_me_requires_auth(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401