"""MusicBrainz lookups for the opener "local" badge.

Qloo's location signal finds acts popular *in* a city, not acts *from* it (Phase 1: Jack Antonoff came up as a Columbus
and a Chicago opener). MusicBrainz knows where an artist is from. Rules: 1 request per second and a real User-Agent.
"""

from __future__ import annotations

import time
from typing import Any, Literal

import anyio
import httpx

from .cache import Cache, NoCache, cache_key
from .geo import fold

Badge = Literal["based_here", "elsewhere", "unknown"]
MIN_SCORE = 90
CITY_TYPES = {"City", "Municipality", "District"}


class MusicBrainz:
    def __init__(
        self,
        user_agent: str,
        cache: Cache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        min_interval_s: float = 1.0,
    ) -> None:
        self.http = httpx.AsyncClient(
            base_url="https://musicbrainz.org/ws/2",
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=10,
            transport=transport,
        )
        self.cache = cache or NoCache()
        self.min_interval_s = min_interval_s
        self._lock = anyio.Lock()
        self._last = 0.0

    async def aclose(self) -> None:
        await self.http.aclose()

    async def home(self, artist_name: str) -> dict[str, Any] | None:
        """Best match for an artist name: {mbid, name, area, area_type, begin_area, begin_area_type}, or None."""
        params = {"query": f'artist:"{artist_name}"', "fmt": "json", "limit": "5"}
        key = cache_key("musicbrainz:artist", {"name": fold(artist_name)})
        if (hit := await self.cache.get(key)) is not None:
            return hit or None

        async with self._lock:  # serialise requests to respect the 1 req/s rule
            for attempt in range(3):
                wait = self.min_interval_s * (1 + 2 * attempt) - (time.monotonic() - self._last)
                if wait > 0:
                    await anyio.sleep(wait)
                try:
                    resp = await self.http.get("/artist", params=params)
                except httpx.TransportError:
                    return None
                finally:
                    self._last = time.monotonic()
                if resp.status_code != 503:  # 503 = "server busy", MusicBrainz's rate limit
                    break
        if resp.status_code != 200:
            return None  # don't cache failures

        match = _best_match(artist_name, resp.json().get("artists", []))
        await self.cache.set(key, match or {})
        return match


def _best_match(name: str, artists: list[dict[str, Any]]) -> dict[str, Any] | None:
    for a in artists:
        if int(a.get("score", 0)) >= MIN_SCORE and fold(a.get("name", "")) == fold(name):
            area, begin = a.get("area") or {}, a.get("begin-area") or {}
            return {
                "mbid": a.get("id"),
                "name": a.get("name"),
                "area": area.get("name"),
                "area_type": area.get("type"),
                "begin_area": begin.get("name"),
                "begin_area_type": begin.get("type"),
            }
    return None


def local_badge(home: dict[str, Any] | None, metro_names: set[str]) -> Badge:
    """based_here if the artist's area/begin-area is a city in this metro; elsewhere if it's a different city."""
    if not home:
        return "unknown"
    places = [(home.get("begin_area"), home.get("begin_area_type")), (home.get("area"), home.get("area_type"))]
    if any(name and fold(name) in metro_names for name, _ in places):
        return "based_here"
    if any(name and kind in CITY_TYPES for name, kind in places):
        return "elsewhere"
    return "unknown"  # only a country/state is known
