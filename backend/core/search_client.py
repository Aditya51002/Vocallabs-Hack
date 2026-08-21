from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

try:
    import tavily
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    tavily = None
    TavilyClient = None
    TAVILY_AVAILABLE = False


class TavilySearchClient:
    """Async wrapper for the synchronous Tavily web search SDK client."""

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

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "advanced",
    ) -> List[Dict[str, Any]]:
        """Perform a single web search asynchronously using to_thread."""

        if not self.enabled:
            raise RuntimeError("TavilySearchClient is not enabled or API key is missing")

        def _sync_search():
            return self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
            )

        res = await asyncio.to_thread(_sync_search)
        results = res.get("results", [])

        normalized = []
        for r in results:
            normalized.append({
                "title": str(r.get("title", "")),
                "url": str(r.get("url", "")),
                "content": str(r.get("content", "")),
                "score": float(r.get("score", 0.0)),
            })
        return normalized

    async def search_many(
        self,
        queries: List[str],
        *,
        max_results_per_query: int = 4,
    ) -> List[Dict[str, Any]]:
        """Run multiple queries concurrently, deduplicating results by URL."""

        tasks = [
            self.search(q, max_results=max_results_per_query)
            for q in queries
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        unique_results: Dict[str, Dict[str, Any]] = {}
        for q, resp in zip(queries, responses):
            if isinstance(resp, Exception):
                self._logger.warning("Search failed for query %r: %s", q, resp)
                continue
            for item in resp:
                url = item["url"]
                if url not in unique_results:
                    unique_results[url] = item
                else:
                    if item["score"] > unique_results[url]["score"]:
                        unique_results[url] = item

        return list(unique_results.values())
