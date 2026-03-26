"""
Web Search Tool: Search the web using DuckDuckGo.

No API key required. Returns top search results with
title, snippet, and URL.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import BaseTool, ToolResult


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    snippet: str
    url: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
        }


class WebSearchTool(BaseTool):
    """
    Search the web using DuckDuckGo.

    Features:
    - No API key required
    - Returns top N results (default 5)
    - Includes title, snippet, and URL
    - Handles rate limiting gracefully
    """

    def __init__(
        self,
        max_results: int = 5,
        region: str = "wt-wt",
        timeout_seconds: float = 10.0,
    ):
        """
        Initialize web search tool.

        Args:
            max_results: Maximum number of results to return
            region: DuckDuckGo region code (wt-wt = worldwide)
            timeout_seconds: Request timeout
        """
        super().__init__(timeout_seconds=timeout_seconds)
        self._max_results = max_results
        self._region = region

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information. "
            "Use this to find recent news, facts, or information "
            "that may not be in the training data."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": f"Maximum results to return (default: {self._max_results})",
                },
            },
            "required": ["query"],
        }

    def validate(self, **kwargs) -> tuple[bool, str | None]:
        query = kwargs.get("query", "")
        if not query or not query.strip():
            return False, "Search query cannot be empty"
        if len(query) > 500:
            return False, "Search query too long (max 500 characters)"
        return True, None

    async def execute(self, query: str, max_results: int | None = None) -> ToolResult:
        """
        Execute web search.

        Args:
            query: Search query
            max_results: Override default max results

        Returns:
            ToolResult with list of search results
        """
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return ToolResult.fail(
                error="duckduckgo-search package not installed. Run: pip install duckduckgo-search",
                tool_name=self.name,
            )

        num_results = max_results or self._max_results

        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(
                    query,
                    region=self._region,
                    max_results=num_results,
                ))

            if not raw_results:
                return ToolResult.ok(
                    data=[],
                    tool_name=self.name,
                    query=query,
                    result_count=0,
                )

            results = [
                SearchResult(
                    title=r.get("title", ""),
                    snippet=r.get("body", ""),
                    url=r.get("href", ""),
                ).to_dict()
                for r in raw_results
            ]

            return ToolResult.ok(
                data=results,
                tool_name=self.name,
                query=query,
                result_count=len(results),
            )

        except Exception as e:
            return ToolResult.fail(
                error=f"Search failed: {str(e)}",
                tool_name=self.name,
            )

    def format_results(self, result: ToolResult) -> str:
        """Format search results for display or LLM consumption."""
        if not result.success:
            return f"Search failed: {result.error}"

        if not result.data:
            return "No results found."

        lines = [f"Found {len(result.data)} results:\n"]
        for i, r in enumerate(result.data, 1):
            lines.append(f"{i}. **{r['title']}**")
            lines.append(f"   {r['snippet']}")
            lines.append(f"   URL: {r['url']}\n")

        return "\n".join(lines)
