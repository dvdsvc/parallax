"""Thin Zhipu search_std adapter for the official ROMA v1 toolkit interface."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from roma_dspy.tools.base.base import BaseToolkit


class ZhipuSearchToolkit(BaseToolkit):
    """Expose exactly one tool: query -> Zhipu search_std -> results."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        search_engine: str = "search_std",
        count: int = 10,
        content_size: str = "medium",
        timeout: float = 30.0,
        enabled: bool = True,
        **config: Any,
    ) -> None:
        self.api_key = api_key or os.environ.get("GLM_API_KEY")
        self.base_url = (base_url or os.environ.get("GLM_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.search_engine = search_engine
        self.count = count
        self.content_size = content_size
        self.timeout = timeout
        super().__init__(enabled=enabled, **config)

    def _setup_dependencies(self) -> None:
        if not self.api_key:
            raise ValueError("GLM_API_KEY is required for ZhipuSearchToolkit")

    def _initialize_tools(self) -> None:
        pass

    async def web_search(self, query: str) -> dict[str, Any]:
        """Search with Zhipu search_std and return native results plus citations."""
        payload = {
            "search_query": query,
            "search_engine": self.search_engine,
            "search_intent": False,
            "count": self.count,
            "content_size": self.content_size,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/web_search",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("search_result", [])
        citations = [
            {"url": item.get("link"), "title": item.get("title", "")}
            for item in results
            if item.get("link")
        ]
        return {
            "success": True,
            "query": query,
            "provider": "zhipu",
            "search_engine": self.search_engine,
            "search_results": results,
            "results": results,
            "citations": citations,
        }


def register() -> None:
    """Register this external toolkit with ROMA's native ToolkitManager."""
    from roma_dspy.tools import register_toolkit

    register_toolkit(ZhipuSearchToolkit)
