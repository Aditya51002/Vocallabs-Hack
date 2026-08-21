"""LangGraph workflow definition for ResearchSwarm.

Provides a compiled StateGraph that replaces ad-hoc message passing with a
deterministic DAG, parallel fan-out via Send(), reducers for fan-in, and
conditional edges for budget-aware retries.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver

from core.graph_state import ResearchState
from core.types import AgentType, MessageType, TaskStatus
from core.schemas import AgentMessage, AgentResult, TaskMessage
from core.llm_router import LLMRouter
from core.search_client import TavilySearchClient
from core.cache import ResearchCache
from core.token_budget import TokenBudgetTracker
from core.message_bus import MessageBus

from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.analyst import AnalystAgent
from agents.critic import CriticAgent
from agents.writer import WriterAgent

_logger = logging.getLogger("researchswarm.graph")
MAX_RETRIES = 2


class SwarmGraphBuilder:
    """Builds and compiles the LangGraph StateGraph for research sessions."""

    def __init__(
        self,
        message_bus: MessageBus,
        llm_router: LLMRouter,
        search_client: TavilySearchClient,
        cache: Optional[ResearchCache] = None,
        budget_tracker: Optional[TokenBudgetTracker] = None,
    ) -> None:
        self.message_bus = message_bus
        self.llm_router = llm_router
        self.search_client = search_client
        self.cache = cache
        self.budget_tracker = budget_tracker

        self.planner_agent = PlannerAgent(message_bus, llm_router)
        self.researcher_agent = ResearcherAgent(message_bus, llm_router, search_client, cache=cache)
        self.analyst_agent = AnalystAgent(message_bus, llm_router)
        self.critic_agent = CriticAgent(message_bus, llm_router)
        self.writer_agent = WriterAgent(message_bus, llm_router)

        self.checkpointer = MemorySaver()

    async def _emit_status(
        self,
        session_id: str,
        agent: AgentType,
        status: TaskStatus,
        content: str = "",
        confidence: float = 0.0,
    ) -> None:
        """Emit agent status update over WebSocket broadcast."""
        try:
            channel = f"ws:broadcast:{session_id}"
            message = AgentMessage(
                type=MessageType.STATUS_UPDATE,
                from_agent=agent,
                to_agent=agent,
                payload={"session_id": session_id, "agent": agent.value, "status": status.value, "content": content},
                status=status,
                confidence=confidence,
            )
            await self.message_bus.publish(channel, message)
        except Exception as exc:
            _logger.warning("Failed to emit status for %s: %s", agent.value, exc)

    # ------------------------------------------------------------------
    # Graph Nodes
    # ------------------------------------------------------------------

    async def planner_node(self, state: ResearchState) -> Dict[str, Any]:
        """Decompose user query into sub-questions."""
        session_id = state.get("session_id", str(uuid4()))
        user_query = state.get("user_query", "")

        await self._emit_status(session_id, AgentType.PLANNER, TaskStatus.RUNNING, "Decomposing research query...")

        task = TaskMessage(
            type=MessageType.TASK_ASSIGN,
            from_agent=AgentType.PLANNER,
            to_agent=AgentType.PLANNER,
            payload={"user_query": user_query, "session_id": session_id},
            status=TaskStatus.PENDING,
            confidence=0.9,
            task_id=uuid4(),
        )

        result = await self.planner_agent.process(task)
        content = json.loads(result.content) if isinstance(result.content, str) else {}
        sub_questions = content.get("tasks", [])

        await self._emit_status(
            session_id,
            AgentType.PLANNER,
            TaskStatus.DONE,
            f"Planned {len(sub_questions)} research tasks",
            confidence=result.confidence,
        )

        return {
            "sub_questions": sub_questions,
            "session_id": session_id,
            "user_query": user_query,
            "retry_rounds": state.get("retry_rounds", 0),
        }

    async def researcher_worker_node(self, state: ResearchState) -> Dict[str, Any]:
        """Execute web research for a single sub-question."""
        session_id = state.get("session_id", "default")
        current_sq = state.get("current_sub_question", {})
        sub_q = current_sq.get("sub_question", "")
        keywords = current_sq.get("search_keywords", [sub_q])

        await self._emit_status(session_id, AgentType.RESEARCHER, TaskStatus.RUNNING, f"Researching: {sub_q[:60]}...")

        task = TaskMessage(
            type=MessageType.TASK_ASSIGN,
            from_agent=AgentType.PLANNER,
            to_agent=AgentType.RESEARCHER,
            payload={
                "sub_question": sub_q,
                "search_keywords": keywords,
                "session_id": session_id,
                "retry": current_sq.get("retry", False),
            },
            status=TaskStatus.PENDING,
            confidence=0.9,
            task_id=uuid4(),
        )

        result = await self.researcher_agent.process(task)
        finding_payload = {
            "task_id": str(result.task_id),
            "confidence": result.confidence,
            "sources": result.sources,
            "content": result.content,
        }

        await self._emit_status(
            session_id,
            AgentType.RESEARCHER,
            TaskStatus.DONE,
            f"Findings ready ({len(result.sources)} sources)",
            confidence=result.confidence,
        )

        return {
            "research_findings": [finding_payload],
            **({"retry_rounds": state.get("retry_rounds", 0) + 1} if current_sq.get("retry") else {}),
        }

    async def analyst_node(self, state: ResearchState) -> Dict[str, Any]:
        """Synthesize researcher findings into coherent insights."""
        session_id = state.get("session_id", "default")
        findings = state.get("research_findings", [])
        image_findings = state.get("image_findings", [])
        all_results = list(findings) + list(image_findings)

        await self._emit_status(session_id, AgentType.ANALYST, TaskStatus.RUNNING, "Synthesizing evidence & claims...")

        task = TaskMessage(
            type=MessageType.TASK_ASSIGN,
            from_agent=AgentType.PLANNER,
            to_agent=AgentType.ANALYST,
            payload={
                "expected_results": len(all_results),
                "researcher_results": all_results,
                "session_id": session_id,
            },
            status=TaskStatus.PENDING,
            confidence=0.9,
            task_id=uuid4(),
        )

        result = await self.analyst_agent.process(task)
        analysis_data = json.loads(result.content) if isinstance(result.content, str) else {}

        await self._emit_status(
            session_id,
            AgentType.ANALYST,
            TaskStatus.DONE,
            f"Synthesized {len(analysis_data.get('key_insights', []))} insights",
            confidence=result.confidence,
        )

        return {
            "analyst_result": {
                "task_id": str(result.task_id),
                "confidence": result.confidence,
                "sources": result.sources,
                "content": result.content,
            },
            "sources": result.sources,
        }

    async def critic_node(self, state: ResearchState) -> Dict[str, Any]:
        """Critique synthesized findings and identify gaps/unsupported claims."""
        session_id = state.get("session_id", "default")
        analyst_result = state.get("analyst_result", {})

        await self._emit_status(session_id, AgentType.CRITIC, TaskStatus.RUNNING, "Fact-checking claims and testing logic...")

        task = TaskMessage(
            type=MessageType.TASK_ASSIGN,
            from_agent=AgentType.ANALYST,
            to_agent=AgentType.CRITIC,
            payload={"analyst_result": analyst_result, "session_id": session_id},
            status=TaskStatus.PENDING,
            confidence=0.8,
            task_id=uuid4(),
        )

        result = await self.critic_agent.process(task)
        critique_data = json.loads(result.content) if isinstance(result.content, str) else {}
        retry_questions = critique_data.get("retry_questions", [])

        # Check soft token limit
        over_soft = False
        if self.budget_tracker:
            over_soft = await self.budget_tracker.is_over_soft_limit(session_id)

        await self._emit_status(
            session_id,
            AgentType.CRITIC,
            TaskStatus.DONE,
            "Critique passed" if critique_data.get("approved") else f"Identified {len(retry_questions)} gaps",
            confidence=result.confidence,
        )

        return {
            "critic_result": {
                "task_id": str(result.task_id),
                "confidence": result.confidence,
                "content": result.content,
                "budget_note": "research depth limited by token budget" if over_soft else "",
            },
            "retry_questions": retry_questions,
            "over_budget": over_soft,
            "confidence": result.confidence,
        }

    async def writer_node(self, state: ResearchState) -> Dict[str, Any]:
        """Stream and assemble final structured report."""
        session_id = state.get("session_id", "default")
        analyst_result = state.get("analyst_result", {})
        critic_result = state.get("critic_result", {})
        over_budget = state.get("over_budget", False)

        # Check hard limit
        budget_exhausted = False
        if self.budget_tracker:
            budget_exhausted = await self.budget_tracker.is_over_hard_limit(session_id)

        await self._emit_status(session_id, AgentType.WRITER, TaskStatus.RUNNING, "Generating verified decision report...")

        writer_payload = {
            "analyst_result": analyst_result,
            "critic_result": critic_result,
            "session_id": session_id,
            "budget_exhausted": budget_exhausted,
        }
        if over_budget or budget_exhausted:
            writer_payload["max_tokens_override"] = 800
            writer_payload["budget_note"] = critic_result.get("budget_note") or "research depth limited by token budget"

        task = TaskMessage(
            type=MessageType.TASK_ASSIGN,
            from_agent=AgentType.CRITIC,
            to_agent=AgentType.WRITER,
            payload=writer_payload,
            status=TaskStatus.PENDING,
            confidence=state.get("confidence", 0.8),
            task_id=uuid4(),
        )

        result = await self.writer_agent.process(task)
        report_data = json.loads(result.content) if isinstance(result.content, str) else {}
        report_text = report_data.get("report", "")

        await self._emit_status(
            session_id,
            AgentType.WRITER,
            TaskStatus.DONE,
            "Report completed",
            confidence=result.confidence,
        )

        return {
            "report": report_text,
            "confidence": result.confidence,
            "sources": result.sources or state.get("sources", []),
            "budget_exhausted": budget_exhausted,
        }

    # ------------------------------------------------------------------
    # Dispatch & Routing Functions
    # ------------------------------------------------------------------

    def dispatch_researchers(self, state: ResearchState) -> Union[List[Send], str]:
        """Fan out parallel researcher worker nodes from planner tasks."""
        sub_questions = state.get("sub_questions", [])
        session_id = state.get("session_id", "default")

        # Issue 19: Guard against empty sub_questions causing deadlock
        if not sub_questions:
            _logger.warning("Session %s: no sub_questions planned, routing directly to analyst", session_id)
            return "analyst_node"

        return [
            Send(
                "researcher_worker_node",
                {
                    "session_id": session_id,
                    "current_sub_question": sq,
                },
            )
            for sq in sub_questions
        ]

    def route_after_critic(self, state: ResearchState) -> Union[List[Send], str]:
        """Decide whether to retry research or proceed to writer."""
        critic_result = state.get("critic_result", {})
        retry_questions = state.get("retry_questions", [])
        retry_rounds = state.get("retry_rounds", 0)
        over_budget = state.get("over_budget", False)
        session_id = state.get("session_id", "default")

        content = {}
        if isinstance(critic_result.get("content"), str):
            try:
                content = json.loads(critic_result["content"])
            except json.JSONDecodeError:
                content = {}

        approved = content.get("approved", True)
        confidence = float(content.get("final_confidence", state.get("confidence", 0.0)))

        # If over budget or approved or low retry budget -> proceed to writer
        if over_budget or approved or confidence >= 0.5 or retry_rounds >= MAX_RETRIES or not retry_questions:
            return "writer_node"

        # Issue 18: Re-fanout retry researchers using Send API
        return [
            Send(
                "researcher_worker_node",
                {
                    "session_id": session_id,
                    "retry_rounds": retry_rounds,
                    "current_sub_question": {
                        "sub_question": q,
                        "search_keywords": [q],
                        "retry": True,
                    },
                },
            )
            for q in retry_questions
            if isinstance(q, str) and q.strip()
        ]

    # ------------------------------------------------------------------
    # Graph Construction
    # ------------------------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Construct the ResearchSwarm StateGraph."""
        workflow = StateGraph(ResearchState)

        # Add Nodes
        workflow.add_node("planner_node", self.planner_node)
        workflow.add_node("researcher_worker_node", self.researcher_worker_node)
        workflow.add_node("analyst_node", self.analyst_node)
        workflow.add_node("critic_node", self.critic_node)
        workflow.add_node("writer_node", self.writer_node)

        # Edges
        workflow.add_edge(START, "planner_node")
        workflow.add_conditional_edges("planner_node", self.dispatch_researchers)
        workflow.add_edge("researcher_worker_node", "analyst_node")
        workflow.add_edge("analyst_node", "critic_node")
        workflow.add_conditional_edges("critic_node", self.route_after_critic)
        workflow.add_edge("writer_node", END)

        return workflow

    def compile(self):
        """Compile the workflow graph with MemorySaver checkpointer."""
        workflow = self.build_graph()
        return workflow.compile(checkpointer=self.checkpointer)
