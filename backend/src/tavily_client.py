"""
Клиент Tavily Search API для веб-поиска в пайплайне анализа pitch-deck.

Используется в промптах 1–5 (рынок, конкуренты, продукт, команда) для валидации
утверждений из слайдов через независимый веб-поиск.
"""
import re
from typing import Any, Callable, List, Optional, Tuple

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env.backend")


def _get_api_key() -> str:
    import os

    return os.getenv("TAVILY_API_KEY", "")


def search_web(
    queries: List[str],
    max_results_per_query: int = 4,
    log_fn: Optional[Callable[[str], None]] = None,
    return_raw: bool = False,
) -> str | Tuple[str, List[dict]]:

    """
    Выполняет веб-поиск через Tavily по списку запросов.

    Args:
        queries: Список поисковых запросов.
        max_results_per_query: Максимум результатов на один запрос (1–20).
        log_fn: Опциональный callback для логирования: log_fn(message).

    Returns:
        Если return_raw=False (по умолчанию) — строка с форматированным текстом для промпта.
        Если return_raw=True — кортеж (formatted_text, raw_responses),
        где raw_responses — список сырых ответов Tavily по каждому запросу.
    """

    def _log(msg: str) -> None:
        if log_fn:
            log_fn(msg)

    api_key = _get_api_key()
    if not api_key:
        _log("API key not configured, skipping web search")
        return "" if not return_raw else ("", [])

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
    except ImportError as e:
        _log(f"tavily-python not installed: {e}")
        return "" if not return_raw else ("", [])

    seen_urls: set[str] = set()
    all_results: List[dict] = []
    raw_responses: List[dict] = []

    _log(f"Starting search: {len(queries)} queries, max {max_results_per_query} results per query")

    for i, query in enumerate(queries, 1):
        if not query or not query.strip():
            continue
        q = query.strip()
        _log(f"Query {i}/{len(queries)}: {q[:80]}{'...' if len(q) > 80 else ''}")
        try:
            response: dict = client.search(
                query=q,
                search_depth="advanced",
                max_results=max_results_per_query,
                include_answer=False,
            )
            raw_responses.append(response)
            results = response.get("results", [])
            new_count = 0
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    new_count += 1
                    all_results.append(
                        {
                            "title": r.get("title", ""),
                            "url": url,
                            "content": r.get("content", ""),
                        }
                    )
            _log(f"Query {i} completed: {len(results)} results, {new_count} new (total unique: {len(all_results)})")
        except Exception as e:
            _log(f"Query {i} failed: {e}")

    _log(
        "Search completed: "
        f"{len(all_results)} unique results, "
        f"{sum(len(r.get('content', '')) for r in all_results)} chars total"
    )

    formatted = _format_results(all_results)
    if return_raw:
        return formatted, raw_responses
    return formatted


def _format_results(results: List[dict], max_total_chars: int = 12000) -> str:
    """Форматирует результаты поиска в текст для промпта."""
    if not results:
        return ""

    parts: List[str] = []
    total_len = 0

    for i, r in enumerate(results, 1):
        block = (
            f"[{i}] {r['title']}\n"
            f"URL: {r['url']}\n"
            f"Content: {r['content'][:800]}\n"
        )
        if total_len + len(block) > max_total_chars:
            remaining = max_total_chars - total_len - 50
            if remaining > 100:
                block = (
                    f"[{i}] {r['title']}\n"
                    f"URL: {r['url']}\n"
                    f"Content: {r['content'][:remaining]}...\n"
                )
            parts.append(block)
            break
        parts.append(block)
        total_len += len(block)

    return "\n".join(parts)
