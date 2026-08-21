"""Search client with Tavily primary and DuckDuckGo async fallback."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List
from urllib.parse import urlparse

try:
    import tavily
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    tavily = None
    TavilyClient = None
    TAVILY_AVAILABLE = False

try:
    from duckduckgo_search import AsyncDDGS
    DDG_AVAILABLE = True
except ImportError:
    AsyncDDGS = None
    DDG_AVAILABLE = False

_CONTENT_TRUNCATE_CHARS = 400
_DEFAULT_MAX_RESULTS = 2  # reduced from 4 for token savings


def _domain_key(url: str) -> str:
    """Extract eTLD+1 from a URL for domain-level deduplication."""
    try:
        host = urlparse(url).hostname or url
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else host
    except Exception:
        return url


class TavilySearchClient:
    """Async wrapper for Tavily with DuckDuckGo fallback.

    search_many() never raises — on total failure it returns an empty list
    with each item's ``degraded`` field set to True. Callers must check for
    this flag and handle degraded-mode results appropriately.
    """

    def __init__(self, api_key: str = "") -> None:
        """Initialize the Tavily client if the SDK is available and key is provided."""

        self.api_key = api_key.strip()
        self.client = None
        self._logger = logging.getLogger("researchswarm.search_client")
        if TAVILY_AVAILABLE and self.api_key:
            self.client = TavilyClient(api_key=self.api_key)

    @property
    def enabled(self) -> bool:
        """Return True if Tavily is configured and client is active."""

        return bool(TAVILY_AVAILABLE and self.client is not None)

    @property
    def ddg_enabled(self) -> bool:
        """Return True if DuckDuckGo async search is available."""
        return bool(DDG_AVAILABLE and AsyncDDGS is not None)

    async def search(
        self,
        query: str,
        *,
        max_results: int = _DEFAULT_MAX_RESULTS,
        search_depth: str = "advanced",
    ) -> List[Dict[str, Any]]:
        """Perform a single web search via Tavily.

        Raises RuntimeError if Tavily is disabled.
        Use search_many() for fault-tolerant multi-query search with fallback.
        """

        if not self.enabled:
            raise RuntimeError("TavilySearchClient is not enabled or API key is missing")

        def _sync_search():
            return self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
            )

        res = await asyncio.to_thread(_sync_search)
        return self._normalize(res.get("results", []))

    async def _search_ddg(
        self, query: str, max_results: int = _DEFAULT_MAX_RESULTS
    ) -> List[Dict[str, Any]]:
        """Run a single query via DuckDuckGo async search."""

        if not self.ddg_enabled:
            raise RuntimeError("duckduckgo-search not available")

        async with AsyncDDGS() as ddgs:
            raw = await ddgs.atext(query, max_results=max_results)

        normalized = []
        for r in (raw or []):
            normalized.append({
                "title": str(r.get("title", "")),
                "url": str(r.get("href", r.get("url", ""))),
                "content": str(r.get("body", r.get("content", "")))[:_CONTENT_TRUNCATE_CHARS],
                "score": 0.3,  # DDG has no relevance score; use a conservative default
                "degraded": True,
            })
        return normalized

    async def _search_one(
        self, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Try Tavily first; fall back to DuckDuckGo on any failure."""

        if self.enabled:
            try:
                return await self.search(query, max_results=max_results)
            except Exception as exc:
                self._logger.warning(
                    "Tavily failed for query %r, trying DuckDuckGo: %s", query, exc
                )

        if self.ddg_enabled:
            try:
                return await self._search_ddg(query, max_results=max_results)
            except Exception as exc:
                self._logger.warning("DuckDuckGo also failed for query %r: %s", query, exc)

        return []

    async def search_many(
        self,
        queries: List[str],
        *,
        max_results_per_query: int = _DEFAULT_MAX_RESULTS,
    ) -> List[Dict[str, Any]]:
        """Run multiple queries concurrently, deduplicating results by URL and domain.

        Never raises. If all providers fail, returns an empty list.
        Results from DuckDuckGo fallback carry ``"degraded": True``.
        Domain-level dedup keeps only the highest-score result per eTLD+1.
        Content is truncated to 400 characters to reduce prompt token usage.
        """

        tasks = [
            self._search_one(q, max_results=max_results_per_query)
            for q in queries
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # First pass: URL-level dedup (keep highest score per URL)
        url_results: Dict[str, Dict[str, Any]] = {}
        for q, resp in zip(queries, responses):
            if isinstance(resp, Exception):
                self._logger.warning("Search error for query %r: %s", q, resp)
                continue
            for item in resp:
                url = item.get("url", "")
                if not url:
                    continue
                if url not in url_results or item.get("score", 0) > url_results[url].get("score", 0):
                    url_results[url] = item

        # Second pass: domain-level dedup (keep highest-score per domain)
        domain_results: Dict[str, Dict[str, Any]] = {}
        for url, item in url_results.items():
            domain = _domain_key(url)
            if domain not in domain_results or item.get("score", 0) > domain_results[domain].get("score", 0):
                domain_results[domain] = item

        return list(domain_results.values())

    def _normalize(self, results: List[Any]) -> List[Dict[str, Any]]:
        """Normalize raw Tavily results, truncating content field."""

        normalized = []
        for r in results:
            content = str(r.get("content", ""))
            normalized.append({
                "title": str(r.get("title", "")),
                "url": str(r.get("url", "")),
                "content": content[:_CONTENT_TRUNCATE_CHARS],
                "score": float(r.get("score", 0.0)),
                "degraded": False,
            })
        return normalized
