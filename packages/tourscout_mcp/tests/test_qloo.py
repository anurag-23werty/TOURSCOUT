from __future__ import annotations

import httpx
import pytest
from conftest import entities, make_client

from tourscout_mcp.allowlist import ParamNotAllowed, validate
from tourscout_mcp.cache import MemoryCache, SQLiteCache, cache_key
from tourscout_mcp.qloo import QlooError, items, normalise

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------- allow-list


def test_allowlist_accepts_verified_opener_params() -> None:
    validate(
        "/v2/insights",
        {
            "filter.type": "urn:entity:artist",
            "signal.interests.entities": "A",
            "signal.location.query": "Chicago",
            "signal.location.weight": "25",
            "filter.popularity.max": "0.7",
            "take": "20",
        },
    )


@pytest.mark.parametrize(
    ("filter_type", "param", "reason"),
    [
        ("urn:entity:artist", "filter.location.query", "signal.location.query"),
        ("urn:entity:place", "filter.popularity.max", "restaurants"),
        ("urn:heatmap", "signal.demographics.age", "ignores the region"),
    ],
)
def test_allowlist_rejects_params_we_saw_fail(filter_type: str, param: str, reason: str) -> None:
    with pytest.raises(ParamNotAllowed, match=reason):
        validate("/v2/insights", {"filter.type": filter_type, param: "x"})


def test_allowlist_rejects_unknown_params_and_types() -> None:
    with pytest.raises(ParamNotAllowed, match="not verified"):
        validate("/v2/insights", {"filter.type": "urn:entity:brand", "filter.typo": "1"})
    with pytest.raises(ParamNotAllowed, match="urn:heatmap"):
        validate("/v2/insights", {"filter.type": "urn:entity:locality"})
    with pytest.raises(ParamNotAllowed, match="limit"):
        validate("/search", {"query": "x", "take": "100"})


# ---------------------------------------------------------------- helpers


def test_normalise_and_items() -> None:
    assert normalise({"a": ["x", "y"], "b": None, "c": True, "d": 3}) == {"a": "x,y", "c": "true", "d": "3"}
    assert items({"results": [{"id": 1}]}) == [{"id": 1}]
    assert items({"results": {"tags": [{"id": 2}]}}) == [{"id": 2}]
    assert items({}) == []


def test_cache_key_ignores_param_order() -> None:
    assert cache_key("/s", {"a": "1", "b": "2"}) == cache_key("/s", {"b": "2", "a": "1"})


# ---------------------------------------------------------------- client


async def test_sends_key_header_and_caches() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return entities({"entity_id": "B1", "name": "Brand"})

    client = make_client(handler)
    for _ in range(2):
        result = await client.insights("urn:entity:brand", **{"signal.interests.entities": ["A1", "A2"]})
    assert result[0]["name"] == "Brand"
    assert client.calls == 1  # second call served from cache
    assert seen[0].headers["X-Api-Key"] == "test-key"
    assert seen[0].url.params["signal.interests.entities"] == "A1,A2"


async def test_retries_on_429_then_succeeds() -> None:
    statuses = iter([429, 503, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return entities({"entity_id": "X"}) if status == 200 else httpx.Response(status, json={"message": "slow down"})

    client = make_client(handler)
    assert (await client.search("Hovvdy", "urn:entity:artist"))[0]["entity_id"] == "X"
    assert client.calls == 3


async def test_errors_carry_hint_and_are_not_cached() -> None:
    cache = MemoryCache()
    client = make_client(lambda r: httpx.Response(401, json={"message": "bad key"}), cache)
    with pytest.raises(QlooError, match="X-Api-Key") as exc:
        await client.search("Hovvdy", "urn:entity:artist")
    assert exc.value.status == 401
    assert cache.data == {}


async def test_invalid_params_never_hit_the_network() -> None:
    client = make_client(lambda r: pytest.fail("network called"))
    with pytest.raises(ParamNotAllowed):
        await client.insights("urn:entity:artist", **{"filter.location.query": "Chicago"})


async def test_sqlite_cache_round_trip_and_ttl(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fresh = SQLiteCache(tmp_path / "c.sqlite", ttl_s=60)
    await fresh.set("k", [{"id": 1}])
    assert await fresh.get("k") == [{"id": 1}]
    expired = SQLiteCache(tmp_path / "c.sqlite", ttl_s=-1)
    assert await expired.get("k") is None


@pytest.mark.skipif(not __import__("os").getenv("TEST_POSTGRES_URL"), reason="set TEST_POSTGRES_URL to test against Postgres")
async def test_postgres_cache_round_trip_and_ttl() -> None:
    import os

    from tourscout_mcp.cache import PostgresCache

    fresh = PostgresCache(os.environ["TEST_POSTGRES_URL"], ttl_s=60)
    await fresh.set("pg-k", [{"id": 1}])
    assert await fresh.get("pg-k") == [{"id": 1}]
    await fresh.set("pg-k", [{"id": 2}])  # upsert
    assert await fresh.get("pg-k") == [{"id": 2}]
    expired = PostgresCache(os.environ["TEST_POSTGRES_URL"], ttl_s=-1)
    assert await expired.get("pg-k") is None
    await fresh.aclose()
    await expired.aclose()
