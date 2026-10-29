from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtest"))

from backtest import evaluate, recall_at  # noqa: E402
from setlistfm import SetlistFm, latest_tour  # noqa: E402

from tourscout_mcp.cache import MemoryCache  # noqa: E402

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def show(date: str, city: str, country: str = "US") -> dict:
    return {"date": date, "city": city, "state": "XX", "country": country, "lat": None, "lon": None}


def test_latest_tour_picks_most_recent_year_with_enough_cities() -> None:
    shows = [show("2024-05-01", f"C{i}") for i in range(4)]  # 2024: only 4 cities
    shows += [show("2023-04-01", f"D{i}") for i in range(7)] + [show("2023-04-09", "Toronto", "CA")]
    year, tour = latest_tour(shows, "US")
    assert year == 2023 and len(tour) == 7
    assert latest_tour(shows, "US", before_year=2023) is None


def test_recall_and_baselines() -> None:
    metros = [{"metro": m, "lat": 0.0, "lon": 0.0, "population": pop, "affinity": aff, "cells": 10}
              for m, pop, aff in [("Big", 9_000_000, 0.5), ("Mid", 400_000, 0.95), ("Small", 90_000, 0.9), ("Other", 500_000, 0.4)]]
    assert recall_at(["a", "b", "c"], {"b", "z"}, 2) == 0.5
    r = evaluate({"Mid", "Small", "Nowhere"}, metros)
    assert r["played"] == 3 and r["played_in_candidates"] == 2 and r["candidates"] == 4
    assert r["tourscout@10"] == 1.0 and r["random@10"] == 1.0  # top-10 covers all 4 candidates


async def test_setlistfm_parses_pages_and_caches() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["x-api-key"] == "k"
        return httpx.Response(200, json={"total": 1, "itemsPerPage": 20, "setlist": [{
            "eventDate": "09-04-2023",
            "venue": {"city": {"name": "Columbus", "stateCode": "OH", "country": {"code": "US"}, "coords": {"lat": 39.96, "long": -83.0}}}}]})

    sfm = SetlistFm("k", MemoryCache(), httpx.MockTransport(handler), min_interval_s=0)
    first = await sfm.shows("mbid-1")
    assert first == [{"date": "2023-04-09", "city": "Columbus", "state": "OH", "country": "US", "lat": 39.96, "lon": -83.0}]
    await sfm.shows("mbid-1")
    assert len(calls) == 1
    with pytest.raises(ValueError, match="setlist.fm"):
        SetlistFm("")
