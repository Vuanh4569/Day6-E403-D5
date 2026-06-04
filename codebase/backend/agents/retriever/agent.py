from __future__ import annotations

import re
from typing import Protocol


class ChunkLike(Protocol):
    text: str


class RetrieverAgent:
    def retrieve(self, question: str, chunks: list[ChunkLike], limit: int = 4) -> list[ChunkLike]:
        keywords = self.keywords(question)
        scored: list[tuple[int, ChunkLike]] = []
        for chunk in chunks:
            body = chunk.text.lower()
            score = sum(1 for keyword in keywords if keyword in body)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def keywords(self, question: str) -> list[str]:
        text = question.lower()
        groups = [
            ["build slice", "slice", "lát cắt"],
            ["thin spec", "spec"],
            ["failure path", "failure"],
            ["happy path", "happy"],
            ["evidence", "evidence pack"],
            ["rag", "retrieval"],
            ["workflow", "agentic", "agent"],
            ["rubric", "checklist"],
        ]
        matches = [word for group in groups for word in group if word in text]
        if matches:
            return matches
        return [word for word in re.split(r"\W+", text) if len(word) > 3][:8]

