"""API limits and CORS, from the environment. Defaults are sized for the free tiers in docs/models.md."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.getenv(name) or default)


@dataclass(frozen=True)
class ApiSettings:
    # Browser origins allowed to call the API (the Vercel site + local dev). Browsers send an origin without a trailing
    # slash, so one pasted with the URL ("https://x.vercel.app/") would never match: strip it.
    web_origins: list[str] = field(default_factory=lambda: [
        o.strip().rstrip("/") for o in (os.getenv("WEB_ORIGINS") or "http://localhost:5173").split(",") if o.strip()])
    trust_proxy: bool = field(default_factory=lambda: (os.getenv("TRUST_PROXY") or "false").lower() == "true")
    # A plan costs ~3–7 LLM calls and ~60 Qloo calls. Groq's free tier is 1,000 requests/day.
    plans_per_ip_per_hour: int = field(default_factory=lambda: _int("LIMIT_PLANS_PER_IP_HOUR", 6))
    plans_per_day: int = field(default_factory=lambda: _int("LIMIT_PLANS_PER_DAY", 150))
    llm_actions_per_ip_per_hour: int = field(default_factory=lambda: _int("LIMIT_LLM_ACTIONS_PER_IP_HOUR", 30))
    uploads_per_ip_per_hour: int = field(default_factory=lambda: _int("LIMIT_UPLOADS_PER_IP_HOUR", 10))
    concurrent_plans: int = field(default_factory=lambda: _int("LIMIT_CONCURRENT_PLANS", 3))
    queue_timeout_s: float = field(default_factory=lambda: float(os.getenv("QUEUE_TIMEOUT_S") or 150))
    session_ttl_s: int = field(default_factory=lambda: _int("SESSION_TTL_S", 6 * 3600))
    upload_max_bytes: int = field(default_factory=lambda: _int("UPLOAD_MAX_BYTES", 2 * 1024 * 1024))
    upload_ttl_s: int = 15 * 60
