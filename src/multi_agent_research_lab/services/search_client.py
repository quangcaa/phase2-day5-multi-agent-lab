"""Search client abstraction for ResearcherAgent."""

import logging

from tavily import TavilyClient

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

logger = logging.getLogger(__name__)


class SearchClient:
    """Search client backed by Tavily API with mock fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._tavily: TavilyClient | None = None
        if self.settings.tavily_api_key:
            self._tavily = TavilyClient(api_key=self.settings.tavily_api_key)

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query."""

        if self._tavily is None:
            logger.warning("No TAVILY_API_KEY set – returning mock results")
            return self._mock_search(query, max_results)

        logger.info("Tavily search  query=%r  max_results=%d", query, max_results)

        raw = self._tavily.search(query=query, max_results=max_results)
        results: list[SourceDocument] = []
        for item in raw.get("results", []):
            results.append(
                SourceDocument(
                    title=item.get("title", "Untitled"),
                    url=item.get("url"),
                    snippet=item.get("content", ""),
                    metadata={"score": item.get("score", 0)},
                )
            )

        logger.info("Tavily returned %d results", len(results))
        return results

    @staticmethod
    def _mock_search(query: str, max_results: int) -> list[SourceDocument]:
        """Return placeholder results for dev/testing without API key."""

        return [
            SourceDocument(
                title=f"Mock result {i + 1} for: {query[:50]}",
                url=f"https://example.com/mock/{i + 1}",
                snippet=f"This is a mock search snippet #{i + 1} related to '{query[:80]}'.",
                metadata={"mock": True},
            )
            for i in range(min(max_results, 3))
        ]
