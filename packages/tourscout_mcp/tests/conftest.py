"""Shared test helpers. All fixtures are synthetic: Qloo response data must never be committed."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tourscout_mcp.cache import MemoryCache
from tourscout_mcp.qloo import QlooClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler, cache: MemoryCache | None = None) -> QlooClient:
    return QlooClient("test-key", cache=cache or MemoryCache(), transport=httpx.MockTransport(handler), retries=3)


def entities(*rows: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "results": {"entities": list(rows)}})


def artist(entity_id: str, name: str, popularity: float, affinity: float, genres: list[str] = ()) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "name": name,
        "popularity": popularity,
        "query": {"affinity": affinity},
        "tags": [{"type": "urn:tag:genre:music", "name": g} for g in genres],
    }


def place(entity_id: str, name: str, affinity: float, address: str | None = "1 Main St") -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "name": name,
        "popularity": 0.9,
        "query": {"affinity": affinity},
        "location": {"lat": 41.9, "lon": -87.6},
        "properties": {"address": address, "business_rating": 4.6},
    }
