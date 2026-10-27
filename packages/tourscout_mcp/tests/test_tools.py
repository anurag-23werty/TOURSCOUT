from __future__ import annotations

import httpx
import pytest
from conftest import artist, entities, make_client, place

from tourscout_mcp.geo import City, MetroIndex
from tourscout_mcp.server import mcp
from tourscout_mcp.tools import Deps, artists, demand, places

pytestmark = pytest.mark.anyio

HEAD = artist("H", "Headliner", 0.80, 1.0, ["Indie Pop", "Dream Pop", "Indie"])


def qloo_router(request: httpx.Request) -> httpx.Response:
    """A fake Qloo that answers based on the request params (all data synthetic)."""
    p = request.url.params
    if request.url.path == "/search":
        return httpx.Response(200, json={"results": [artist("K", "Kayano Ai", 0.7, 0.0)]})
    if request.url.path == "/entities":
        return httpx.Response(200, json={"results": [HEAD]})
    kind, city = p.get("filter.type"), p.get("signal.location.query") or p.get("filter.location.query")
    if kind == "urn:entity:artist":
        assert p["filter.popularity.max"] == "0.75" and p["signal.location.weight"] == "25"
        national = artist("N", "Famous Producer", 0.74, 0.990, ["Pop"])
        local = {
            "Chicago": [artist("C1", "Chi Dream", 0.6, 0.995, ["Dream Pop", "Indie", "Chicago"]),
                        artist("C2", "Chi Rap", 0.6, 0.996, ["Hip Hop", "Chicago"])],
            "Columbus": [artist("O1", "Col Indie", 0.5, 0.99, ["Indie Pop", "Indie"])],
            "Austin": [artist("A1", "Atx Folk", 0.5, 0.99, ["Folk", "Indie"])],
        }[city]
        return entities(*local, national)
    if kind == "urn:entity:place":
        tag = p["filter.tags"]
        if tag.endswith("live_music_venue"):
            return entities(place("V1", "Big Theatre", 0.92), place("V2", "Small Club", 0.90), place("V9", "Area", 0.99, None))
        if tag.endswith("music_venue"):
            return entities(place("V2", "Small Club", 0.95), place("V3", "Basement", 0.91))
        return entities(place("R1", "Records", 0.9), place("R2", "No Address", 0.95, None))
    if kind == "urn:entity:brand":
        if city:
            return entities({"entity_id": "B1", "name": "Big Brand", "query": {"affinity": 0.95}},
                            {"entity_id": "B3", "name": "Local Brand", "query": {"affinity": 0.97}})
        return entities({"entity_id": "B1", "name": "Big Brand", "query": {"affinity": 0.90}},
                        {"entity_id": "B2", "name": "Other Brand", "query": {"affinity": 0.88}})
    if kind == "urn:heatmap":
        cells = [
            {"location": {"latitude": 41.9, "longitude": -87.6, "geohash": "dp3w"}, "query": {"affinity": 0.9, "popularity": 1.0}},
            {"location": {"latitude": 39.33, "longitude": -82.1, "geohash": "dph1"}, "query": {"affinity": 0.95, "popularity": 0.5}},
        ]
        return httpx.Response(200, json={"results": {"heatmap": cells}})
    return httpx.Response(404, json={"message": "unexpected"})


@pytest.fixture
def deps() -> Deps:
    metros = MetroIndex([
        City("Chicago", "US", "IL", 41.88, -87.63, 2_700_000),
        City("Athens", "US", "OH", 39.33, -82.10, 24_000),
    ])
    return Deps(qloo=make_client(qloo_router), metros=metros)


async def test_resolve_artist_flags_fuzzy_matches(deps: Deps) -> None:
    result = await artists.resolve_artist(deps, "Kayan")
    assert result["needs_confirmation"] is True
    assert result["candidates"][0]["name"] == "Kayano Ai"


async def test_openers_rank_by_fit_and_drop_national_acts(deps: Deps) -> None:
    result = await artists.find_openers(deps, "H", ["Chicago", "Columbus", "Austin"], take=3, check_local=False)
    assert result["popularity_cap"] == 0.75
    chicago = result["cities"][0]
    names = [o["name"] for o in chicago["openers"]]
    assert names[0] == "Chi Dream"  # genre fit beats the slightly higher local affinity of Chi Rap
    assert "Famous Producer" not in names
    assert chicago["dropped"][0]["name"] == "Famous Producer"
    assert chicago["openers"][0]["qloo_city_tag"] is True


async def test_openers_keep_everyone_with_fewer_than_three_cities(deps: Deps) -> None:
    result = await artists.find_openers(deps, "H", ["Chicago"], check_local=False)
    assert "Famous Producer" in [o["name"] for o in result["cities"][0]["openers"]]


def test_genre_fit_normalises_spelling() -> None:
    assert artists.genre_fit(["Hip - Hop", "R & B"], ["Hip Hop", "R&B"]) == 1.0
    assert artists.genre_fit([], []) == 0.0


async def test_venues_merge_tags_drop_areas_and_never_guess_capacity(deps: Deps) -> None:
    result = await places.find_venues(deps, ["H"], "Chicago")
    venues = {v["id"]: v for v in result["venues"]}
    assert set(venues) == {"V1", "V2", "V3"}
    assert venues["V2"]["affinity"] == 0.95 and venues["V2"]["matched_tags"] == ["live_music_venue", "music_venue"]
    assert all(v["capacity"] == "verify" for v in venues.values())
    assert result["venues"][0]["id"] == "V2"


async def test_sponsors_city_uplift(deps: Deps) -> None:
    result = await places.find_sponsors(deps, ["H"], ["Chicago"])
    brands = {b["name"]: b for b in result["cities"][0]["brands"]}
    assert brands["Big Brand"]["uplift"] == 0.05
    assert brands["Local Brand"]["new_in_city"] is True


async def test_promo_spots_validate_kinds_and_need_address(deps: Deps) -> None:
    result = await places.find_promo_spots(deps, ["H"], "Chicago", ["record_store"])
    assert [s["id"] for s in result["spots"]["record_store"]] == ["R1"]
    with pytest.raises(ValueError, match="unknown promo kinds"):
        await places.find_promo_spots(deps, ["H"], "Chicago", ["stadium"])


async def test_demand_map_rolls_cells_into_metros(deps: Deps) -> None:
    result = await demand.demand_map(deps, ["H", "S"], "United States")
    metros = [m["metro"] for m in result["metros"]]
    assert metros == ["Chicago, IL", "Athens, OH"]
    assert result["metros"][0]["demand"] == 100.0
    assert result["hotspots"][0]["near"] == "Chicago, IL"
    with pytest.raises(ValueError):
        await demand.demand_map(deps, [], "Ohio")


async def test_demand_map_expands_regions_and_dedupes_border_cells(deps: Deps) -> None:
    result = await demand.demand_map(deps, ["H"], "Midwest + Texas")
    assert len(result["queried"]) == 13 and result["queried"][-1] == "Texas"
    assert result["cells"] == 2  # every state answered with the same two cells


def test_expand_region() -> None:
    assert demand.expand_region("Ohio") == ["Ohio"]
    assert demand.expand_region("the PNW, Idaho") == ["Oregon", "Washington", "Idaho"]
    assert "Wisconsin" in demand.expand_region("midwest")


async def test_server_exposes_seven_read_only_tools() -> None:
    tools = await mcp.list_tools()
    assert {t.name for t in tools} == {
        "resolve_artist", "search_tags", "demand_map", "find_venues", "find_openers", "find_sponsors", "find_promo_spots",
    }
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)
