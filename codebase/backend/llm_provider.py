from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import urllib.error
import urllib.request

from config import LLMSettings, get_llm_settings


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    used_mock: bool = False


class LLMClient:
    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or get_llm_settings()

    def generate(self, system: str, prompt: str) -> LLMResponse:
        if self.settings.provider == "openai":
            return self._openai_compatible(
                url="https://api.openai.com/v1/chat/completions",
                api_key=self.settings.api_key,
                system=system,
                prompt=prompt,
            )
        if self.settings.provider == "groq":
            return self._openai_compatible(
                url="https://api.groq.com/openai/v1/chat/completions",
                api_key=self.settings.api_key,
                system=system,
                prompt=prompt,
            )
        if self.settings.provider == "gemini":
            return self._gemini(system=system, prompt=prompt)
        return self._mock(prompt)

    def _openai_compatible(self, url: str, api_key: str, system: str, prompt: str) -> LLMResponse:
        if not api_key:
            return self._mock(prompt, reason=f"missing api key for {self.settings.provider}")

        payload = {
            "model": self.settings.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            data = self._post_json(url, payload, {"Authorization": f"Bearer {api_key}"})
        except Exception as exc:
            return self._mock(prompt, reason=f"{self.settings.provider} request failed: {type(exc).__name__}")
        try:
            text = data["choices"][0]["message"]["content"]
        except Exception:
            return self._mock(prompt, reason="provider response parse failed")
        return LLMResponse(text=text, provider=self.settings.provider, model=self.settings.model)

    def _gemini(self, system: str, prompt: str) -> LLMResponse:
        if not self.settings.api_key:
            return self._mock(prompt, reason="missing api key for gemini")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.model}:generateContent?key={self.settings.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        try:
            data = self._post_json(url, payload, {})
        except Exception as exc:
            return self._mock(prompt, reason=f"gemini request failed: {type(exc).__name__}")
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return self._mock(prompt, reason="gemini response parse failed")
        return LLMResponse(text=text, provider=self.settings.provider, model=self.settings.model)

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    def _mock(self, prompt: str, reason: str = "mock provider selected") -> LLMResponse:
        return LLMResponse(
            text=(
                "LLM mock đang bật nên phần này dùng rule-based answer. "
                f"Reason: {reason}. "
                "Khi điền `.env`, agent sẽ dùng provider thật để compose reasoning."
            ),
            provider=self.settings.provider,
            model=self.settings.model,
            used_mock=True,
        )
