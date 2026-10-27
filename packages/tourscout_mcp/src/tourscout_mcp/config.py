"""Settings read from the environment (and the repo-root .env in development)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")


def _default_cache_url() -> str:
    # Outside the repo on purpose: Qloo responses must never end up in git.
    return f"sqlite:///{Path.home() / '.cache' / 'tourscout' / 'qloo.sqlite'}"


@dataclass(frozen=True)
class Settings:
    qloo_api_key: str = field(default_factory=lambda: os.getenv("QLOO_API_KEY", ""))
    qloo_base_url: str = field(
        default_factory=lambda: os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com").rstrip("/")
    )
    # postgres://… in production (Neon), sqlite:///… locally, "none" to disable.
    cache_url: str = field(default_factory=lambda: os.getenv("TOURSCOUT_CACHE_URL") or _default_cache_url())
    cache_ttl_days: int = field(default_factory=lambda: int(os.getenv("TOURSCOUT_CACHE_TTL_DAYS", "7")))
    geonames_file: Path = field(
        default_factory=lambda: Path(os.getenv("GEONAMES_FILE", REPO_ROOT / "data" / "raw" / "cities15000.txt"))
    )
    musicbrainz_user_agent: str = field(
        default_factory=lambda: os.getenv(
            "MUSICBRAINZ_USER_AGENT", "TourScout/0.1 (https://github.com/anurag-23werty/TOURSCOUT)"
        )
    )
    timeout_s: float = 20.0
