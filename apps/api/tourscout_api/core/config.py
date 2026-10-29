"""Agent settings from the environment (repo-root .env in development)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name) or default


@dataclass(frozen=True)
class LLMSettings:
    gemini_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_main: str = field(default_factory=lambda: _env("GEMINI_MAIN_MODEL", "gemini-flash-latest"))
    gemini_lite: str = field(default_factory=lambda: _env("GEMINI_LITE_MODEL", "gemini-flash-lite-latest"))
    groq_key: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: _env("GROQ_FALLBACK_MODEL", "openai/gpt-oss-120b"))
    # "gemini" (default, Groq as fallback) or "groq" (skip Gemini, e.g. during a demo when Gemini is overloaded).
    primary: str = field(default_factory=lambda: _env("LLM_PRIMARY", "gemini"))
    primary_timeout_s: float = field(default_factory=lambda: float(_env("LLM_PRIMARY_TIMEOUT_S", "12")))
    fallback_timeout_s: float = field(default_factory=lambda: float(_env("LLM_FALLBACK_TIMEOUT_S", "45")))
    cooldown_s: float = field(default_factory=lambda: float(_env("LLM_COOLDOWN_S", "120")))
