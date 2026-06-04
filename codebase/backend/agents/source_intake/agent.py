from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class Chunk:
    text: str
    title: str
    source_type: str
    source_url: str
    chunk_id: int


@dataclass
class Source:
    title: str
    source_type: str
    source_url: str
    status: str
    note: str
    chunks: list[Chunk] = field(default_factory=list)


def detect_source_type(raw: str) -> str:
    value = raw.strip().lower()
    if not value:
        return "empty"
    if "github.com" in value and "/blob/" not in value and "/raw/" not in value:
        return "github_repo"
    if "github.com" in value and "/blob/" in value:
        return "github_file"
    if value.endswith(".pdf") or ".pdf?" in value or value.startswith("data:application/pdf;base64,"):
        return "pdf"
    if value.startswith("http://") or value.startswith("https://"):
        return "web"
    return "pasted_text"


def chunk_text(text: str, title: str, source_type: str, source_url: str, size: int = 700) -> list[Chunk]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    chunks: list[Chunk] = []
    for index in range(0, len(cleaned), size):
        chunks.append(
            Chunk(
                text=cleaned[index : index + size],
                title=title,
                source_type=source_type,
                source_url=source_url,
                chunk_id=len(chunks) + 1,
            )
        )
    return chunks

