"""LLM-assisted extraction using Crawl4AI's LLMExtractionStrategy.

This module is optional for MVP. It requires a compatible LLM provider and API token.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def extract_with_llm(
    url: str,
    provider: str = "openai/gpt-4o",
    api_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract structured meeting data using an LLM via Crawl4AI.

    Returns a dict with keys matching MeetingSchema. Requires valid provider credentials.
    """
    if not api_token:
        raise ValueError("An API token is required for LLM extraction.")

    from .llm_schemas import MeetingSchema  # local import inside package context

    try:
        from crawl4ai import (
            AsyncWebCrawler,
            CacheMode,
            CrawlerRunConfig,
            LLMConfig,
            LLMExtractionStrategy,
        )
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    except ImportError:
        # Return empty dict if crawl4ai is not available
        return {}

    import asyncio
    import json

    async def _run() -> Dict[str, Any]:
        md_gen = DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.4))
        run_conf = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=md_gen,
            extraction_strategy=LLMExtractionStrategy(
                llm_config=LLMConfig(provider=provider, api_token=api_token),
                schema=MeetingSchema.model_json_schema(),
                extraction_type="schema",
                instruction=(
                    "Extract meeting metadata including meeting name, meeting date and location. "
                    "For agenda/minutes/transcript fields, return the full text blocks if present. "
                    "For meetingItems return an array of items with fileNumber, title, type, "
                    "status if found."
                ),
                extra_args={"temperature": 0, "max_tokens": 1500},
            ),
        )
        async with AsyncWebCrawler() as crawler:
            res = await crawler.arun(url=url, config=run_conf)
            if not res.extracted_content:
                return {}
            return json.loads(res.extracted_content)

    return asyncio.run(_run())
