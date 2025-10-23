"""Search dispatching helpers."""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from ...configuration import Configuration
from ...utils import (
    advanced_search,
    deduplicate_and_format_sources,
    duckduckgo_search,
    format_sources,
    get_config_value,
    perplexity_search,
    searxng_search,
    tavily_search,
)

logger = logging.getLogger(__name__)

MAX_TOKENS_PER_SOURCE = 2000


def dispatch_search(
    query: str,
    config: Configuration,
    loop_count: int,
) -> Tuple[dict[str, Any] | None, list[str], Optional[str], str]:
    """Call the configured search backend and normalize the response."""

    search_api = get_config_value(config.search_api)
    notices: list[str] = []
    answer_text: Optional[str] = None
    backend_label = search_api

    if search_api == "tavily":
        result = tavily_search(
            query,
            fetch_full_page=config.fetch_full_page,
            max_results=5,
        )
    elif search_api == "perplexity":
        result = perplexity_search(
            query,
            perplexity_search_loop_count=loop_count,
        )
    elif search_api == "duckduckgo":
        result = duckduckgo_search(
            query,
            max_results=5,
            fetch_full_page=config.fetch_full_page,
        )
    elif search_api == "searxng":
        result = searxng_search(
            query,
            max_results=5,
            fetch_full_page=config.fetch_full_page,
        )
    elif search_api == "advanced":
        result = advanced_search(
            query,
            fetch_full_page=config.fetch_full_page,
        )
        if isinstance(result, dict):
            notices = list(result.get("notices") or [])
            answer_text = result.get("answer")
            backend_label = str(result.get("backend") or "advanced")
    else:
        raise ValueError(f"Unsupported search API: {config.search_api}")

    if answer_text is None and isinstance(result, dict):
        answer_text = result.get("answer")

    if isinstance(result, dict):
        results_len = len(result.get("results", []))
    elif isinstance(result, list):
        results_len = len(result)
    else:
        results_len = "?"

    if notices:
        for notice in notices:
            logger.info("Search notice (%s): %s", backend_label, notice)
    logger.info(
        "Search backend=%s resolved_backend=%s answer=%s results=%s",
        search_api,
        backend_label,
        bool(answer_text),
        results_len,
    )

    return result, notices, answer_text, backend_label


def prepare_research_context(
    search_result: dict[str, Any] | None,
    answer_text: Optional[str],
    config: Configuration,
) -> tuple[str, str]:
    """Format sources and research context for downstream summarization."""

    sources_summary = format_sources(search_result)
    context = deduplicate_and_format_sources(
        search_result,
        max_tokens_per_source=MAX_TOKENS_PER_SOURCE,
        fetch_full_page=config.fetch_full_page,
    )

    if answer_text:
        context = f"AI直接答案：\n{answer_text}\n\n{context}"

    return sources_summary, context

