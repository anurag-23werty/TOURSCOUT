"""Async Qloo client: allow-list validation, private cache, retries, and trimming for the LLM."""

from __future__ import annotations

from typing import Any

import anyio
import httpx

from .allowlist import validate
from .cache import Cache, NoCache, cache_key

ERROR_HINTS = {
    400: "a param value is invalid for this filter.type",
    401: "check QLOO_BASE_URL is https://hackathon.api.qloo.com and the key is sent as X-Api-Key",
    403: "this filter.type is not enabled for hackathon keys",
    404: "wrong path (insights is GET /v2/insights)",
    429: "rate limited by Qloo",
}
RETRY_STATUSES = {429, 500, 502, 503, 504}


class QlooError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        hint = ERROR_HINTS.get(status)
        super().__init__(f"Qloo {status}: {message}" + (f" ({hint})" if hint else ""))
        self.status = status


def normalise(params: dict[str, Any]) -> dict[str, str]:
    """Drop None values; lists become comma-separated strings; bools become 'true'/'false'."""
    out: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = ",".join(str(v) for v in value)
        out[key] = str(value).lower() if isinstance(value, bool) else str(value)
    return out


def items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Result list for any endpoint shape (search: results[], insights: results.entities[], tags: results.tags[])."""
    results = data.get("results")
    if isinstance(results, list):
        return results
    if isinstance(results, dict):
        for value in results.values():
            if isinstance(value, list):
                return value
    return []


class QlooClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://hackathon.api.qloo.com",
        cache: Cache | None = None,
        timeout_s: float = 20.0,
        retries: int = 4,
        max_concurrency: int = 4,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("QLOO_API_KEY is missing. Copy .env.example to .env and add your key.")
        self.http = httpx.AsyncClient(
            base_url=base_url, headers={"X-Api-Key": api_key}, timeout=timeout_s, transport=transport
        )
        self.cache = cache or NoCache()
        self.retries = retries
        # A tour fan-out is ~60 requests. Measured: 4+ in flight starts returning 429s, so cap requests in flight.
        self._slots = anyio.Semaphore(max_concurrency)
        self.calls = 0  # real network calls, for tests and traces

    async def aclose(self) -> None:
        await self.http.aclose()

    async def get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Validated, cached GET. Returns the result list; raises QlooError on failure."""
        clean = normalise(params)
        validate(path, clean)
        key = cache_key(path, clean)
        if (hit := await self.cache.get(key)) is not None:
            return hit

        for attempt in range(self.retries):
            try:
                async with self._slots:
                    resp = await self.http.get(path, params=clean)
            except httpx.TransportError as exc:
                if attempt == self.retries - 1:
                    raise QlooError(0, f"network error: {exc.__class__.__name__}") from exc
            else:
                self.calls += 1
                if resp.status_code not in RETRY_STATUSES or attempt == self.retries - 1:
                    break
            await anyio.sleep(0.5 * 2**attempt)

        if resp.status_code != 200:
            raise QlooError(resp.status_code, _message(resp))
        result = items(resp.json())
        await self.cache.set(key, result)
        return result

    async def insights(self, filter_type: str, **params: Any) -> list[dict[str, Any]]:
        return await self.get("/v2/insights", {"filter.type": filter_type, **params})

    async def search(self, query: str, types: str, take: int = 5) -> list[dict[str, Any]]:
        return await self.get("/search", {"query": query, "types": types, "take": take})

    async def entity(self, entity_id: str) -> dict[str, Any] | None:
        found = await self.get("/entities", {"entity_ids": entity_id})
        return found[0] if found else None


def _message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("message", err))
        return str(body.get("message") or body.get("reason") or err or body)[:200]
    return str(body)[:200]


# ---------------------------------------------------------------- trimming for the LLM


def affinity(item: dict[str, Any]) -> float | None:
    query = item.get("query")
    return query.get("affinity") if isinstance(query, dict) else None


def genre_tags(item: dict[str, Any]) -> list[str]:
    return [t["name"] for t in item.get("tags") or [] if str(t.get("type", "")).startswith("urn:tag:genre") and t.get("name")]


def round_or_none(value: float | None, digits: int = 3) -> float | None:
    return round(value, digits) if isinstance(value, (int, float)) else None


def trim_place(item: dict[str, Any]) -> dict[str, Any]:
    props = item.get("properties") or {}
    loc = item.get("location") or {}
    return {
        "id": item.get("entity_id"),
        "name": item.get("name"),
        "address": props.get("address"),
        "lat": loc.get("lat"),
        "lon": loc.get("lon"),
        "rating": props.get("business_rating"),
        "affinity": round_or_none(affinity(item)),
        "popularity": round_or_none(item.get("popularity")),
    }


def trim_artist(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("entity_id"),
        "name": item.get("name"),
        "popularity": round_or_none(item.get("popularity")),
        "affinity": round_or_none(affinity(item)),
        "genres": genre_tags(item)[:8],
    }


def trim_brand(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("entity_id"),
        "name": item.get("name"),
        "affinity": round_or_none(affinity(item)),
        "popularity": round_or_none(item.get("popularity")),
    }

