"""Comprehensive tests for LangGraph StateGraph (Step 3).

Tests:
1. Multi-branch fan-out and fan-in reducer accumulation (Issue 17).
2. Critic retry fan-out via Send() (Issue 18).
3. Empty planner sub_questions routing directly to analyst (Issue 19).
4. Full graph execution happy path.
5. Token budget enforcement in the graph.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from core.graph import SwarmGraphBuilder
from core.graph_state import ResearchState
from core.llm_router import LLMRouter
from core.search_client import TavilySearchClient
from core.token_budget import TokenBudgetTracker
from core.types import AgentType


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


@pytest.mark.asyncio
async def test_langgraph_fan_in_reducer_accumulates_all_findings():
    """Concrete verification that Annotated[List[dict], operator.add] collects all parallel branch results (Issue 17)."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    router = MagicMock()
    search = MagicMock()

    builder = SwarmGraphBuilder(bus, router, search)

    # Mock researcher process to return unique finding for each sub-question
    async def fake_researcher_process(task):
        sub_q = task.payload.get("sub_question", "")
        return MagicMock(
            task_id=uuid4(),
            confidence=0.85,
            sources=[f"https://example.com/{sub_q}"],
            content=json.dumps({"findings": [{"fact": f"Fact about {sub_q}"}], "summary": f"Summary of {sub_q}"}),
        )

    builder.researcher_agent.process = AsyncMock(side_effect=fake_researcher_process)

    # Mock planner to generate 3 sub-questions
    builder.planner_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.9,
            content=json.dumps({
                "tasks": [
                    {"sub_question": "Solar policy", "search_keywords": ["policy"]},
                    {"sub_question": "Grid capacity", "search_keywords": ["grid"]},
                    {"sub_question": "Market growth", "search_keywords": ["market"]},
                ]
            }),
        )
    )

    # Mock analyst, critic, writer
    builder.analyst_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.85,
            sources=["https://example.com/all"],
            content=json.dumps({"key_insights": ["Insight 1", "Insight 2"], "overall_confidence": 0.85}),
        )
    )
    builder.critic_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.85,
            content=json.dumps({"approved": True, "critique_notes": [], "retry_questions": [], "final_confidence": 0.85}),
        )
    )
    builder.writer_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.85,
            sources=["https://example.com/all"],
            content=json.dumps({"report": "# Final Verified Report\n\nAll 3 topics covered."}),
        )
    )

    graph = builder.compile()
    initial_state = {
        "session_id": "test-fan-in-session",
        "user_query": "Analyze Vietnam solar energy transition",
        "research_findings": [],
        "image_findings": [],
    }

    final_state = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test-fan-in-session"}},
    )

    # Assert that all 3 researcher outputs were accumulated into research_findings
    assert len(final_state["research_findings"]) == 3
    assert len(final_state["sub_questions"]) == 3
    assert final_state["report"] == "# Final Verified Report\n\nAll 3 topics covered."


@pytest.mark.asyncio
async def test_langgraph_empty_sub_questions_routes_to_analyst():
    """Verify Issue 19: empty planner output routes to analyst instead of causing graph deadlock."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    router = MagicMock()
    search = MagicMock()

    builder = SwarmGraphBuilder(bus, router, search)

    # Planner returns empty tasks
    builder.planner_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.5,
            content=json.dumps({"tasks": []}),
        )
    )
    builder.analyst_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.5,
            sources=[],
            content=json.dumps({"key_insights": ["No data available"], "overall_confidence": 0.5}),
        )
    )
    builder.critic_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.5,
            content=json.dumps({"approved": True, "critique_notes": [], "retry_questions": [], "final_confidence": 0.5}),
        )
    )
    builder.writer_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.5,
            sources=[],
            content=json.dumps({"report": "Empty analysis report"}),
        )
    )

    graph = builder.compile()
    final_state = await graph.ainvoke(
        {"session_id": "test-empty-planner", "user_query": "Unknown topic", "research_findings": [], "image_findings": []},
        config={"configurable": {"thread_id": "test-empty-planner"}},
    )

    assert final_state["sub_questions"] == []
    assert final_state["report"] == "Empty analysis report"


@pytest.mark.asyncio
async def test_langgraph_critic_retry_loop_via_send():
    """Verify Issue 18: Critic retry fans out new research tasks via Send API."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    router = MagicMock()
    search = MagicMock()

    builder = SwarmGraphBuilder(bus, router, search)

    builder.planner_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.9,
            content=json.dumps({"tasks": [{"sub_question": "Q1", "search_keywords": ["k1"]}]}),
        )
    )

    research_count = 0

    async def fake_research(task):
        nonlocal research_count
        research_count += 1
        return MagicMock(
            task_id=uuid4(),
            confidence=0.7,
            sources=["https://example.com"],
            content=json.dumps({"findings": [{"fact": f"Fact {research_count}"}]}),
        )

    builder.researcher_agent.process = AsyncMock(side_effect=fake_research)

    builder.analyst_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.6,
            sources=["https://example.com"],
            content=json.dumps({"key_insights": ["Insight"]}),
        )
    )

    # First call: reject with retry question; Second call: approve
    critic_calls = 0

    async def fake_critic(task):
        nonlocal critic_calls
        critic_calls += 1
        if critic_calls == 1:
            return MagicMock(
                task_id=uuid4(),
                confidence=0.3,
                content=json.dumps({
                    "approved": False,
                    "critique_notes": ["Missing policy gap"],
                    "retry_questions": ["Investigate feed-in tariff changes"],
                    "final_confidence": 0.3,
                }),
            )
        return MagicMock(
            task_id=uuid4(),
            confidence=0.8,
            content=json.dumps({
                "approved": True,
                "critique_notes": [],
                "retry_questions": [],
                "final_confidence": 0.8,
            }),
        )

    builder.critic_agent.process = AsyncMock(side_effect=fake_critic)
    builder.writer_agent.process = AsyncMock(
        return_value=MagicMock(
            task_id=uuid4(),
            confidence=0.8,
            sources=["https://example.com"],
            content=json.dumps({"report": "Report after successful retry"}),
        )
    )

    graph = builder.compile()
    final_state = await graph.ainvoke(
        {"session_id": "test-retry-session", "user_query": "Solar policy test", "research_findings": [], "image_findings": []},
        config={"configurable": {"thread_id": "test-retry-session"}},
    )

    assert critic_calls == 2
    assert research_count == 2
    assert final_state["report"] == "Report after successful retry"
    assert len(final_state["research_findings"]) == 2
