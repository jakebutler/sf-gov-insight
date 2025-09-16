"""CSS-based extraction helpers using Crawl4AI.

Note: CSS selectors are placeholders and must be tuned to the actual SF Supes pages.
We import Crawl4AI lazily inside functions to avoid import errors when the dependency
is not installed yet.
"""
from __future__ import annotations

from typing import Dict, Any


# Example CSS schema to extract a meeting items table.
MEETING_TABLE_SCHEMA: Dict[str, Any] = {
    "name": "meetingItems",
    "baseSelector": "table.meeting-items tr",  # TODO: tune selectors
    "fields": [
        {"name": "fileNumber", "selector": "td.file-number", "type": "text"},
        {"name": "ver", "selector": "td.ver", "type": "text"},
        {"name": "agendaNumber", "selector": "td.agenda-number", "type": "text"},
        {"name": "name", "selector": "td.name", "type": "text"},
        {"name": "type", "selector": "td.type", "type": "text"},
        {"name": "status", "selector": "td.status", "type": "text"},
        {"name": "title", "selector": "td.title", "type": "text"},
    ],
}


def extract_table_css(url: str) -> Dict[str, Any]:
    """Extract a meeting items table using Crawl4AI's JsonCssExtractionStrategy.

    Returns a dict parsed from JSON extraction content or an empty dict on failure.
    """
    import json
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
        from crawl4ai import JsonCssExtractionStrategy
    except Exception as e:
        raise RuntimeError(
            "crawl4ai is required for CSS extraction. Please `pip install crawl4ai`."
        ) from e

    async def _run() -> Dict[str, Any]:
        async with AsyncWebCrawler() as crawler:
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=JsonCssExtractionStrategy(MEETING_TABLE_SCHEMA),
            )
            res = await crawler.arun(url=url, config=config)
            if not res.extracted_content:
                return {}
            return json.loads(res.extracted_content)

    import asyncio
    return asyncio.run(_run())
