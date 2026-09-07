from __future__ import annotations

import asyncio

from duckduckgo_search import DDGS

from app.config import settings
from app.http_client import get_http_client


def search_duckduckgo(query: str, max_results: int = 5) -> str:
    results: list[str] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            title = item.get("title", "")
            body = item.get("body", "")
            href = item.get("href", "")
            results.append(f"- {title}\n  {body}\n  {href}")
    if not results:
        return f"No DuckDuckGo results found for: {query}"
    return "DuckDuckGo search results:\n" + "\n".join(results)


async def search_exa(query: str, max_results: int = 5) -> str:
    if not settings.exa_api_key:
        return "EXA_API_KEY is not configured. Set it in your environment to use Exa search."

    client = get_http_client()
    response = await client.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": settings.exa_api_key, "Content-Type": "application/json"},
        json={"query": query, "numResults": max_results, "type": "auto"},
    )
    response.raise_for_status()
    data = response.json()
    results: list[str] = []
    for item in data.get("results", []):
        title = item.get("title", "Untitled")
        url = item.get("url", "")
        snippet = item.get("text") or item.get("snippet") or ""
        results.append(f"- {title}\n  {snippet}\n  {url}")
    if not results:
        return f"No Exa results found for: {query}"
    return "Exa search results:\n" + "\n".join(results)


async def run_search(provider: str, query: str) -> str:
    provider = (provider or "google").lower()
    if provider == "exa":
        return await search_exa(query)
    if provider in {"duckduckgo", "ddg"}:
        return await asyncio.to_thread(search_duckduckgo, query)
    return query