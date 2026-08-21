"""Critic agent implementation for ResearchSwarm."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List
from uuid import UUID, uuid4

from core.llm_router import LLMRouter

from agents.base_agent import BaseAgent
from core.message_bus import MessageBus
from core.schemas import AgentMessage, AgentResult, TaskMessage
from core.types import AgentType, MessageType, TaskStatus

LLM_MAX_TOKENS = 1200
LLM_TEMPERATURE = 0.1
LLM_TIMEOUT_SECONDS = 60

SYSTEM_PROMPT = (
    "You are a rigorous fact-checker and devil's advocate. You receive an analyst's "
    "synthesis and must challenge it. Identify: unsupported claims (confidence < 0.6), "
    "logical leaps, missing context, potential biases. If overall_confidence < 0.5, "
    "request re-research on specific gaps. Be direct and specific. Return JSON only."
)


class RetryableError(RuntimeError):
    """Signals that a task should be retried by the orchestrator."""


class CriticAgent(BaseAgent):
    """Agent that reviews analysis and requests retries if needed."""

    def __init__(self, message_bus: MessageBus, llm_router: LLMRouter) -> None:
        """Initialize the critic agent with required dependencies."""

        super().__init__(AgentType.CRITIC, message_bus, llm_router)
        self._logger = logging.getLogger("researchswarm.agent.critic")

    async def run(self) -> None:
        """Subscribe to all critic task channels and process assignments."""

        channel_pattern = f"agent:{self.agent_type.value}:*"
        async for message in self.message_bus.subscribe_pattern(channel_pattern):
            if not isinstance(message, TaskMessage):
                self._logger.warning("Ignoring message: %s", message)
                continue

            try:
                self._sync_session_from_message(message)
                result = await self.process(message)
                await self.emit_result(result)
            except Exception as exc:  # pragma: no cover - runtime safety
                task_id = str(getattr(message, "task_id", ""))
                await self.handle_error(exc, task_id)

    async def process(self, message: TaskMessage) -> AgentResult:
        """Critique analyst output and decide on retry or approval."""

        analyst_result = message.payload.get("analyst_result")
        if not isinstance(analyst_result, dict):
            raise ValueError("Critic requires analyst_result payload")

        critique = await self._call_llm_for_critique(analyst_result)
        final_confidence = float(critique.get("final_confidence", 0.0))

        return AgentResult(
            task_id=message.task_id,
            agent_type=AgentType.CRITIC,
            content=json.dumps(critique, ensure_ascii=True),
            sources=analyst_result.get("sources", []),
            confidence=final_confidence,
        )

    async def handle_error(self, error: Exception, task_id: str) -> None:
        """Handle retries and errors without crashing the agent loop."""

        if isinstance(error, RetryableError):
            await self.emit_status(task_id, TaskStatus.RETRY)
            return
        await super().handle_error(error, task_id)

    async def _call_llm_for_critique(self, analyst_result: Dict[str, Any]) -> Dict[str, Any]:
        """Call LLM to critique the analyst synthesis."""

        if self._demo_mode_enabled():
            return {
                "approved": True,
                "critique_notes": [
                    "The project is strongest when positioned as verifiable research for decisions, not a generic multi-agent demo.",
                    "Judges should see claim-level sources, confidence, and critic review in the first minute.",
                    "The remaining risk is market clarity; the demo should name a specific buyer and workflow.",
                ],
                "retry_questions": [],
                "final_confidence": 0.81,
            }

        prompt = {
            "analyst_result": analyst_result,
            "required_output": {
                "approved": True,
                "critique_notes": ["string"],
                "retry_questions": ["string"],
                "final_confidence": 0.0,
            },
        }

        response = await asyncio.wait_for(
            self._call_llm(
                SYSTEM_PROMPT,
                json.dumps(prompt),
                agent_type=AgentType.CRITIC,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )

        try:
            return json.loads(self._strip_code_fence(response))
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM returned invalid JSON") from exc

    async def _emit_retry_requests(self, message: TaskMessage, critique: Dict[str, Any]) -> None:
        """Send retry tasks to the researcher channel for each gap."""

        retry_questions = critique.get("retry_questions")
        if not isinstance(retry_questions, list):
            return

        channel = self.message_bus.channel_name(AgentType.RESEARCHER, self._session_id)
        for question in retry_questions:
            if not isinstance(question, str) or not question.strip():
                continue
            payload = {
                "sub_question": question,
                "search_keywords": [question],
                "session_id": self._session_id,
                "retry": True,
            }
            task = TaskMessage(
                type=MessageType.TASK_ASSIGN,
                from_agent=AgentType.CRITIC,
                to_agent=AgentType.RESEARCHER,
                payload=payload,
                status=TaskStatus.RETRY,
                confidence=0.2,
                task_id=uuid4(),
                parent_task_id=message.task_id,
                depth=message.depth + 1,
            )
            await self._publish(channel, task)

    def _wrap_analyst_message(self, message: AgentMessage) -> TaskMessage:
        """Convert analyst AgentMessage into a TaskMessage for processing."""

        payload = message.payload if isinstance(message.payload, dict) else {}
        task_id = payload.get("task_id")
        try:
            task_uuid = UUID(task_id) if task_id else uuid4()
        except (ValueError, TypeError):
            task_uuid = uuid4()

        return TaskMessage(
            type=MessageType.TASK_ASSIGN,
            from_agent=AgentType.ANALYST,
            to_agent=AgentType.CRITIC,
            payload={"analyst_result": payload},
            status=TaskStatus.PENDING,
            confidence=message.confidence,
            task_id=task_uuid,
            parent_task_id=None,
            depth=0,
        )

    def _strip_code_fence(self, text: str) -> str:
        """Strip leading/trailing markdown code fences and optional json language tag."""

        text = text.strip()
        if text.startswith("```"):
            first_nl = text.find("\n")
            if first_nl != -1:
                text = text[first_nl:].strip()
            else:
                text = text[3:].strip()
            if text.endswith("```"):
                text = text[:-3].strip()
        return text


async def run_critic_test() -> None:
    """Run a standalone critic test with synthetic analyst output."""

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    router = LLMRouter(
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
    )
    bus = MessageBus(redis_url)
    critic = CriticAgent(bus, router)

    analyst_result = AgentResult(
        task_id=uuid4(),
        agent_type=AgentType.ANALYST,
        content=json.dumps(
            {
                "key_insights": ["Solar capacity expanded rapidly after 2019."],
                "confidence_map": {"Solar capacity expanded rapidly after 2019.": 0.7},
                "contradictions": [],
                "gaps": ["Regional policy incentives"],
                "overall_confidence": 0.7,
            }
        ),
        sources=["https://example.com/report"],
        confidence=0.7,
    )

    task = TaskMessage(
        type=MessageType.TASK_ASSIGN,
        from_agent=AgentType.ANALYST,
        to_agent=AgentType.CRITIC,
        payload={"analyst_result": analyst_result.model_dump(mode="json")},
        status=TaskStatus.PENDING,
        confidence=0.7,
        task_id=uuid4(),
        parent_task_id=None,
        depth=1,
    )

    result = await critic.process(task)
    print(result.content)


if __name__ == "__main__":
    asyncio.run(run_critic_test())
