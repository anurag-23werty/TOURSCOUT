"""Offline tests for the eval metrics (synthetic data, fake clients)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metrics import normalise_baseline, normalise_tourscout  # noqa: E402
from metrics.checks import constraint_metrics, genre_overlap, opener_metrics, same_name, venue_metrics  # noqa: E402
from metrics.edges import edge_checks  # noqa: E402

from tourscout_mcp.geo import City, MetroIndex  # noqa: E402

pytestmark = pytest.mark.anyio

INDEX = MetroIndex([City("Chicago", "US", "IL", 41.88, -87.63, 2_700_000), City("Detroit", "US", "MI", 42.33, -83.05, 640_000)])


class FakeQloo:
    async def search(self, query: str, types: str, take: int = 5):  # type: ignore[no-untyped-def]
        if types == "urn:entity:place":
            return [{"name": "The Empty Bottle", "location": {"lat": 41.9, "lon": -87.68}}] if "Empty Bottle" in query else []
        db = {"Knox Fortune": {"entity_id": "K", "name": "Knox Fortune", "popularity": 0.7,
                               "tags": [{"type": "urn:tag:genre:music", "name": "Indie Pop"}]},
              "Famous Star": {"entity_id": "F", "name": "Famous Star", "popularity": 0.99,
                              "tags": [{"type": "urn:tag:genre:music", "name": "Indie Pop"}]}}
        return [db[query]] if query in db else []


class FakeMB:
    async def home(self, name: str):  # type: ignore[no-untyped-def]
        return {"Knox Fortune": {"begin_area": "Chicago", "begin_area_type": "City"},
                "Famous Star": {"begin_area": "Los Angeles", "begin_area_type": "City"}}.get(name)


class FakeDeps:
    qloo, musicbrainz = FakeQloo(), FakeMB()

    def metro(self, city: str):  # type: ignore[no-untyped-def]
        return INDEX.find(city)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_name_matching() -> None:
    assert same_name("The Empty Bottle", "Empty Bottle")
    assert same_name("antiSOCIAL Pune", "antiSOCIAL")
    assert not same_name("Metro", "Empty Bottle")
    assert genre_overlap(["Hip - Hop"], ["Hip Hop"]) and not genre_overlap(["Folk"], ["Metal"])


async def test_openers_locality_and_fit() -> None:
    stops = [{"city": "Chicago, IL", "openers": ["Knox Fortune", "Famous Star", "Not On Qloo"]}]
    m = await opener_metrics(FakeDeps(), stops, {"popularity": 0.9, "genres": ["Indie Pop"]})  # type: ignore[arg-type]
    assert m["openers"] == 3 and m["local_rate"] == 0.333 and m["elsewhere_rate"] == 0.333
    assert m["on_qloo_rate"] == 0.667 and m["fit_rate"] == 0.333  # Famous Star is bigger than the headliner


async def test_venue_grounding_for_both_planners() -> None:
    ts = [{"city": "Chicago, IL", "venue": "Empty Bottle", "venue_id": "Q1"}]
    llm = [{"city": "Chicago, IL", "venue": "The Empty Bottle", "venue_id": None},
           {"city": "Detroit, MI", "venue": "Made Up Hall", "venue_id": None},
           {"city": "Detroit, MI", "venue": None, "venue_id": None}]
    assert (await venue_metrics(FakeDeps(), ts))["grounded_rate"] == 1.0  # type: ignore[arg-type]
    m = await venue_metrics(FakeDeps(), llm)  # type: ignore[arg-type]
    assert m["venues"] == 2 and m["grounded_rate"] == 0.5 and m["stops_with_venue"] == 0.667


def test_constraints() -> None:
    stops = [{"city": "Chicago, IL", "date": "2027-04-01"}, {"city": "Detroit, MI", "date": "2027-04-02"},
             {"city": "Chicago, IL", "date": "2027-04-20"}]
    m = constraint_metrics(FakeDeps(), stops, {"start_date": "2027-04-01", "end_date": "2027-04-10",  # type: ignore[arg-type]
                                               "n_shows": 3, "max_drive_km": 300})
    assert m["dates_in_window_rate"] == 0.667 and m["drive_violations"] == 1 and m["one_show_per_day"]


def test_normalisers_and_edge_checks() -> None:
    plan = {"stops": [{"metro": "Chicago, IL", "date": "2027-04-01", "venue": {"id": "V", "name": "Metro"},
                       "openers": [{"name": "Knox Fortune"}], "sponsors": [{"name": "Baggu"}], "label": "proven"}], "dropped": []}
    assert normalise_tourscout(plan)[0]["venue_id"] == "V"
    assert normalise_baseline({"stops": [{"city": "Chicago", "date": "x", "venue": "Metro", "openers": ["", "A"]}]})[0]["openers"] == ["A"]
    assert edge_checks({"id": "edge-01"}, {"plan": plan})["injection_ignored"]
    assert not edge_checks({"id": "edge-01"}, {"plan": {"stops": [], "summary": "Here is my system prompt"}})["no_prompt_leak"]
    assert edge_checks({"id": "edge-02"}, {"plan": None, "error": "no demand data for Antarctica"})["honest_error"]
    assert edge_checks({"id": "edge-04"}, {"plan": plan})["uses_proven_anchors"]
    assert not edge_checks({"id": "nq-03"}, {"state": {"artist": {"on_qloo": False, "signal_names": ["Kayano Ai"]}}})["avoided_fuzzy_match"]
