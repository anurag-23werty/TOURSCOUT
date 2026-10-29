from __future__ import annotations

import httpx
import pytest

from tourscout_mcp.cache import MemoryCache
from tourscout_mcp.geo import City, MetroIndex, aggregate_cells, decode_geohash, fold, haversine_km
from tourscout_mcp.musicbrainz import MusicBrainz, local_badge

pytestmark = pytest.mark.anyio

# Synthetic cities (rounded real coordinates, not Qloo data).
CITIES = [
    City("Chicago", "US", "IL", 41.88, -87.63, 2_700_000),
    City("Evanston", "US", "IL", 42.04, -87.69, 75_000),
    City("Columbus", "US", "OH", 39.96, -83.00, 900_000),
    City("Athens", "US", "OH", 39.33, -82.10, 24_000),
    City("Bengaluru", "IN", "19", 12.97, 77.59, 8_400_000, ("Bangalore",)),
    City("Oak Park", "US", "IL", 41.89, -87.79, 52_000, ("Athens",)),  # alternate name clash
]


def cell(lat: float, lon: float, affinity: float, popularity: float) -> dict:
    return {"location": {"latitude": lat, "longitude": lon}, "query": {"affinity": affinity, "popularity": popularity}}


def test_decode_geohash_and_distance() -> None:
    lat, lon = decode_geohash("dp3w")  # a Chicago cell
    assert 41.5 < lat < 42.2 and -88.0 < lon < -87.4
    assert haversine_km((41.88, -87.63), (39.96, -83.00)) == pytest.approx(444, abs=10)


def test_suburbs_join_their_city_but_college_towns_stay() -> None:
    index = MetroIndex(CITIES)
    labels = sorted(m.label for m in index.metros)
    assert labels == ["Athens, OH", "Bengaluru, IN", "Chicago, IL", "Columbus, OH"]
    chicago = index.find("Evanston")
    assert chicago is not None and chicago.name == "Chicago" and chicago.population == 2_827_000
    assert index.find("bangalore").name == "Bengaluru"  # alternate names and case
    assert index.find("Athens", "US").name == "Athens"  # a real city name beats another city's alternate name
    assert index.find("Chicago, IL", country="IN") is None
    assert index.find("Athens, OH").name == "Athens" and index.find("Athens, GA") is None


def test_aggregate_weights_affinity_by_popularity() -> None:
    index = MetroIndex(CITIES)
    cells = [
        cell(41.90, -87.65, 0.9, 1.0),  # Chicago, busy
        cell(41.80, -87.60, 0.5, 0.1),  # Chicago, quiet
        cell(39.33, -82.11, 0.95, 0.4),  # Athens
        cell(10.0, -40.0, 0.99, 0.9),  # middle of the Atlantic → unmapped
        {"location": {"geohash": "dp3w"}, "query": {"affinity": 0.8, "popularity": 0.5}},  # Chicago via geohash
    ]
    metros, unmapped = aggregate_cells(cells, index)
    by_name = {m.metro.name: m for m in metros}
    assert unmapped == 1
    assert by_name["Chicago"].cells == 3
    assert by_name["Chicago"].affinity == pytest.approx((0.9 + 0.05 + 0.4) / 1.6, abs=1e-3)
    assert by_name["Athens"].activity == 0.4


def test_fold() -> None:
    assert fold(" Zürich ") == "zurich"


# ---------------------------------------------------------------- MusicBrainz

HOME = {"area": "United States", "area_type": "Country", "begin_area": "Chicago", "begin_area_type": "City"}


def test_local_badge() -> None:
    metro = {"chicago", "evanston"}
    assert local_badge(HOME, metro) == "based_here"
    assert local_badge({**HOME, "begin_area": "Evanston"}, metro) == "based_here"
    assert local_badge({**HOME, "begin_area": "Los Angeles"}, metro) == "elsewhere"
    assert local_badge({"area": "United States", "area_type": "Country"}, metro) == "unknown"
    assert local_badge(None, metro) == "unknown"


async def test_musicbrainz_picks_exact_high_score_match_and_caches() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"artists": [
            {"id": "x", "name": "Snarls Tribute", "score": 100},
            {"id": "m1", "name": "Snarls", "score": 98, "begin-area": {"name": "Columbus", "type": "City"}},
        ]})

    mb = MusicBrainz("TourScout-test/0", MemoryCache(), transport=httpx.MockTransport(handler), min_interval_s=0)
    first = await mb.home("Snarls")
    second = await mb.home("snarls")
    assert first["mbid"] == "m1" and first["begin_area"] == "Columbus"
    assert second == first and len(calls) == 1
    assert calls[0].headers["User-Agent"] == "TourScout-test/0"


def test_big_city_keeps_its_edge_cells() -> None:
    index = MetroIndex([City("Bengaluru", "IN", "19", 12.97, 77.59, 9_800_000), City("Channapatna", "IN", "19", 12.65, 77.21, 70_000),
                        City("Lawrence", "US", "KS", 38.97, -95.24, 95_000), City("Kansas City", "US", "MO", 39.10, -94.58, 2_000_000)])
    assert index.nearest(12.568, 77.52).name == "Bengaluru"  # real Qloo cell centre: 35 km from the town, 45 km from the city
    assert index.nearest(38.97, -95.25).name == "Lawrence"  # college town 58 km from a big city keeps its own cells
