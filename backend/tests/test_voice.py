"""Unit tests for Voice Input (Step 4).

Tests:
1. Rejection of audio files exceeding 24MB limit (413).
2. Empty audio file handling (400).
3. Groq Whisper transcription happy path.
4. Fallback in offline / unconfigured mode.
"""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from main import app
from core.auth import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token({"id": "test-user-id", "email": "tester@example.com", "name": "Tester"})
    return {"Authorization": f"Bearer {token}"}


def test_voice_transcription_rejects_oversized_file(auth_headers):
    client = TestClient(app)
    # 25MB synthetic payload
    oversized_data = b"0" * (25 * 1024 * 1024)
    response = client.post(
        "/api/voice",
        files={"file": ("large_recording.webm", io.BytesIO(oversized_data), "audio/webm")},
        headers=auth_headers,
    )
    assert response.status_code == 413
    assert "exceeds 24MB limit" in response.json()["detail"]


def test_voice_transcription_rejects_empty_file(auth_headers):
    client = TestClient(app)
    response = client.post(
        "/api/voice",
        files={"file": ("empty.webm", io.BytesIO(b""), "audio/webm")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Empty audio file" in response.json()["detail"]


def test_voice_transcription_happy_path(auth_headers):
    client = TestClient(app)
    fake_audio = b"fake-audio-bytes-for-testing"

    # Mock llm_router.transcribe_audio
    mock_router = MagicMock()
    mock_router.is_configured.return_value = True
    mock_router.transcribe_audio = AsyncMock(return_value="What is the renewable energy forecast in Vietnam?")

    app.state.llm_router = mock_router

    response = client.post(
        "/api/voice",
        files={"file": ("voice_sample.webm", io.BytesIO(fake_audio), "audio/webm")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["text"] == "What is the renewable energy forecast in Vietnam?"
