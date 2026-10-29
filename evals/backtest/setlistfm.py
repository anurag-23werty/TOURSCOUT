"""setlist.fm client for the backtest: an artist's most recent real tour in one country.

Free API key: https://www.setlist.fm/settings/api (non-commercial). Rate limit ~2 requests/second. Responses are cached
in the private cache like Qloo's, and nothing from setlist.fm is committed (only aggregate backtest numbers).
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import anyio
import httpx

from tourscout_mcp.cache import Cache, NoCache, cache_key

BASE = "https://api.setlist.fm/rest/1.0"
MIN_CITIES = 6  # a "tour" needs at least this many distinct cities in one year


class SetlistFm:
    def __init__(self, api_key: str, cache: Cache | None = None, transport: httpx.AsyncBaseTransport | None = None,
                 min_interval_s: float = 0.6) -> None:
        if not api_key:
            raise ValueError("SETLISTFM_API_KEY is missing: get a free key at https://www.setlist.fm/settings/api")
        self.http = httpx.AsyncClient(base_url=BASE, timeout=20, transport=transport,
                                      headers={"x-api-key": api_key, "Accept": "application/json"})
        self.cache = cache or NoCache()
        self.min_interval_s, self._last = min_interval_s, 0.0

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        key = cache_key(f"setlistfm:{path}", params)
        if (hit := await self.cache.get(key)) is not None:
            return hit
        for attempt in range(3):
            wait = self.min_interval_s - (time.monotonic() - self._last)
            if wait > 0:
                await anyio.sleep(wait)
            resp = await self.http.get(path, params=params)
            self._last = time.monotonic()
            if resp.status_code != 429:
                break
            await anyio.sleep(2 * (attempt + 1))
        if resp.status_code == 404:
            return {"setlist": []}
        resp.raise_for_status()
        data = resp.json()
        await self.cache.set(key, data)
        return data

    async def shows(self, mbid: str, pages: int = 3) -> list[dict[str, Any]]:
        """Newest-first shows: {date: YYYY-MM-DD, city, state, country, lat, lon}."""
        out = []
        for page in range(1, pages + 1):
            data = await self._get(f"/artist/{mbid}/setlists", {"p": str(page)})
            for s in data.get("setlist", []):
                city = (s.get("venue") or {}).get("city") or {}
                coords = city.get("coords") or {}
                day, month, year = (s.get("eventDate") or "00-00-0000").split("-")
                out.append({"date": f"{year}-{month}-{day}", "city": city.get("name"), "state": city.get("stateCode"),
                            "country": (city.get("country") or {}).get("code"), "lat": coords.get("lat"), "lon": coords.get("long")})
            total = int(data.get("total", 0))
            if page * int(data.get("itemsPerPage", 20) or 20) >= total:
                break
        return out


def latest_tour(shows: list[dict[str, Any]], country: str, before_year: int | None = None) -> tuple[int, list[dict[str, Any]]] | None:
    """The most recent year with at least MIN_CITIES distinct cities in `country`. Returns (year, shows that year)."""
    by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in shows:
        if s["country"] == country and s["date"][:4].isdigit():
            year = int(s["date"][:4])
            if before_year is None or year < before_year:
                by_year[year].append(s)
    for year in sorted(by_year, reverse=True):
        if len({(s["city"], s["state"]) for s in by_year[year]}) >= MIN_CITIES:
            return year, by_year[year]
    return None
