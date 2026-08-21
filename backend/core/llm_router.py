from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, AsyncIterator

from core.types import AgentType

try:
    import groq
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    groq = None
    AsyncGroq = None
    GROQ_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    genai_types = None
    GEMINI_AVAILABLE = False


class LLMRouter:
    """Routes LLM calls to Groq or Gemini based on agent type, load, and availability."""

    def __init__(
        self,
        groq_api_key: str = "",
        gemini_api_key: str = "",
        groq_model: str = "llama-3.3-70b-versatile",
        gemini_model: str = "gemini-2.0-flash",
        groq_rpm_budget: int = 28,
        gemini_rpm_budget: int = 14,
        agent_provider_map: Optional[Dict[AgentType, List[str]]] = None,
    ) -> None:
        """Initialize LLMRouter with client configs and load tracking budgets."""

        self.groq_api_key = groq_api_key.strip()
        self.gemini_api_key = gemini_api_key.strip()
        self.groq_model = groq_model
        self.gemini_model = gemini_model
        self.groq_rpm_budget = groq_rpm_budget
        self.gemini_rpm_budget = gemini_rpm_budget

        self._default_map = {
            AgentType.PLANNER: ["groq", "gemini"],
            AgentType.CRITIC: ["groq", "gemini"],
            AgentType.ANALYST: ["gemini", "groq"],
            AgentType.WRITER: ["gemini", "groq"],
            AgentType.RESEARCHER: ["groq", "gemini"],
        }
        self.agent_provider_map = agent_provider_map or self._default_map

        self.groq_client = None
        self.gemini_client = None

        if GROQ_AVAILABLE and self.groq_api_key:
            self.groq_client = AsyncGroq(api_key=self.groq_api_key)
        if GEMINI_AVAILABLE and self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)

        self._calls: Dict[str, List[float]] = {"groq": [], "gemini": []}
        self._budgets = {"groq": self.groq_rpm_budget, "gemini": self.gemini_rpm_budget}
        self._researcher_counter = 0
        self._logger = logging.getLogger("researchswarm.llm_router")

    def is_configured(self, provider: str) -> bool:
        """Check if a provider is fully installed and has an API key configured."""

        if provider == "groq":
            return bool(GROQ_AVAILABLE and self.groq_api_key)
        elif provider == "gemini":
            return bool(GEMINI_AVAILABLE and self.gemini_api_key)
        return False

    def available_providers(self) -> List[str]:
        """List currently configured and available providers."""

        providers = []
        if self.is_configured("groq"):
            providers.append("groq")
        if self.is_configured("gemini"):
            providers.append("gemini")
        return providers

    def _record_call(self, provider: str) -> None:
        """Record a call timestamp for sliding window tracking."""

        if provider in self._calls:
            self._calls[provider].append(time.time())

    def get_load(self, provider: str) -> int:
        """Calculate load count for provider in the last 60 seconds, capped at budget."""

        now = time.time()
        cutoff = now - 60.0
        if provider in self._calls:
            self._calls[provider] = [t for t in self._calls[provider] if t > cutoff]
            recent = len(self._calls[provider])
            budget = self._budgets.get(provider, 9999)
            return min(recent, budget)
        return 0

    def provider_load_snapshot(self) -> Dict[str, int]:
        """Get recent call counts for all providers (observability)."""

        snapshot = {}
        for p in ["groq", "gemini"]:
            now = time.time()
            cutoff = now - 60.0
            if p in self._calls:
                self._calls[p] = [t for t in self._calls[p] if t > cutoff]
                snapshot[p] = len(self._calls[p])
            else:
                snapshot[p] = 0
        return snapshot

    def _order_for(self, agent_type: Optional[AgentType]) -> List[str]:
        """Compute the order of providers to try for a given agent type."""

        if not agent_type:
            preferred = ["groq", "gemini"]
        else:
            preferred = list(self.agent_provider_map.get(agent_type, ["groq", "gemini"]))

        configured = [p for p in preferred if self.is_configured(p)]

        if agent_type == AgentType.RESEARCHER:
            cnt = self._researcher_counter
            self._researcher_counter += 1
            if cnt % 2 == 1:
                configured.reverse()

        # Sort by load (ascending, stable sort preserves preferred ordering on equal load)
        configured.sort(key=lambda p: self.get_load(p))
        return configured

    async def complete(
        self,
        system: str,
        user_content: str,
        *,
        agent_type: Optional[AgentType] = None,
        max_tokens: int = 1200,
        temperature: float = 0.3,
    ) -> str:
        """Execute a text completion, automatically falling back on error."""

        provider_order = self._order_for(agent_type)
        if not provider_order:
            raise RuntimeError("No configured LLM providers available")

        errors = []
        for provider in provider_order:
            try:
                self._record_call(provider)
                if provider == "groq":
                    if not self.groq_client:
                        raise RuntimeError("Groq client not initialized")
                    response = await self.groq_client.chat.completions.create(
                        model=self.groq_model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user_content},
                        ],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=False,
                    )
                    content = response.choices[0].message.content
                    return content or ""
                elif provider == "gemini":
                    if not self.gemini_client:
                        raise RuntimeError("Gemini client not initialized")
                    response = await self.gemini_client.aio.models.generate_content(
                        model=self.gemini_model,
                        contents=user_content,
                        config=genai_types.GenerateContentConfig(
                            system_instruction=system,
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                        )
                    )
                    return response.text or ""
            except Exception as exc:
                self._logger.warning("Provider %s complete call failed: %s", provider, exc)
                errors.append(f"{provider}: {exc}")
                continue

        raise RuntimeError(f"All providers failed in complete: {'; '.join(errors)}")

    async def stream(
        self,
        system: str,
        user_content: str,
        *,
        agent_type: Optional[AgentType] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream a text generation, falling back if the initial call fails."""

        provider_order = self._order_for(agent_type)
        if not provider_order:
            raise RuntimeError("No configured LLM providers available")

        errors = []
        for provider in provider_order:
            yielded_any = False
            try:
                self._record_call(provider)
                if provider == "groq":
                    if not self.groq_client:
                        raise RuntimeError("Groq client not initialized")
                    response = await self.groq_client.chat.completions.create(
                        model=self.groq_model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user_content},
                        ],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=True,
                    )
                    async for chunk in response:
                        content = chunk.choices[0].delta.content
                        if content:
                            yielded_any = True
                            yield content
                    return
                elif provider == "gemini":
                    if not self.gemini_client:
                        raise RuntimeError("Gemini client not initialized")
                    response = await self.gemini_client.aio.models.generate_content_stream(
                        model=self.gemini_model,
                        contents=user_content,
                        config=genai_types.GenerateContentConfig(
                            system_instruction=system,
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                        )
                    )
                    async for chunk in response:
                        if chunk.text:
                            yielded_any = True
                            yield chunk.text
                    return
            except Exception as exc:
                self._logger.warning("Provider %s stream failed: %s", provider, exc)
                if yielded_any:
                    # Do not retry another provider if we have already yielded content
                    raise
                errors.append(f"{provider}: {exc}")
                continue

        raise RuntimeError(f"All providers failed in stream: {'; '.join(errors)}")
