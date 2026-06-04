from __future__ import annotations

from typing import Any

from agents.prompt_loader import load_prompt
from llm_provider import LLMClient


class AnswerComposerAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self.prompt = load_prompt("answer_composer")

    def compose(self, route: str, question: str, evidence: list[dict[str, Any]]) -> str:
        response = self.llm.generate(
            system=self.prompt,
            prompt=(
                f"Route: {route}\n"
                f"Question: {question}\n"
                f"Evidence:\n{evidence}\n\n"
                "Hãy tạo câu trả lời theo format trong system prompt."
            ),
        )
        if response.used_mock:
            return ""
        return self._clean_response(response.text)

    def call_label(self) -> str:
        settings = self.llm.settings
        return f"answer_composer_llm(provider={settings.provider}, model={settings.model})"

    def _clean_response(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned
