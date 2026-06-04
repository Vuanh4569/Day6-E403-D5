from __future__ import annotations

from pathlib import Path


AGENTS_DIR = Path(__file__).resolve().parent


def load_prompt(agent_name: str) -> str:
    path = AGENTS_DIR / agent_name / "prompt.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()

