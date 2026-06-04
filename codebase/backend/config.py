from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
ALT_ENV_PATH = ROOT / ".evn"


def load_env(path: Path = ENV_PATH) -> None:
    env_path = path if path.exists() else ALT_ENV_PATH
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str


def get_llm_settings() -> LLMSettings:
    load_env()
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()

    if provider == "auto":
        if os.getenv("OPENAI_API_KEY", "").strip():
            provider = "openai"
        elif os.getenv("GROQ_API_KEY", "").strip():
            provider = "groq"
        elif os.getenv("GOOGLE_API_KEY", "").strip():
            provider = "gemini"
        else:
            provider = "mock"

    if provider == "openai":
        return LLMSettings(
            provider=provider,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
        )
    if provider == "groq":
        return LLMSettings(
            provider=provider,
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            api_key=os.getenv("GROQ_API_KEY", ""),
        )
    if provider == "gemini":
        return LLMSettings(
            provider=provider,
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            api_key=os.getenv("GOOGLE_API_KEY", ""),
        )
    return LLMSettings(provider="mock", model="mock", api_key="")
