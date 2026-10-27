"""Minimal Qloo client for Phase 1 exploration.

The production client (validation, async, Postgres cache) lives in packages/qloo_mcp (Phase 2).
Everything this module writes goes to qloo_responses/, which is git-ignored: Qloo data must never be committed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "qloo_responses"
CACHE_DIR = OUT_DIR / "cache"

load_dotenv(ROOT / ".env")

ERROR_HINTS = {
    401: "check QLOO_BASE_URL is https://hackathon.api.qloo.com and the key is sent as X-Api-Key",
    403: "this filter.type is not supported for hackathon keys",
    404: "wrong path, or POST used (insights is GET with query params)",
    429: "rate limited; wait or ask in Discord #api-help",
}


@dataclass
class QlooResponse:
    status: int
    data: dict[str, Any]
    seconds: float
    cached: bool

    @property
    def ok(self) -> bool:
        return self.status == 200

    @property
    def message(self) -> str:
        msg = self.data.get("message") or self.data.get("reason") or self.data.get("error") or ""
        hint = ERROR_HINTS.get(self.status, "")
        return f"{msg} ({hint})" if hint else str(msg)

    def items(self) -> list[dict[str, Any]]:
        """Result list regardless of endpoint shape (search: results[], insights: results.entities[], tags: results.tags[])."""
        results = self.data.get("results")
        if isinstance(results, list):
            return results
        if isinstance(results, dict):
            for value in results.values():
                if isinstance(value, list):
                    return value
        return []


class Qloo:
    def __init__(self, use_cache: bool = True) -> None:
        key = os.getenv("QLOO_API_KEY")
        if not key:
            raise SystemExit("QLOO_API_KEY is missing. Copy .env.example to .env and add your key.")
        self.base_url = os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com").rstrip("/")
        self.use_cache = use_cache
        self.http = httpx.Client(base_url=self.base_url, headers={"X-Api-Key": key}, timeout=30)

    def get(self, path: str, params: dict[str, Any]) -> QlooResponse:
        params = normalise(params)
        cache_file = CACHE_DIR / f"{cache_key(path, params)}.json"
        if self.use_cache and cache_file.exists():
            saved = json.loads(cache_file.read_text())
            return QlooResponse(200, saved["data"], saved["seconds"], cached=True)

        for attempt in range(3):
            start = time.perf_counter()
            resp = self.http.get(path, params=params)
            seconds = round(time.perf_counter() - start, 3)
            if resp.status_code != 429:
                break
            time.sleep(2 ** (attempt + 1))

        try:
            data = resp.json()
        except ValueError:
            data = {"message": resp.text[:300]}
        if not isinstance(data, dict):
            data = {"results": data}

        if resp.status_code == 200:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"path": path, "params": params, "seconds": seconds, "data": data}, indent=2))
        return QlooResponse(resp.status_code, data, seconds, cached=False)


def normalise(params: dict[str, Any]) -> dict[str, str]:
    """Drop None values; Qloo takes array params as comma-separated strings."""
    out = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = ",".join(str(v) for v in value)
        out[key] = str(value).lower() if isinstance(value, bool) else str(value)
    return out


def cache_key(path: str, params: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps([path, sorted(params.items())]).encode()).hexdigest()[:24]


def item_id(item: dict[str, Any]) -> str | None:
    return item.get("entity_id") or item.get("id") or item.get("tag_id")


def ids(resp: QlooResponse) -> list[str]:
    return [i for i in (item_id(x) for x in resp.items()) if i]


def affinity(item: dict[str, Any]) -> float | None:
    query = item.get("query")
    return query.get("affinity") if isinstance(query, dict) else None


def lat_lon(item: dict[str, Any]) -> tuple[float, float] | None:
    """Entities use location.lat/lon; heatmap cells use location.latitude/longitude."""
    loc = item.get("location")
    if not isinstance(loc, dict):
        return None
    lat = loc.get("lat", loc.get("latitude"))
    lon = loc.get("lon", loc.get("longitude"))
    return (lat, lon) if lat is not None and lon is not None else None


def popularity(item: dict[str, Any]) -> float | None:
    """Entities carry top-level popularity; heatmap cells carry it under query."""
    if isinstance(item.get("popularity"), (int, float)):
        return item["popularity"]
    query = item.get("query")
    return query.get("popularity") if isinstance(query, dict) else None


def key_paths(obj: Any, prefix: str = "") -> set[str]:
    """All dotted key paths in a JSON object; lists are entered through their first element as '[]'."""
    paths: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            paths.add(path)
            paths |= key_paths(value, path)
    elif isinstance(obj, list) and obj:
        paths |= key_paths(obj[0], f"{prefix}[]")
    return paths


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return round(len(sa & sb) / len(sa | sb), 2) if sa | sb else 1.0
