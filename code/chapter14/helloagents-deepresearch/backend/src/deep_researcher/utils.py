import os
import logging
import httpx
import requests
from typing import Dict, Any, List, Union, Optional

from markdownify import markdownify
from langsmith import traceable
from tavily import TavilyClient
from ddgs import DDGS
from ddgs.exceptions import DDGSException


logger = logging.getLogger(__name__)

# Constants
CHARS_PER_TOKEN = 4


def get_config_value(value: Any) -> str:
    """
    Convert configuration values to string format, handling both string and enum types.

    Args:
        value (Any): The configuration value to process. Can be a string or an Enum.

    Returns:
        str: The string representation of the value.

    Examples:
        >>> get_config_value("tavily")
        'tavily'
        >>> get_config_value(SearchAPI.TAVILY)
        'tavily'
    """
    return value if isinstance(value, str) else value.value


def strip_thinking_tokens(text: str) -> str:
    """
    Remove <think> and </think> tags and their content from the text.

    Iteratively removes all occurrences of content enclosed in thinking tokens.

    Args:
        text (str): The text to process

    Returns:
        str: The text with thinking tokens and their content removed
    """
    while "<think>" in text and "</think>" in text:
        start = text.find("<think>")
        end = text.find("</think>") + len("</think>")
        text = text[:start] + text[end:]
    return text


def deduplicate_and_format_sources(
    search_response: Union[Dict[str, Any], List[Dict[str, Any]]],
    max_tokens_per_source: int,
    fetch_full_page: bool = False,
) -> str:
    """
    Format and deduplicate search responses from various search APIs.

    Takes either a single search response or list of responses from search APIs,
    deduplicates them by URL, and formats them into a structured string.

    Args:
        search_response (Union[Dict[str, Any], List[Dict[str, Any]]]): Either:
            - A dict with a 'results' key containing a list of search results
            - A list of dicts, each containing search results
        max_tokens_per_source (int): Maximum number of tokens to include for each source's content
        fetch_full_page (bool, optional): Whether to include the full page content. Defaults to False.

    Returns:
        str: Formatted string with deduplicated sources

    Raises:
        ValueError: If input is neither a dict with 'results' key nor a list of search results
    """
    # Convert input to list of results
    if isinstance(search_response, dict):
        sources_list = search_response["results"]
    elif isinstance(search_response, list):
        sources_list = []
        for response in search_response:
            if isinstance(response, dict) and "results" in response:
                sources_list.extend(response["results"])
            else:
                sources_list.extend(response)
    else:
        raise ValueError(
            "Input must be either a dict with 'results' or a list of search results"
        )

    # Deduplicate by URL
    unique_sources = {}
    for source in sources_list:
        if source["url"] not in unique_sources:
            unique_sources[source["url"]] = source

    # Format output text
    formatted_text = ""
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"信息来源: {source['title']}\n\n"
        formatted_text += f"URL: {source['url']}\n\n"
        formatted_text += (
            f"信息内容: {source['content']}\n\n"
        )
        if fetch_full_page:
            # Using rough estimate of characters per token
            char_limit = max_tokens_per_source * CHARS_PER_TOKEN
            # Handle None raw_content
            raw_content = source.get("raw_content", "")
            if raw_content is None:
                raw_content = ""
                print(f"Warning: No raw_content found for source {source['url']}")
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"详细信息内容限制为 {max_tokens_per_source} 个 token: {raw_content}\n\n"

    return formatted_text.strip()


def format_sources(search_results: Dict[str, Any]) -> str:
    """Format search results into a bullet-point list of sources with URLs.

    Creates a simple bulleted list of search results with title and URL for each source.

    Args:
        search_results (Dict[str, Any]): Search response containing a 'results' key with
                                        a list of search result objects

    Returns:
        str: Formatted string with sources as bullet points in the format "* title : url"
    """
    return "\n".join(
        f"* {source['title']} : {source['url']}" for source in search_results["results"]
    )


def fetch_raw_content(url: str) -> Optional[str]:
    """
    Fetch HTML content from a URL and convert it to markdown format.

    Uses a 10-second timeout to avoid hanging on slow sites or large pages.

    Args:
        url (str): The URL to fetch content from

    Returns:
        Optional[str]: The fetched content converted to markdown if successful,
                      None if any error occurs during fetching or conversion
    """
    try:
        # Create a client with reasonable timeout
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return markdownify(response.text)
    except Exception as e:
        print(f"Warning: Failed to fetch full page content for {url}: {str(e)}")
        return None


@traceable
def duckduckgo_search(
    query: str, max_results: int = 3, fetch_full_page: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """Search the web using DuckDuckGo and return formatted results.

    Uses the DDGS library to perform web searches through DuckDuckGo.

    Args:
        query (str): The search query to execute
        max_results (int, optional): Maximum number of results to return. Defaults to 3.
        fetch_full_page (bool, optional): Whether to fetch full page content from result URLs.
                                         Defaults to False.

    Returns:
        Dict[str, List[Dict[str, Any]]]: Search response containing:
            - results (list): List of search result dictionaries, each containing:
                - title (str): Title of the search result
                - url (str): URL of the search result
                - content (str): Snippet/summary of the content
                - raw_content (str or None): Full page content if fetch_full_page is True,
                                            otherwise same as content
    """
    try:
        with DDGS(timeout=10) as client:
            search_results = client.text(
                query,
                max_results=max_results,
                backend="duckduckgo",
            )

        results: list[dict[str, Any]] = []
        for entry in search_results:
            url = entry.get("href") or entry.get("url")
            title = entry.get("title") or url
            content = entry.get("body") or entry.get("content")

            if not all([url, title, content]):
                print(f"Warning: Incomplete result from DuckDuckGo: {entry}")
                continue

            raw_content = content
            if fetch_full_page:
                fetched = fetch_raw_content(url)
                raw_content = fetched if fetched is not None else content

            results.append(
                {
                    "title": title,
                    "url": url,
                    "content": content,
                    "raw_content": raw_content,
                }
            )

        return {"results": results}
    except DDGSException as exc:
        print(f"Error in DuckDuckGo search: {str(exc)}")
        print("Full error details: DDGSException")
        return {"results": []}
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Unexpected error in DuckDuckGo search: {str(exc)}")
        print(f"Full error details: {type(exc).__name__}")
        return {"results": []}


@traceable
def searxng_search(
    query: str, max_results: int = 3, fetch_full_page: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search the web using SearXNG and return formatted results.

    Uses the SearXNG JSON API (`/search?format=json`) to执行检索。
    The SearXNG host URL is read from the SEARXNG_URL environment variable
    or defaults to http://localhost:8888.

    Args:
        query (str): The search query to execute
        max_results (int, optional): Maximum number of results to return. Defaults to 3.
        fetch_full_page (bool, optional): Whether to fetch full page content from result URLs.
                                         Defaults to False.

    Returns:
        Dict[str, List[Dict[str, Any]]]: Search response containing:
            - results (list): List of search result dictionaries, each containing:
                - title (str): Title of the search result
                - url (str): URL of the search result
                - content (str): Snippet/summary of the content
                - raw_content (str or None): Full page content if fetch_full_page is True,
                                           otherwise same as content
    """
    host = os.environ.get("SEARXNG_URL", "http://localhost:8888")
    endpoint = f"{host.rstrip('/')}/search"

    try:
        response = requests.get(
            endpoint,
            params={
                "q": query,
                "format": "json",
                "language": "zh-CN",
                "safesearch": 1,
                "categories": "general",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - 远程接口失败兜底
        logger.warning("SearXNG request failed: %s", exc)
        return {"results": []}

    results = []
    for entry in payload.get("results", [])[:max_results]:
        url = entry.get("url") or entry.get("link")
        title = entry.get("title") or url
        content = entry.get("content") or entry.get("snippet") or ""

        if not all([url, title]) or not content:
            logger.debug("Skipping incomplete SearXNG result: %s", entry)
            continue

        raw_content = content
        if fetch_full_page:
            fetched = fetch_raw_content(url)
            raw_content = fetched if fetched is not None else content

        results.append(
            {
                "title": title,
                "url": url,
                "content": content,
                "raw_content": raw_content,
            }
        )

    return {"results": results}


@traceable
def tavily_search(
    query: str, fetch_full_page: bool = True, max_results: int = 3
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search the web using the Tavily API and return formatted results.

    Uses the TavilyClient to perform searches. Tavily API key must be configured
    in the environment.

    Args:
        query (str): The search query to execute
        fetch_full_page (bool, optional): Whether to include raw content from sources.
                                         Defaults to True.
        max_results (int, optional): Maximum number of results to return. Defaults to 3.

    Returns:
        Dict[str, List[Dict[str, Any]]]: Search response containing:
            - results (list): List of search result dictionaries, each containing:
                - title (str): Title of the search result
                - url (str): URL of the search result
                - content (str): Snippet/summary of the content
                - raw_content (str or None): Full content of the page if available and
                                            fetch_full_page is True
    """

    tavily_client = TavilyClient()
    return tavily_client.search(
        query, max_results=max_results, include_raw_content=fetch_full_page
    )


@traceable
def advanced_search(query: str, fetch_full_page: bool = False) -> Dict[str, Any]:
    """利用多源策略执行搜索，优先 Tavily，其次 SerpApi，最后 DuckDuckGo。"""

    notices: list[str] = []
    results: list[dict[str, Any]] = []
    answer: Optional[str] = None
    backend = "advanced"

    # 优先尝试 Tavily
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            tavily_result = tavily_search(
                query,
                fetch_full_page=fetch_full_page,
                max_results=5,
            )
            if tavily_result.get("results"):
                backend = "tavily"
                answer = tavily_result.get("answer")
                results.extend(tavily_result["results"])
                logger.info("advanced_search: using Tavily results for query='%s'", query)
                return {
                    "results": results,
                    "notices": notices,
                    "answer": answer,
                    "backend": backend,
                }
            notices.append("⚠️ Tavily 未返回有效结果，尝试其他搜索源")
            logger.info("advanced_search: Tavily returned no results for query='%s'", query)
        except Exception as exc:  # pragma: no cover - 第三方库防御
            notices.append(f"⚠️ Tavily 搜索失败：{exc}")
            logger.warning("advanced_search: Tavily failed for query='%s': %s", query, exc)
    else:
        notices.append("⚠️ 未检测到 TAVILY_API_KEY，跳过 Tavily 搜索")
        logger.info("advanced_search: Tavily disabled for query='%s'", query)

    # 其次尝试 SerpApi
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    if serpapi_key:
        try:
            from serpapi import GoogleSearch  # type: ignore

            params = {
                "engine": "google",
                "q": query,
                "api_key": serpapi_key,
                "gl": "cn",
                "hl": "zh-cn",
                "num": 5,
            }

            client = GoogleSearch(params)
            response = client.get_dict()

            answer_box = response.get("answer_box") or {}
            direct_answer = answer_box.get("answer") or answer_box.get("snippet")
            if direct_answer:
                answer = direct_answer

            organic_results = response.get("organic_results", [])
            for item in organic_results[:5]:
                results.append(
                    {
                        "title": item.get("title") or item.get("link") or query,
                        "url": item.get("link", ""),
                        "content": item.get("snippet") or item.get("title") or "",
                        "raw_content": item.get("snippet") or "",
                    }
                )

            if results:
                backend = "serpapi"
                logger.info("advanced_search: using SerpApi results for query='%s'", query)
                return {
                    "results": results,
                    "notices": notices,
                    "answer": answer,
                    "backend": backend,
                }

            notices.append("⚠️ SerpApi 未返回有效结果，回退到通用搜索")
            logger.info("advanced_search: SerpApi returned no results for query='%s'", query)
        except ImportError:
            notices.append("⚠️ SerpApi 库未安装，跳过 SerpApi 搜索 (pip install google-search-results)")
            logger.warning("advanced_search: serpapi package missing, skip query='%s'", query)
        except Exception as exc:  # pragma: no cover - 第三方库防御
            notices.append(f"⚠️ SerpApi 搜索失败：{exc}")
            logger.warning("advanced_search: SerpApi failed for query='%s': %s", query, exc)
    else:
        notices.append("⚠️ 未检测到 SERPAPI_API_KEY，跳过 SerpApi 搜索")
        logger.info("advanced_search: SerpApi disabled for query='%s'", query)

    # 最后回退到 DuckDuckGo（无需额外配置）
    try:
        ddg_result = duckduckgo_search(
            query,
            max_results=5,
            fetch_full_page=fetch_full_page,
        )
        if ddg_result.get("results"):
            backend = "duckduckgo"
            results.extend(ddg_result["results"])
            logger.info("advanced_search: using DuckDuckGo results for query='%s'", query)
        else:
            notices.append("⚠️ DuckDuckGo 未返回有效结果")
            logger.info("advanced_search: DuckDuckGo returned no results for query='%s'", query)
    except Exception as exc:  # pragma: no cover - 第三方库防御
        notices.append(f"⚠️ DuckDuckGo 搜索失败：{exc}")
        logger.warning("advanced_search: DuckDuckGo failed for query='%s': %s", query, exc)

    return {
        "results": results,
        "notices": notices,
        "answer": answer,
        "backend": backend,
    }


@traceable
def perplexity_search(
    query: str, perplexity_search_loop_count: int = 0
) -> Dict[str, Any]:
    """
    Search the web using the Perplexity API and return formatted results.

    Uses the Perplexity API to perform searches with the 'sonar-pro' model.
    Requires a PERPLEXITY_API_KEY environment variable to be set.

    Args:
        query (str): The search query to execute
        perplexity_search_loop_count (int, optional): The loop step for perplexity search
                                                     (used for source labeling). Defaults to 0.

    Returns:
        Dict[str, Any]: Search response containing:
            - results (list): List of search result dictionaries, each containing:
                - title (str): Title of the search result (includes search counter)
                - url (str): URL of the citation source
                - content (str): Content of the response or reference to main content
                - raw_content (str or None): Full content for the first source, None for additional
                                            citation sources

    Raises:
        requests.exceptions.HTTPError: If the API request fails
    """

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
    }

    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": "Search the web and provide factual information with sources.",
            },
            {"role": "user", "content": query},
        ],
    }

    response = requests.post(
        "https://api.perplexity.ai/chat/completions", headers=headers, json=payload
    )
    response.raise_for_status()  # Raise exception for bad status codes

    # Parse the response
    data = response.json()
    content = data["choices"][0]["message"]["content"]

    # Perplexity returns a list of citations for a single search result
    citations = data.get("citations", ["https://perplexity.ai"])

    # Return first citation with full content, others just as references
    results = [
        {
            "title": f"Perplexity Search {perplexity_search_loop_count + 1}, Source 1",
            "url": citations[0],
            "content": content,
            "raw_content": content,
        }
    ]

    # Add additional citations without duplicating content
    for i, citation in enumerate(citations[1:], start=2):
        results.append(
            {
                "title": f"Perplexity Search {perplexity_search_loop_count + 1}, Source {i}",
                "url": citation,
                "content": "See above for full content",
                "raw_content": None,
            }
        )

    return {"results": results}
