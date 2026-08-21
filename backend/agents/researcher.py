"""Researcher agent implementation using Claude web search tool use."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID, uuid4

from core.llm_router import LLMRouter
from core.search_client import TavilySearchClient

from agents.base_agent import BaseAgent
from core.message_bus import MessageBus
from core.schemas import AgentMessage, AgentResult, TaskMessage
from core.types import AgentType, MessageType, TaskStatus

LLM_MAX_TOKENS = 1400
LLM_TEMPERATURE = 0.2
LLM_TIMEOUT_SECONDS = 60
SEARCH_TIMEOUT_SECONDS = 30

SYSTEM_PROMPT = (
    "You are a precise research agent. You receive a specific research sub-question "
    "along with a list of pre-fetched search results. You must synthesize these results to answer the question. "
    "Do not extrapolate or assume. Cite your sources using their URLs. "
    "Return your findings as structured JSON only.\n"
    "Required output schema: "
    '{"findings": [{"fact": "string", "source": "url", "confidence": 0.0}], '
    '"summary": "string", "key_data_points": ["string"]}'
)

ADJECTIVE_STOPWORDS = {
    "current",
    "recent",
    "latest",
    "new",
    "major",
    "leading",
    "emerging",
    "global",
    "regional",
    "local",
    "rapid",
    "accelerating",
    "significant",
    "large",
    "small",
    "high",
    "low",
    "annual",
    "quarterly",
    "monthly",
    "yearly",
    "estimated",
    "approximate",
}

URL_PATTERN = re.compile(r"https?://\S+")


class RetryableError(RuntimeError):
    """Signals that a task should be retried by the orchestrator."""


class ResearcherAgent(BaseAgent):
    """Agent that performs web research and returns structured findings."""

    def __init__(
        self,
        message_bus: MessageBus,
        llm_router: LLMRouter,
        search_client: TavilySearchClient,
        cache: Optional[Any] = None,
    ) -> None:
        """Initialize the researcher agent with required dependencies."""

        super().__init__(AgentType.RESEARCHER, message_bus, llm_router)
        self.search_client = search_client
        self.cache = cache
        if self.cache is None and hasattr(message_bus, "_redis") and message_bus._redis:
            try:
                from core.cache import ResearchCache
                self.cache = ResearchCache(message_bus._redis)
            except Exception:
                self.cache = None
        self._logger = logging.getLogger("researchswarm.agent.researcher")

    async def process(self, message: TaskMessage) -> AgentResult:
        """Run web research for a sub-question and return structured findings."""

        self._sync_session_from_message(message)
        task_id = str(message.task_id)
        sub_question = self._require_str(message.payload, "sub_question")
        search_keywords = self._require_str_list(message.payload, "search_keywords")

        start_time = time.perf_counter()
        all_degraded = False
        if self._demo_mode_enabled():
            parsed, raw_text, sources, result_count = self._demo_research(
                sub_question, search_keywords
            )
        else:
            cached_data = None
            if self.cache:
                cached_data = await self.cache.get(sub_question, search_keywords)

            if cached_data:
                self._logger.info("Cache hit for sub_question: %s", sub_question)
                parsed = cached_data.get("parsed")
                raw_text = cached_data.get("raw_text", "")
                sources = cached_data.get("sources", [])
                result_count = cached_data.get("result_count", 0)
                all_degraded = cached_data.get("all_degraded", False)
            else:
                try:
                    parsed, raw_text, sources, result_count, all_degraded = await self._research(
                        sub_question, search_keywords
                    )
                    if result_count == 0 and not all_degraded:
                        broader = self._broaden_keywords(search_keywords)
                        self._logger.warning(
                            "No web search results for task %s; retrying with broader keywords: %s",
                            task_id,
                            broader,
                        )
                        parsed, raw_text, sources, _, all_degraded = await self._research(
                            sub_question, broader
                        )
                except asyncio.TimeoutError as exc:
                    raise RetryableError("Research request timed out") from exc

                if self.cache and parsed is not None and not all_degraded:
                    await self.cache.set(
                        sub_question,
                        search_keywords,
                        {
                            "parsed": parsed,
                            "raw_text": raw_text,
                            "sources": sources,
                            "result_count": result_count,
                            "all_degraded": all_degraded,
                        },
                    )

        duration = time.perf_counter() - start_time

        if parsed is None:
            # JSON parsing failed; provide a best-effort summary with reduced confidence.
            parsed = {
                "findings": [],
                "summary": raw_text.strip(),
                "key_data_points": [],
            }
            confidence = 0.5
            sources = sources or self._extract_urls(raw_text)
        else:
            confidence = self._average_confidence(parsed.get("findings", []))

        # Apply degraded-mode adjustments when search providers were unavailable
        if all_degraded:
            self._logger.warning(
                "Task %s: all search results degraded or missing; flagging degraded_mode",
                task_id,
            )
            confidence = min(confidence * 0.5, 0.4) if confidence > 0 else 0.35
            findings = parsed.get("findings", [])
            for finding in findings:
                if isinstance(finding, dict):
                    finding["degraded_mode"] = True
                    finding["confidence"] = min(float(finding.get("confidence", 0.5)) * 0.5, 0.4)
            parsed["findings"] = findings
            parsed["degraded_mode"] = True

        parsed["metadata"] = {"duration_seconds": round(duration, 2)}

        return AgentResult(
            task_id=message.task_id,
            agent_type=AgentType.RESEARCHER,
            content=json.dumps(parsed, ensure_ascii=True),
            sources=sources,
            confidence=confidence,
        )

    async def handle_error(self, error: Exception, task_id: str) -> None:
        """Handle retries and errors without crashing the agent loop."""

        if isinstance(error, RetryableError):
            self._logger.warning("Retry requested for task %s: %s", task_id, error)
            await self.emit_status(task_id, TaskStatus.RETRY)
            return
        await super().handle_error(error, task_id)

    async def _research(
        self, sub_question: str, search_keywords: List[str]
    ) -> Tuple[Optional[Dict[str, Any]], str, List[str], int]:
        """Execute a research pass and return parsed JSON, raw text, sources, and result count."""

        queries = search_keywords[:3] if search_keywords else [sub_question]
        try:
            search_results = await asyncio.wait_for(
                self.search_client.search_many(queries, max_results_per_query=2),
                timeout=SEARCH_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            raise RetryableError("Search timed out") from exc

        result_count = len(search_results)
        # Detect degraded results — all items have degraded=True (DDG fallback or empty)
        all_degraded = result_count == 0 or all(
            item.get("degraded", False) for item in search_results
        )

        payload = {
            "sub_question": sub_question,
            "search_keywords": search_keywords,
            "search_results": search_results,
            "instructions": [
                "Facts must come only from the provided search_results when available.",
                "If search_results is empty or degraded, use your general knowledge but mark confidence low.",
                "The source URL must be one of the provided URLs, or 'general-knowledge' if none available.",
            ]
        }

        try:
            text = await asyncio.wait_for(
                self._call_llm(
                    SYSTEM_PROMPT,
                    json.dumps(payload),
                    agent_type=AgentType.RESEARCHER,
                    max_tokens=LLM_MAX_TOKENS,
                    temperature=LLM_TEMPERATURE,
                ),
                timeout=LLM_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            raise RetryableError("LLM call timed out") from exc

        if not text:
            raise RuntimeError("LLM returned no text")

        sources = [str(r["url"]) for r in search_results if "url" in r and not r.get("degraded")]
        if not sources:
            sources = self._extract_urls(text)

        try:
            parsed = json.loads(self._strip_code_fence(text))
        except json.JSONDecodeError:
            parsed = None

        return parsed, text, sources, result_count, all_degraded

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

    def _average_confidence(self, findings: Iterable[Dict[str, Any]]) -> float:
        """Compute average confidence across findings."""

        scores = [item.get("confidence") for item in findings if isinstance(item, dict)]
        normalized = [score for score in scores if isinstance(score, (int, float))]
        if not normalized:
            return 0.0
        return float(sum(normalized) / len(normalized))

    def _broaden_keywords(self, keywords: List[str]) -> List[str]:
        """Remove common adjectives to broaden search keywords."""

        broadened: List[str] = []
        for phrase in keywords:
            tokens = [token for token in phrase.split() if token]
            kept = [
                token
                for token in tokens
                if token.lower() not in ADJECTIVE_STOPWORDS
            ]
            broadened.append(" ".join(kept) if kept else phrase)
        return list(dict.fromkeys(broadened))

    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text content."""

        return list(dict.fromkeys(URL_PATTERN.findall(text)))

    def _demo_research(
        self, sub_question: str, search_keywords: List[str]
    ) -> Tuple[Dict[str, Any], str, List[str], int]:
        """Return deterministic research findings for offline demos."""

        source = "https://learn.microsoft.com/azure/architecture/ai-ml/"
        focus = self._demo_focus(sub_question)
        keyword_text = ", ".join(search_keywords[:3])
        parsed = {
            "findings": [
                {
                    "fact": f"The {focus} dimension should be evaluated with explicit evidence, uncertainty, and human review checkpoints.",
                    "source": source,
                    "confidence": 0.78,
                },
                {
                    "fact": f"Relevant evaluation signals include {keyword_text}; together they map to product fit, feasibility, and risk.",
                    "source": "https://learn.microsoft.com/azure/architecture/guide/",
                    "confidence": 0.72,
                },
            ],
            "summary": (
                "The strongest answer will combine market evidence, architecture quality, "
                "responsible AI controls, and a clear operational workflow."
            ),
            "key_data_points": [
                "Evidence traceability is required for trustworthy research output.",
                "Human-in-the-loop review improves usability for high-stakes decisions.",
            ],
        }
        return parsed, json.dumps(parsed), [source, "https://learn.microsoft.com/azure/architecture/guide/"], 2

    def _demo_focus(self, sub_question: str) -> str:
        """Extract a readable focus phrase from a demo sub-question."""

        lowered = sub_question.lower()
        marker = "evaluate "
        if marker in lowered:
            start = lowered.index(marker) + len(marker)
            focus = sub_question[start:].strip().rstrip(".")
            return focus or "research"
        return "research"

    def _require_str(self, payload: Dict[str, Any], key: str) -> str:
        """Fetch a required string field from payload."""

        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Task payload must include {key}")
        return value.strip()

    def _require_str_list(self, payload: Dict[str, Any], key: str) -> List[str]:
        """Fetch a required list of strings from payload."""

        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Task payload must include {key} as list[str]")
        return [item.strip() for item in value if item.strip()]


async def run_researcher_test() -> None:
    """Run a standalone researcher test and print the findings JSON."""

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    router = LLMRouter(
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
    )
    search_client = TavilySearchClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
    bus = MessageBus(redis_url)
    researcher = ResearcherAgent(bus, router, search_client)

    task = TaskMessage(
        type=MessageType.TASK_ASSIGN,
        from_agent=AgentType.PLANNER,
        to_agent=AgentType.RESEARCHER,
        payload={
            "sub_question": "What is the current solar energy capacity in Vietnam?",
            "search_keywords": [
                "Vietnam solar energy capacity",
                "Vietnam solar power installed capacity",
                "Vietnam renewable energy statistics",
            ],
            "session_id": "researcher-test",
        },
        status=TaskStatus.PENDING,
        confidence=0.9,
        task_id=uuid4(),
        parent_task_id=None,
        depth=1,
    )

    result = await researcher.process(task)
    print(result.content)


if __name__ == "__main__":
    asyncio.run(run_researcher_test())
