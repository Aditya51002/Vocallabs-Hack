"""Tests for user registration, authentication, JWT tokens, and security rules."""

import pytest
from fastapi.testclient import TestClient

from core.auth import create_access_token, decode_access_token, hash_password, verify_password
from main import app


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def hset(self, name, mapping=None, **kwargs):
        if name not in self.store:
            self.store[name] = {}
        if mapping:
            self.store[name].update(mapping)
        if kwargs:
            self.store[name].update(kwargs)
        return len(mapping or kwargs)

    async def hgetall(self, name):
        return self.store.get(name, {})

    async def incr(self, key):
        val = int(self.store.get(key, 0)) + 1
        self.store[key] = str(val)
        return val

    async def expire(self, key, seconds):
        return True


@pytest.fixture
def mock_app_redis(monkeypatch):
    fake_redis = FakeRedis()
    app.state.redis = fake_redis
    return fake_redis


def test_password_hashing():
    pwd = "SecretPassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_creation_and_decoding():
    user = {"id": "usr_12345", "email": "test@example.com", "name": "Test User"}
    token = create_access_token(user)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "usr_12345"
    assert decoded["email"] == "test@example.com"
    assert decoded["name"] == "Test User"


def test_garbage_jwt_returns_none():
    assert decode_access_token("invalid.garbage.token") is None


@pytest.mark.asyncio
async def test_signup_login_and_me_flow(mock_app_redis):
    client = TestClient(app)

    # 1. Signup user
    signup_payload = {
        "email": "user@example.com",
        "name": "Jane Doe",
        "password": "securepassword123",
    }
    res = client.post("/api/auth/signup", json=signup_payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "user@example.com"
    assert data["user"]["name"] == "Jane Doe"
    token = data["access_token"]

    # 2. Duplicate signup should return 409
    res_dup = client.post("/api/auth/signup", json=signup_payload)
    assert res_dup.status_code == 409
    assert res_dup.json()["detail"] == "Email is already registered."

    # 3. Login with correct credentials
    login_payload = {"email": "user@example.com", "password": "securepassword123"}
    res_login = client.post("/api/auth/login", json=login_payload)
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()

    # 4. Login with wrong password should return 401
    res_bad = client.post("/api/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert res_bad.status_code == 401

    # 5. Get current user via /api/auth/me with Bearer token
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["email"] == "user@example.com"
    assert me_data["name"] == "Jane Doe"

    # 6. Get current user with invalid token should return 401
    res_bad_me = client.get("/api/auth/me", headers={"Authorization": "Bearer badtoken"})
    assert res_bad_me.status_code == 401
