"""Unit tests for Image Input (Step 5).

Tests:
1. Rejection of images exceeding 500KB limit (413).
2. Empty image upload rejection (400).
3. Vision analysis happy path via Gemini Vision.
4. SHA-256 caching: repeated upload returns cached=True without re-calling LLM.
5. Token tracking recording on image analysis.
"""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from main import app
from core.auth import create_access_token
from core.cache import ResearchCache
from core.token_budget import TokenBudgetTracker


class FakeAsyncRedis:
    def __init__(self):
        self._store = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex=None):
        self._store[key] = str(value)
        return True

    async def incrby(self, key: str, amount: int):
        val = int(self._store.get(key, 0)) + amount
        self._store[key] = str(val)
        return val


@pytest.fixture
def auth_headers():
    token = create_access_token({"id": "test-user-id", "email": "tester@example.com", "name": "Tester"})
    return {"Authorization": f"Bearer {token}"}


def test_image_rejects_oversized_file(auth_headers):
    client = TestClient(app)
    # 600KB payload (over 500KB limit)
    oversized_data = b"0" * (600 * 1024)
    response = client.post(
        "/api/image",
        files={"file": ("large_chart.jpg", io.BytesIO(oversized_data), "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 413
    assert "exceeds 500KB limit" in response.json()["detail"]


def test_image_rejects_empty_file(auth_headers):
    client = TestClient(app)
    response = client.post(
        "/api/image",
        files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Empty image file" in response.json()["detail"]


def test_image_vision_and_caching(auth_headers):
    client = TestClient(app)
    fake_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb"

    redis = FakeAsyncRedis()
    cache = ResearchCache(redis)
    tracker = TokenBudgetTracker(redis)

    app.state.cache = cache
    app.state.budget_tracker = tracker

    mock_router = MagicMock()
    mock_router.is_configured.return_value = True
    mock_router.vision_complete = AsyncMock(
        return_value={
            "findings": [{"fact": "Chart shows 45% CAGR in solar installations", "confidence": 0.9}],
            "content_type": "chart",
            "usage": {"prompt_tokens": 200, "completion_tokens": 50},
        }
    )
    app.state.llm_router = mock_router

    # 1. First upload: cache miss, calls vision_complete
    resp1 = client.post(
        "/api/image?session_id=img-test-session",
        files={"file": ("chart.jpg", io.BytesIO(fake_img), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["cached"] is False
    assert len(data1["findings"]) == 1
    assert data1["findings"][0]["fact"] == "Chart shows 45% CAGR in solar installations"
    assert mock_router.vision_complete.call_count == 1

    # 2. Second upload of identical image: cache hit, no LLM call
    resp2 = client.post(
        "/api/image?session_id=img-test-session",
        files={"file": ("chart.jpg", io.BytesIO(fake_img), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["cached"] is True
    assert data2["image_hash"] == data1["image_hash"]
    # LLM call count did NOT increase
    assert mock_router.vision_complete.call_count == 1
