from __future__ import annotations

from typing import Any
import json
import os
import urllib.request

from config import load_env


def tavily_search(query: str, max_results: int = 4) -> list[dict[str, str]]:
    load_env()
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return mock_tavily_search(query)

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        data = post_json("https://api.tavily.com/search", payload)
        return [
            {
                "title": item.get("title", "Tavily result"),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
            for item in data.get("results", [])
        ]
    except Exception:
        return mock_tavily_search(query)


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def mock_tavily_search(query: str) -> list[dict[str, str]]:
    text = query.lower()
    if "rag" in text:
        return [
            {
                "title": "Retrieval augmented generation",
                "url": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
                "snippet": "RAG retrieves relevant documents before generation to ground answers in external context.",
            }
        ]
    if "agent" in text:
        return [
            {
                "title": "AI Agent overview",
                "url": "https://example.com/ai-agent-overview",
                "snippet": "An AI Agent routes a user goal, gathers context, calls tools when needed, reasons over evidence, and returns an action or answer.",
            },
            {
                "title": "Agent workflow pattern",
                "url": "https://example.com/agent-workflow",
                "snippet": "A practical agent loop is: understand the request, decide if context is missing, use tools or retrieval, compose an answer, and refuse when evidence is insufficient.",
            },
        ]
    return [
        {
            "title": "Mock public source",
            "url": "https://example.com/public-learning-source",
            "snippet": f"Mock Tavily result for '{query}'. Set TAVILY_API_KEY in .env to use real search.",
        }
    ]


def tavily_multi_search(queries: list[str], max_results_per_query: int = 3, max_results_total: int = 6) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()

    for query in queries:
        for item in tavily_search(query, max_results=max_results_per_query):
            key = item.get("url", "").strip() or item.get("title", "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= max_results_total:
                return merged
    return merged
