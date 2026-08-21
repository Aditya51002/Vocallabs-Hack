"""Unit tests for Step 2 Token Governance: TokenBudgetTracker, ResearchCache, and Model Right-Sizing."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from core.cache import ResearchCache
from core.token_budget import TokenBudgetTracker
from core.llm_router import LLMRouter, TokenUsage, LLMResult
from core.types import AgentType, MessageType, TaskStatus
from core.schemas import AgentResult, TaskMessage
from core.orchestrator import Orchestrator, SessionState
from core.task_dag import TaskDAG


class FakeAsyncRedis:
    """In-memory async Redis double for testing."""

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

    async def delete(self, key: str):
        return self._store.pop(key, None) is not None

    async def keys(self, pattern: str):
        import fnmatch
        return [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]


@pytest.mark.asyncio
async def test_token_budget_tracker_records_and_checks_limits():
    redis = FakeAsyncRedis()
    tracker = TokenBudgetTracker(redis, soft_limit=100, hard_limit=200)

    session_id = "test-session"
    assert await tracker.get_total(session_id) == 0
    assert not await tracker.is_over_soft_limit(session_id)
    assert not await tracker.is_over_hard_limit(session_id)

    # Record 60 tokens
    tot = await tracker.record(session_id, prompt_tokens=40, completion_tokens=20)
    assert tot == 60
    assert await tracker.get_total(session_id) == 60
    assert not await tracker.is_over_soft_limit(session_id)

    # Record 50 more tokens -> 110 (over soft limit 100)
    tot = await tracker.record(session_id, prompt_tokens=30, completion_tokens=20)
    assert tot == 110
    assert await tracker.is_over_soft_limit(session_id)
    assert not await tracker.is_over_hard_limit(session_id)

    # Record 100 more tokens -> 210 (over hard limit 200)
    tot = await tracker.record(session_id, prompt_tokens=50, completion_tokens=50)
    assert tot == 210
    assert await tracker.is_over_hard_limit(session_id)

    # Reset
    await tracker.reset(session_id)
    assert await tracker.get_total(session_id) == 0


@pytest.mark.asyncio
async def test_research_cache_stores_and_retrieves():
    redis = FakeAsyncRedis()
    cache = ResearchCache(redis, ttl=3600)

    sub_q = "What is the solar adoption rate in Vietnam?"
    keywords = ["solar adoption", "Vietnam 2024"]

    # Miss
    hit = await cache.get(sub_q, keywords)
    assert hit is None

    # Set
    payload = {
        "parsed": {"findings": [{"fact": "18 GW capacity", "source": "https://example.com"}]},
        "raw_text": "Sample text",
        "sources": ["https://example.com"],
        "result_count": 1,
        "all_degraded": False,
    }
    await cache.set(sub_q, keywords, payload)

    # Hit with same keywords in different order
    hit = await cache.get(sub_q, ["Vietnam 2024", "solar adoption"])
    assert hit is not None
    assert hit["parsed"]["findings"][0]["fact"] == "18 GW capacity"

    # Image cache
    img_hash = "abc123def456"
    assert await cache.get_image(img_hash) is None
    await cache.set_image(img_hash, {"analysis": "diagram showing solar grid"})
    img_hit = await cache.get_image(img_hash)
    assert img_hit is not None
    assert img_hit["analysis"] == "diagram showing solar grid"


def test_model_routing_selects_small_model_for_fast_agents():
    router = LLMRouter(
        groq_api_key="fake-groq",
        gemini_api_key="fake-gemini",
        groq_model="llama-3.3-70b-versatile",
        groq_model_small="llama-3.1-8b-instant",
    )

    assert router._groq_model_for(AgentType.PLANNER) == "llama-3.1-8b-instant"
    assert router._groq_model_for(AgentType.RESEARCHER) == "llama-3.1-8b-instant"
    assert router._groq_model_for(AgentType.CRITIC) == "llama-3.1-8b-instant"
    assert router._groq_model_for(AgentType.ANALYST) == "llama-3.3-70b-versatile"
    assert router._groq_model_for(AgentType.WRITER) == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_orchestrator_skips_critic_retry_when_over_soft_limit():
    bus = MagicMock()
    bus.channel_name = MagicMock(return_value="fake_channel")
    bus.publish = AsyncMock()
    router = MagicMock()
    search = MagicMock()
    redis = FakeAsyncRedis()
    tracker = TokenBudgetTracker(redis, soft_limit=100, hard_limit=500)
    orchestrator = Orchestrator(bus, router, search, budget_tracker=tracker)

    session_id = "test-soft-limit-session"
    dag = TaskDAG(session_id)
    state = SessionState(dag=dag, planner_task_id=str(uuid4()))
    state.analyst_result = {"findings": "some findings"}
    state.analyst_task_id = str(uuid4())
    orchestrator._sessions[session_id] = state

    # Record 150 tokens -> over soft limit
    await tracker.record(session_id, 100, 50)

    # Critic returns unapproved with retry questions
    critic_payload = {
        "task_id": str(uuid4()),
        "agent_type": AgentType.CRITIC,
        "content": '{"approved": false, "critique_notes": ["missing data"], "retry_questions": ["explore grid constraints"], "final_confidence": 0.3}',
        "confidence": 0.3,
    }

    # Handle critic result
    orchestrator._trigger_writer = AsyncMock()
    orchestrator._requeue_research = AsyncMock()
    orchestrator._persist_dag = AsyncMock()
    orchestrator._broadcast_status = AsyncMock()
    orchestrator._clear_timeout = AsyncMock()

    await orchestrator._handle_critic_result(session_id, critic_payload)

    # Should NOT requeue research because over soft limit
    assert orchestrator._requeue_research.call_count == 0
    # Should trigger writer with over_budget=True
    orchestrator._trigger_writer.assert_called_once_with(session_id, over_budget=True)


@pytest.mark.asyncio
async def test_orchestrator_stops_early_when_over_hard_limit():
    bus = MagicMock()
    bus.channel_name = MagicMock(return_value="fake_channel")
    bus.publish = AsyncMock()
    router = MagicMock()
    search = MagicMock()
    redis = FakeAsyncRedis()
    tracker = TokenBudgetTracker(redis, soft_limit=100, hard_limit=200)
    orchestrator = Orchestrator(bus, router, search, budget_tracker=tracker)

    session_id = "test-hard-limit-session"
    dag = TaskDAG(session_id)
    r_task_id = str(uuid4())
    state = SessionState(dag=dag, planner_task_id=str(uuid4()), researcher_task_ids=[r_task_id])
    dag.add_task(
        TaskMessage(
            type=MessageType.TASK_ASSIGN,
            from_agent=AgentType.PLANNER,
            to_agent=AgentType.RESEARCHER,
            payload={},
            status=TaskStatus.PENDING,
            confidence=0.9,
            task_id=r_task_id,
        )
    )
    orchestrator._sessions[session_id] = state

    # Record 250 tokens -> over hard limit 200
    await tracker.record(session_id, 150, 100)

    researcher_payload = {
        "task_id": r_task_id,
        "agent_type": AgentType.RESEARCHER,
        "content": '{"findings": []}',
        "confidence": 0.5,
    }

    orchestrator._trigger_writer = AsyncMock()
    orchestrator._trigger_analyst = AsyncMock()
    orchestrator._persist_dag = AsyncMock()
    orchestrator._broadcast_status = AsyncMock()
    orchestrator._clear_timeout = AsyncMock()

    await orchestrator._handle_researcher_result(session_id, researcher_payload)

    # Should trigger writer immediately with over_budget=True
    orchestrator._trigger_writer.assert_called_once_with(session_id, over_budget=True)
    assert orchestrator._trigger_analyst.call_count == 0
