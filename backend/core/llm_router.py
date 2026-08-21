from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from core.types import AgentType


@dataclass
class TokenUsage:
    """Token usage data returned by an LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider: str = ""

    @property
    def total_tokens(self) -> int:
        """Sum of prompt and completion tokens."""
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResult:
    """Result from an LLM call, bundling text output with token usage."""

    text: str
    usage: TokenUsage = field(default_factory=TokenUsage)

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
        groq_model: str = "qwen/qwen3.6-27b",
        groq_model_small: str = "qwen/qwen3.6-27b",
        gemini_model: str = "gemini-3.6-flash",
        groq_rpm_budget: int = 28,
        gemini_rpm_budget: int = 14,
        agent_provider_map: Optional[Dict[AgentType, List[str]]] = None,
    ) -> None:
        """Initialize LLMRouter with client configs and load tracking budgets."""

        self.groq_api_key = groq_api_key.strip()
        self.gemini_api_key = gemini_api_key.strip()
        self.groq_model = groq_model
        self.groq_model_small = groq_model_small
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

        # Agents that should use the smaller/cheaper Groq model.
        self._small_model_agents = {AgentType.PLANNER, AgentType.RESEARCHER, AgentType.CRITIC}

        self.groq_client = None
        self.gemini_client = None

        if GROQ_AVAILABLE and self.groq_api_key:
            self.groq_client = AsyncGroq(api_key=self.groq_api_key)
        if GEMINI_AVAILABLE and self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)

        self._calls: Dict[str, List[float]] = {"groq": [], "gemini": []}
        self._budgets = {"groq": self.groq_rpm_budget, "gemini": self.gemini_rpm_budget}
        self._researcher_counter = 0
        self._last_usage: TokenUsage = TokenUsage()
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

    def _groq_model_for(self, agent_type: Optional[AgentType]) -> str:
        """Select groq_model_small for low-complexity agents, groq_model otherwise."""
        if agent_type in self._small_model_agents:
            return self.groq_model_small
        return self.groq_model

    def get_last_usage(self) -> TokenUsage:
        """Return token usage from the most recent complete() or stream() call."""
        return self._last_usage

    async def complete(
        self,
        system: str,
        user_content: str,
        *,
        agent_type: Optional[AgentType] = None,
        max_tokens: int = 1200,
        temperature: float = 0.3,
    ) -> LLMResult:
        """Execute a text completion, automatically falling back on error.

        Returns LLMResult with .text and .usage (real token counts from provider).
        Callers that only need text should use result.text.
        """

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
                    candidate_models = [self._groq_model_for(agent_type), "qwen/qwen3.6-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
                    seen = set()
                    last_g_err = None
                    for g_model in candidate_models:
                        if not g_model or g_model in seen:
                            continue
                        seen.add(g_model)
                        try:
                            response = await self.groq_client.chat.completions.create(
                                model=g_model,
                                messages=[
                                    {"role": "system", "content": system},
                                    {"role": "user", "content": user_content},
                                ],
                                max_tokens=max_tokens,
                                temperature=temperature,
                                stream=False,
                            )
                            content = response.choices[0].message.content or ""
                            # If model produces thought tags (like Qwen), strip thinking block if JSON is expected
                            if "<think>" in content and "</think>" in content:
                                end_think = content.rfind("</think>") + len("</think>")
                                content = content[end_think:].strip()
                            usage = TokenUsage(
                                prompt_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
                                completion_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
                                provider="groq",
                            )
                            self._last_usage = usage
                            return LLMResult(text=content, usage=usage)
                        except Exception as g_err:
                            last_g_err = g_err
                            continue
                    if last_g_err:
                        raise last_g_err
                elif provider == "gemini":
                    if not self.gemini_client:
                        raise RuntimeError("Gemini client not initialized")
                    candidate_models = [self.gemini_model, "gemini-3.6-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]
                    seen = set()
                    last_m_err = None
                    for m_model in candidate_models:
                        if not m_model or m_model in seen:
                            continue
                        seen.add(m_model)
                        try:
                            response = await self.gemini_client.aio.models.generate_content(
                                model=m_model,
                                contents=user_content,
                                config=genai_types.GenerateContentConfig(
                                    system_instruction=system,
                                    temperature=temperature,
                                    max_output_tokens=max_tokens,
                                )
                            )
                            meta = getattr(response, "usage_metadata", None)
                            usage = TokenUsage(
                                prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                                completion_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                                provider="gemini",
                            )
                            self._last_usage = usage
                            return LLMResult(text=response.text or "", usage=usage)
                        except Exception as m_err:
                            last_m_err = m_err
                            continue
                    if last_m_err:
                        raise last_m_err
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
        """Stream a text generation, falling back if the initial call fails.

        Token usage is captured from the final chunk of each provider and
        stored in self._last_usage / accessible via get_last_usage().
        """

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
                    candidate_models = [self._groq_model_for(agent_type), "qwen/qwen3.6-27b", "openai/gpt-oss-120b"]
                    for g_model in candidate_models:
                        try:
                            response = await self.groq_client.chat.completions.create(
                                model=g_model,
                                messages=[
                                    {"role": "system", "content": system},
                                    {"role": "user", "content": user_content},
                                ],
                                max_tokens=max_tokens,
                                temperature=temperature,
                                stream=True,
                                stream_options={"include_usage": True},
                            )
                            async for chunk in response:
                                content = chunk.choices[0].delta.content if chunk.choices else None
                                if content:
                                    yielded_any = True
                                    yield content
                                if chunk.usage:
                                    self._last_usage = TokenUsage(
                                        prompt_tokens=getattr(chunk.usage, "prompt_tokens", 0) or 0,
                                        completion_tokens=getattr(chunk.usage, "completion_tokens", 0) or 0,
                                        provider="groq",
                                    )
                            return
                        except Exception:
                            if yielded_any:
                                raise
                            continue
                elif provider == "gemini":
                    if not self.gemini_client:
                        raise RuntimeError("Gemini client not initialized")
                    candidate_models = [self.gemini_model, "gemini-3.6-flash", "gemini-flash-latest"]
                    for m_model in candidate_models:
                        try:
                            response = await self.gemini_client.aio.models.generate_content_stream(
                                model=m_model,
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
                                meta = getattr(chunk, "usage_metadata", None)
                                if meta and getattr(meta, "prompt_token_count", None):
                                    self._last_usage = TokenUsage(
                                        prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                                        completion_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                                        provider="gemini",
                                    )
                            return
                        except Exception:
                            if yielded_any:
                                raise
                            continue
            except Exception as exc:
                self._logger.warning("Provider %s stream failed: %s", provider, exc)
                if yielded_any:
                    raise
                errors.append(f"{provider}: {exc}")
                continue

        raise RuntimeError(f"All providers failed in stream: {'; '.join(errors)}")

    async def vision_complete(
        self,
        image_bytes: bytes,
        image_hash: str,
        *,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Single Gemini vision call for image analysis (Step 5)."""
        if not self.gemini_client or not GEMINI_AVAILABLE:
            raise RuntimeError("Gemini client not configured; vision not available")

        if not genai_types:
            raise RuntimeError("google-genai types not available")

        vision_prompt = (
            "Analyze this image and return a JSON object. "
            "If it is a document, screenshot, or contains text: extract OCR text as findings. "
            "If it is a chart or photo: describe key data points as structured findings. "
            "Return JSON only: {\"findings\": [{\"fact\": str, \"confidence\": float}], "
            "\"content_type\": \"ocr\" | \"chart\" | \"photo\"}"
        )

        import base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        self._record_call("gemini")
        candidate_models = [self.gemini_model, "gemini-3.6-flash", "gemini-flash-latest"]
        last_err = None
        response = None
        for m_model in candidate_models:
            try:
                response = await asyncio.wait_for(
                    self.gemini_client.aio.models.generate_content(
                        model=m_model,
                        contents=[
                            {
                                "parts": [
                                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                                    {"text": vision_prompt},
                                ]
                            }
                        ],
                        config=genai_types.GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=800,
                        ),
                    ),
                    timeout=timeout,
                )
                break
            except Exception as v_err:
                last_err = v_err
                continue

        if response is None:
            raise RuntimeError(f"Vision call failed: {last_err}") from last_err

        import json as _json
        text = response.text or ""
        try:
            # Strip code fence if present
            stripped = text.strip()
            if stripped.startswith("```"):
                first_nl = stripped.find("\n")
                stripped = stripped[first_nl:].strip() if first_nl != -1 else stripped[3:].strip()
                if stripped.endswith("```"):
                    stripped = stripped[:-3].strip()
            parsed = _json.loads(stripped)
        except (_json.JSONDecodeError, Exception):
            parsed = {"findings": [{"fact": text, "confidence": 0.5}], "content_type": "unknown"}

        meta = getattr(response, "usage_metadata", None)
        usage = TokenUsage(
            prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(meta, "candidates_token_count", 0) or 0,
            provider="gemini",
        )
        self._last_usage = usage

        return {
            "findings": [
                {
                    **f,
                    "source": f"user-upload:{image_hash}",
                }
                for f in parsed.get("findings", [])
                if isinstance(f, dict)
            ],
            "source": f"user-upload:{image_hash}",
            "content_type": parsed.get("content_type", "unknown"),
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
            },
        }

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "recording.webm",
        timeout: float = 60.0,
    ) -> str:
        """Transcribe an audio buffer using Groq Whisper API (whisper-large-v3).

        Args:
            audio_bytes: Raw audio bytes.
            filename: Virtual filename with extension for mime detection.
            timeout: Timeout in seconds for the transcription request.

        Returns:
            Transcribed text string.
        """
        if not self.groq_client:
            raise RuntimeError("Groq is not configured; voice transcription unavailable")

        try:
            transcription = await asyncio.wait_for(
                self.groq_client.audio.transcriptions.create(
                    file=(filename, audio_bytes),
                    model="whisper-large-v3",
                    response_format="json",
                    temperature=0.0,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Voice transcription timed out") from exc

        if hasattr(transcription, "text"):
            return transcription.text.strip()
        if isinstance(transcription, dict):
            return str(transcription.get("text", "")).strip()
        return str(transcription).strip()
