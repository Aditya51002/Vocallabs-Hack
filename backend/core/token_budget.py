"""Per-session token budget tracker backed by Redis.

Design:
  Key: session:{id}:tokens  (Redis integer, INCRBY)
  The counter is never decremented. Soft limit triggers reduced Writer
  output. Hard limit stops research and synthesizes from what exists.

Usage:
    tracker = TokenBudgetTracker(redis_client)
    await tracker.record(session_id, prompt_tokens=450, completion_tokens=120)
    if await tracker.is_over_hard_limit(session_id):
        # skip to writer immediately
    elif await tracker.is_over_soft_limit(session_id):
        # skip critic retry, short writer
"""

from __future__ import annotations

import logging
from typing import Optional

_TOKEN_KEY_TEMPLATE = "session:{session_id}:tokens"
_logger = logging.getLogger("researchswarm.token_budget")


class TokenBudgetTracker:
    """Tracks cumulative token usage per session in Redis.

    Limits:
        SOFT_LIMIT (9 000): skip Critic retry, reduce Writer to max_tokens=800.
        HARD_LIMIT (13 000): stop research phase immediately, synthesize from
                             whatever findings exist, mark budget_exhausted=True.

    Both limits are configurable at construction time to support testing
    with much smaller values (e.g., soft_limit=500 for a quick gate check).
    """

    SOFT_LIMIT: int = 9_000
    HARD_LIMIT: int = 13_000

    def __init__(
        self,
        redis_client,
        soft_limit: int = SOFT_LIMIT,
        hard_limit: int = HARD_LIMIT,
    ) -> None:
        self._redis = redis_client
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit

    def _key(self, session_id: str) -> str:
        return _TOKEN_KEY_TEMPLATE.format(session_id=session_id)

    async def record(
        self, session_id: str, prompt_tokens: int, completion_tokens: int
    ) -> int:
        """Increment the session token counter; return new total.

        Non-fatal: on Redis failure, logs warning and returns -1 so callers
        can decide whether to treat -1 as "unknown" or abort.
        """
        total = prompt_tokens + completion_tokens
        if total <= 0:
            return await self.get_total(session_id)
        try:
            new_total = await self._redis.incrby(self._key(session_id), total)
            _logger.debug(
                "Token record session=%s +%d => %d total", session_id, total, new_total
            )
            return new_total
        except Exception as exc:
            _logger.warning("TokenBudgetTracker.record failed session=%s: %s", session_id, exc)
            return -1

    async def get_total(self, session_id: str) -> int:
        """Return current token total for the session (0 on miss or error)."""
        try:
            raw = await self._redis.get(self._key(session_id))
            return int(raw) if raw is not None else 0
        except Exception as exc:
            _logger.warning("TokenBudgetTracker.get_total failed session=%s: %s", session_id, exc)
            return 0

    async def is_over_soft_limit(self, session_id: str) -> bool:
        """Return True when total tokens >= soft_limit."""
        return await self.get_total(session_id) >= self.soft_limit

    async def is_over_hard_limit(self, session_id: str) -> bool:
        """Return True when total tokens >= hard_limit."""
        return await self.get_total(session_id) >= self.hard_limit

    async def reset(self, session_id: str) -> None:
        """Delete the session token counter (for testing / cleanup)."""
        try:
            await self._redis.delete(self._key(session_id))
        except Exception as exc:
            _logger.warning("TokenBudgetTracker.reset failed session=%s: %s", session_id, exc)
