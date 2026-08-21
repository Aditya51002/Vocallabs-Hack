"""Redis-backed research result cache for ResearchSwarm.

Keys sub-namespace: cache:research:{sha256} (TTL 3600s)
                    cache:image:{sha256}     (TTL 3600s)

The cache is keyed on normalized sub_question + sorted keywords so
identical questions asked in different sessions or retry rounds return
the cached result without triggering another search + LLM call.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

_CACHE_TTL_SECONDS = 3600
_RESEARCH_KEY_PREFIX = "cache:research:"
_IMAGE_KEY_PREFIX = "cache:image:"

_logger = logging.getLogger("researchswarm.cache")


class ResearchCache:
    """Content-addressed Redis cache for researcher and vision results.

    Usage:
        cache = ResearchCache(redis_client)

        # Research
        hit = await cache.get(sub_question, keywords)
        if hit is None:
            result = ... # run search + LLM
            await cache.set(sub_question, keywords, result)

        # Vision / image
        hit = await cache.get_image(image_hash)
        if hit is None:
            result = ... # run vision call
            await cache.set_image(image_hash, result)
    """

    def __init__(self, redis_client, ttl: int = _CACHE_TTL_SECONDS) -> None:
        """Initialise the cache with an async redis client and TTL in seconds."""
        self._redis = redis_client
        self._ttl = ttl

    # ------------------------------------------------------------------
    # Research cache
    # ------------------------------------------------------------------

    def _make_research_key(self, sub_question: str, keywords: List[str]) -> str:
        """Content-address a research request by question + sorted keywords."""
        normalized_q = sub_question.lower().strip()
        kw_str = json.dumps(sorted(k.lower().strip() for k in keywords if k))
        digest = hashlib.sha256((normalized_q + kw_str).encode()).hexdigest()
        return _RESEARCH_KEY_PREFIX + digest

    async def get(
        self, sub_question: str, keywords: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Return cached research result or None on miss."""
        key = self._make_research_key(sub_question, keywords)
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            result = json.loads(raw)
            _logger.debug("Cache HIT research key=%s", key[-8:])
            return result
        except Exception as exc:
            _logger.warning("Cache get failed (key=%s): %s", key[-8:], exc)
            return None

    async def set(
        self, sub_question: str, keywords: List[str], result: Dict[str, Any]
    ) -> None:
        """Store a research result in the cache with TTL."""
        key = self._make_research_key(sub_question, keywords)
        try:
            await self._redis.set(key, json.dumps(result), ex=self._ttl)
            _logger.debug("Cache SET research key=%s ttl=%ds", key[-8:], self._ttl)
        except Exception as exc:
            # Cache write failures are non-fatal — log and continue.
            _logger.warning("Cache set failed (key=%s): %s", key[-8:], exc)

    # ------------------------------------------------------------------
    # Image / vision cache
    # ------------------------------------------------------------------

    def _make_image_key(self, image_hash: str) -> str:
        """Build image cache key from pre-computed sha256 hex digest."""
        return _IMAGE_KEY_PREFIX + image_hash

    async def get_image(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """Return cached vision result or None on miss."""
        key = self._make_image_key(image_hash)
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            result = json.loads(raw)
            _logger.debug("Cache HIT image hash=%s", image_hash[:8])
            return result
        except Exception as exc:
            _logger.warning("Cache get_image failed (hash=%s): %s", image_hash[:8], exc)
            return None

    async def set_image(self, image_hash: str, result: Dict[str, Any]) -> None:
        """Store a vision result in the cache with TTL."""
        key = self._make_image_key(image_hash)
        try:
            await self._redis.set(key, json.dumps(result), ex=self._ttl)
            _logger.debug("Cache SET image hash=%s ttl=%ds", image_hash[:8], self._ttl)
        except Exception as exc:
            _logger.warning("Cache set_image failed (hash=%s): %s", image_hash[:8], exc)
