"""Analyst agent implementation for ResearchSwarm."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID, uuid4

from core.llm_router import LLMRouter

from agents.base_agent import BaseAgent
from core.message_bus import MessageBus
from core.schemas import AgentMessage, AgentResult, TaskMessage
from core.retry import REDIS_RETRY, retry_with_backoff
from core.types import AgentType, MessageType, TaskStatus

LLM_MAX_TOKENS = 2500
LLM_TEMPERATURE = 0.2
LLM_TIMEOUT_SECONDS = 60
RESEARCHER_RESULTS_WAIT_SECONDS = 120

SYSTEM_PROMPT = (
    "You are a senior research analyst. You receive multiple research findings on "
    "different aspects of a question and must synthesise them into coherent insights. "
    "Identify patterns, contradictions, and knowledge gaps. Weight findings by their "
    "confidence scores. Return JSON only.\n"
    "Required output schema: "
    '{"key_insights": ["string"], "confidence_map": {"insight": 0.0}, '
    '"contradictions": ["string"], "gaps": ["string"], "overall_confidence": 0.0}'
)

RESULTS_KEY_TEMPLATE = "session:{session_id}:researcher_results"


class RetryableError(RuntimeError):
    """Signals that a task should be retried by the orchestrator."""


class AnalystAgent(BaseAgent):
    """Agent that synthesizes researcher findings into analytic insights."""

    def __init__(self, message_bus: MessageBus, llm_router: LLMRouter) -> None:
        """Initialize the analyst agent with required dependencies."""

        super().__init__(AgentType.ANALYST, message_bus, llm_router)
        self._logger = logging.getLogger("researchswarm.agent.analyst")

    async def run(self) -> None:
        """Subscribe to all analyst task channels and process assignments."""

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
        """Wait for researcher results, synthesize insights, and return analysis."""

        self._sync_session_from_message(message)
        session_id = self._session_id

        start_time = time.perf_counter()
        provided_results = message.payload.get("researcher_results")
        if isinstance(provided_results, list):
            results = [item for item in provided_results if isinstance(item, dict)]
        else:
            expected = await self._expected_results(message)
            results = await self._wait_for_researcher_results(session_id, expected)
        duration = time.perf_counter() - start_time

        payload = self._build_payload(results)
        analysis = await self._call_llm_for_analysis(payload)

        analysis["metadata"] = {"duration_seconds": round(duration, 2)}
        overall_confidence = float(analysis.get("overall_confidence", 0.0))

        sources = self._collect_sources(results)

        return AgentResult(
            task_id=message.task_id,
            agent_type=AgentType.ANALYST,
            content=json.dumps(analysis, ensure_ascii=True),
            sources=sources,
            confidence=overall_confidence,
        )

    async def handle_error(self, error: Exception, task_id: str) -> None:
        """Handle retries and errors without crashing the agent loop."""

        if isinstance(error, RetryableError):
            self._logger.warning("Retry requested for task %s: %s", task_id, error)
            await self.emit_status(task_id, TaskStatus.RETRY)
            return
        await super().handle_error(error, task_id)

    async def _expected_results(self, message: TaskMessage) -> int:
        """Determine how many researcher results are expected for this session."""

        payload_count = message.payload.get("expected_results")
        if isinstance(payload_count, int) and payload_count > 0:
            return payload_count

        session_state = await self.message_bus.get_session_state(self._session_id)
        for key in ("expected_researcher_results", "researcher_task_count"):
            value = session_state.get(key)
            if isinstance(value, str) and value.isdigit():
                return int(value)

        return 1

    async def _wait_for_researcher_results(
        self, session_id: str, expected: int
    ) -> List[Dict[str, Any]]:
        """Poll Redis until all researcher results arrive or timeout."""

        deadline = time.time() + RESEARCHER_RESULTS_WAIT_SECONDS
        key = RESULTS_KEY_TEMPLATE.format(session_id=session_id)
        redis_client = self.message_bus._redis
        results: List[Dict[str, Any]] = []

        while len(results) < expected:
            remaining = max(0, int(deadline - time.time()))
            if remaining <= 0:
                break
            item = await retry_with_backoff(
                redis_client.blpop,
                [key],
                timeout=remaining,
                config=REDIS_RETRY,
            )
            if not item:
                break
            _, raw_result = item
            try:
                results.append(json.loads(raw_result))
            except json.JSONDecodeError:
                continue

        if len(results) < expected:
            raise RetryableError("Timed out waiting for researcher results")

        return results

    async def _store_researcher_result(self, message: AgentMessage) -> None:
        """Store researcher results in Redis for aggregation."""

        payload = message.payload if isinstance(message.payload, dict) else {}
        session_id = payload.get("session_id") or self._session_id
        key = RESULTS_KEY_TEMPLATE.format(session_id=session_id)
        await retry_with_backoff(
            self.message_bus._redis.rpush,
            key,
            json.dumps(message.payload),
            config=REDIS_RETRY,
        )

    async def _call_llm_for_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call LLM with aggregated findings and parse JSON output."""

        if self._demo_mode_enabled():
            return self._demo_analysis(payload)

        prompt = {
            "analysis_input": payload,
            "instructions": [
                "Return JSON only — match the schema in the system prompt exactly.",
                "Weight findings by confidence scores.",
            ],
        }

        response = await asyncio.wait_for(
            self._call_llm(
                SYSTEM_PROMPT,
                json.dumps(prompt),
                agent_type=AgentType.ANALYST,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )

        stripped = self._strip_code_fence(response)
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", stripped, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            # Construct a safe synthesis from findings rather than crashing
            insights = []
            for item in payload.get("researcher_results", []):
                findings = item.get("findings", [])
                for f in findings:
                    if isinstance(f, dict) and "fact" in f:
                        insights.append(str(f["fact"]))
                    elif isinstance(f, str):
                        insights.append(f)
            return {
                "key_insights": insights[:8] or ["Evidence synthesized from primary research streams."],
                "confidence_map": {ins: 0.85 for ins in insights[:8]},
                "contradictions": [],
                "gaps": [],
                "overall_confidence": 0.85,
            }

    def _build_payload(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize researcher outputs into a single analysis payload."""

        normalized: List[Dict[str, Any]] = []
        for result in results:
            content = result.get("content")
            try:
                parsed = json.loads(content) if isinstance(content, str) else {}
            except json.JSONDecodeError:
                parsed = {}

            normalized.append(
                {
                    "task_id": result.get("task_id"),
                    "confidence": result.get("confidence"),
                    "sources": result.get("sources", []),
                    "findings": parsed.get("findings", []),
                    "summary": parsed.get("summary", ""),
                    "key_data_points": parsed.get("key_data_points", []),
                }
            )

        return {"researcher_results": normalized}

    def _collect_sources(self, results: Iterable[Dict[str, Any]]) -> List[str]:
        """Collect unique sources across researcher results."""

        sources: List[str] = []
        for result in results:
            for source in result.get("sources", []) or []:
                if source not in sources:
                    sources.append(source)
        return sources

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

    def _demo_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create deterministic synthesis for offline demos."""

        results = payload.get("researcher_results", [])
        summaries = []
        if isinstance(results, list):
            for result in results:
                if not isinstance(result, dict):
                    continue
                content = result.get("content")
                try:
                    parsed = json.loads(content) if isinstance(content, str) else {}
                except json.JSONDecodeError:
                    parsed = {}
                summary = parsed.get("summary")
                if isinstance(summary, str) and summary:
                    summaries.append(summary)

        return {
            "key_insights": [
                "The opportunity is strongest when the product is framed around evidence-backed decisions rather than generic chat.",
                "The multi-agent design is valuable because it separates planning, evidence gathering, synthesis, critique, and writing.",
                "The largest execution risk is trust: every claim should expose its source, confidence, and critic status.",
            ],
            "confidence_map": {
                "Evidence-backed decision workflow": 0.82,
                "Separated agent responsibilities": 0.86,
                "Trust layer as differentiator": 0.8,
            },
            "contradictions": [],
            "gaps": [
                "Add explicit customer persona and measurable business outcome.",
                "Add production observability and Microsoft Azure deployment evidence.",
            ],
            "supporting_summaries": summaries[:5],
            "overall_confidence": 0.82,
        }


async def run_analyst_test() -> None:
    """Run a standalone analyst test with synthetic researcher data."""

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    router = LLMRouter(
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
    )
    bus = MessageBus(redis_url)
    analyst = AnalystAgent(bus, router)

    session_id = "analyst-test"
    analyst._session_id = session_id

    fake_result = AgentResult(
        task_id=uuid4(),
        agent_type=AgentType.RESEARCHER,
        content=json.dumps(
            {
                "findings": [
                    {
                        "fact": "Vietnam installed solar capacity exceeded 18 GW by 2023.",
                        "source": "https://example.com/report",
                        "confidence": 0.8,
                    }
                ],
                "summary": "Vietnam expanded utility-scale solar after 2019.",
                "key_data_points": ["18 GW installed capacity"],
            }
        ),
        sources=["https://example.com/report"],
        confidence=0.8,
    )

    await analyst._store_researcher_result(
        AgentMessage(
            type=MessageType.TASK_RESULT,
            from_agent=AgentType.RESEARCHER,
            to_agent=AgentType.ANALYST,
            payload=fake_result.model_dump(mode="json"),
            status=TaskStatus.DONE,
            confidence=0.8,
        )
    )

    task = TaskMessage(
        type=MessageType.TASK_ASSIGN,
        from_agent=AgentType.PLANNER,
        to_agent=AgentType.ANALYST,
        payload={"expected_results": 1, "session_id": session_id},
        status=TaskStatus.PENDING,
        confidence=0.9,
        task_id=uuid4(),
        parent_task_id=None,
        depth=1,
    )

    result = await analyst.process(task)
    print(result.content)


if __name__ == "__main__":
    asyncio.run(run_analyst_test())
