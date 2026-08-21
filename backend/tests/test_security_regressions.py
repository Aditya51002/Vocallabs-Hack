import asyncio
import zipfile
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest

from api.routes import _build_docx, _pdf_text_stream
from config import parse_cors_origins
from core.orchestrator import Orchestrator
from core.schemas import ResearchQuery


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def set(self, key, value):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)


class FakeBus:
    def __init__(self):
        self._redis = FakeRedis()

    @staticmethod
    def channel_name(agent_type, session_id: str) -> str:
        value = agent_type.value if hasattr(agent_type, "value") else str(agent_type)
        return f"agent:{value}:{session_id}"

    async def publish(self, channel, message):
        return None


def test_cors_origins_reject_wildcards():
    with pytest.raises(ValueError):
        parse_cors_origins("*")
    with pytest.raises(ValueError):
        parse_cors_origins("https://*.example.com")


def test_cors_origins_parse_whitelist():
    assert parse_cors_origins(
        "http://localhost:3000, https://app.example.com/"
    ) == ["http://localhost:3000", "https://app.example.com"]


def test_pdf_export_escapes_control_and_pdf_special_characters():
    stream = _pdf_text_stream(["report %) ( \x00 \\ done"])

    assert b"\x00" not in stream
    assert b"\\045" in stream
    assert b"\\(" in stream
    assert b"\\)" in stream
    assert b"\\\\" in stream


def test_docx_export_removes_invalid_xml_control_characters():
    docx = _build_docx("ok\x00bad\x1ftext")

    with zipfile.ZipFile(BytesIO(docx)) as archive:
        document_xml = archive.read("word/document.xml")

    assert b"\x00" not in document_xml
    assert b"\x1f" not in document_xml
    assert b"ok bad text" in document_xml


@pytest.mark.asyncio
async def test_requeued_research_tasks_are_registered_before_publishing(monkeypatch):
    bus = FakeBus()
    orchestrator = Orchestrator(bus, SimpleNamespace(), SimpleNamespace())

    monkeypatch.setattr(orchestrator, "_ensure_agents_running", lambda: asyncio.sleep(0))
    monkeypatch.setattr(orchestrator, "_start_session_listeners", lambda session_id: None)
    monkeypatch.setattr(orchestrator, "_schedule_timeout", lambda session_id, task_id: None)

    query = ResearchQuery(user_query="test query", session_id=uuid4())
    session_id = await orchestrator.start_session(query)
    state = orchestrator._sessions[session_id]
    original_count = len(state.researcher_task_ids)
    state.analyst_task_id = str(uuid4())
    state.critic_task_id = str(uuid4())
    state.writer_task_id = str(uuid4())
    state.analyst_result = {"old": "analyst"}
    state.critic_result = {"old": "critic"}

    snapshots = []

    async def capture_publish(task, publish_session_id):
        snapshots.append(list(orchestrator._sessions[publish_session_id].researcher_task_ids))

    monkeypatch.setattr(orchestrator, "_publish_task", capture_publish)

    requeued = await orchestrator._requeue_research(session_id, ["gap one", "gap two"])

    assert requeued is True
    assert state.analyst_task_id is None
    assert state.critic_task_id is None
    assert state.writer_task_id is None
    assert state.analyst_result is None
    assert state.critic_result is None
    assert len(state.researcher_task_ids) == original_count + 2
    assert snapshots
    assert all(len(snapshot) == original_count + 2 for snapshot in snapshots)
