"""End-to-end agent tests with a fake toolbox and a fake LLM (synthetic data only)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from langgraph.types import Command

from tourscout_api.agent.graph import AgentContext
from tourscout_api.agent.runner import TourAgent
from tourscout_api.agent.schemas import Brief, Intake, Pitch, RefineOps, SimilarArtists, StopPlan
from tourscout_api.core.llm import LLM, LLMUnavailable
from tourscout_mcp.geo import City, MetroIndex

pytestmark = pytest.mark.anyio

CITIES = {
    "Chicago": (41.88, -87.63, 2_700_000), "Columbus": (39.96, -83.00, 900_000), "Detroit": (42.33, -83.05, 640_000),
    "Milwaukee": (43.04, -87.91, 570_000), "Madison": (43.07, -89.40, 270_000), "Austin": (30.27, -97.74, 960_000),
}
INDEX = MetroIndex([City(n, "US", {"Columbus": "OH", "Detroit": "MI", "Austin": "TX"}.get(n, "IL" if n == "Chicago" else "WI"),
                         lat, lon, pop) for n, (lat, lon, pop) in CITIES.items()])
ARTISTS = {
    "Hovvdy": [{"id": "HV", "name": "Hovvdy", "popularity": 0.9, "genres": []}],
    "Easy Wanderlings": [{"id": "ES", "name": "Easy Star All-Stars", "popularity": 0.8, "genres": []}],
    "Prateek Kuhad": [{"id": "PK", "name": "Prateek Kuhad", "popularity": 0.86, "genres": []}],
    "Fleet Foxes": [{"id": "FF", "name": "Fleet Foxes", "popularity": 0.97, "genres": []}],
}


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.no_venues: set[str] = set()

    def metro(self, city: str):  # type: ignore[no-untyped-def]
        return INDEX.find(city)

    async def resolve_artist(self, name: str) -> dict[str, Any]:
        cands = ARTISTS.get(name, [])
        return {"query": name, "candidates": cands, "needs_confirmation": not cands or cands[0]["name"] != name}

    async def demand_map(self, ids: list[str], region: str, top_n: int = 40) -> dict[str, Any]:
        self.calls.append(f"demand:{','.join(ids)}:{region}")
        rows = [("Chicago", 0.75, 40), ("Columbus", 0.81, 7), ("Detroit", 0.79, 7), ("Milwaukee", 0.75, 11), ("Madison", 0.9, 5)]
        if "Texas" in region:
            rows.append(("Austin", 0.95, 9))
        metros = []
        for name, aff, cells in rows:
            m = INDEX.find(name)
            metros.append({"metro": m.label, "lat": m.lat, "lon": m.lon, "population": m.population, "affinity": aff, "cells": cells})
        return {"cells": 70, "metros": metros}

    async def find_venues(self, ids: list[str], city: str, take: int = 5) -> dict[str, Any]:
        if city in self.no_venues:
            return {"city": city, "venues": []}
        slug = city.split(",")[0][:3].upper()
        return {"city": city, "venues": [{"id": f"V-{slug}-1", "name": f"{city} Hall", "address": "1 Main St"},
                                         {"id": f"V-{slug}-2", "name": f"{city} Club", "address": "2 Main St"}]}

    async def find_promo_spots(self, ids: list[str], city: str, take: int = 3) -> dict[str, Any]:
        return {"city": city, "spots": {"record_store": [{"id": f"P-{city[:3]}", "name": f"{city} Records", "address": "x"}]}}

    async def find_openers(self, headliner_id: str, cities: list[str], take: int = 3) -> dict[str, Any]:
        self.calls.append(f"openers:{headliner_id}")
        return {"cities": [{"city": c, "openers": [{"id": f"O-{c[:3]}", "name": f"{c} Band", "badge": "based_here"}]} for c in cities]}

    async def find_sponsors(self, ids: list[str], cities: list[str], take: int = 6) -> dict[str, Any]:
        return {"national": [{"id": "B1", "name": "Baggu", "affinity": 0.98}],
                "cities": [{"city": c, "brands": [{"id": "B1", "name": "Baggu", "uplift": 0.01, "new_in_city": False}]} for c in cities]}

    async def aclose(self) -> None:
        pass


def facts_from(prompt_text: str) -> dict[str, Any]:
    start = prompt_text.index("FACTS (the only data you may use):\n") + len("FACTS (the only data you may use):\n")
    return json.loads(prompt_text[start : prompt_text.index("\n\nInstructions")])


class FakeLLM(LLM):
    """Answers by schema. compose_plan controls the composer: 'good', 'bad_then_good', 'always_bad', 'down'."""

    def __init__(self, compose_plan: str = "good") -> None:
        super().__init__()
        self.compose_plan, self.compose_calls, self.purposes = compose_plan, 0, []

    async def json(self, schema, prompt, system="", tier="main", purpose="", image=None, patience_s=None):  # type: ignore[no-untyped-def,override]
        self.purposes.append(purpose or schema.__name__)
        if schema is Intake:
            return Intake(artist="Hovvdy", home_base="Chicago", regions=["Midwest"], start_date="2027-04-01", n_shows=4,
                          max_drive_km=700)
        if schema is SimilarArtists:
            return SimilarArtists(artists=["Prateek Kuhad", "Fleet Foxes", "Unknown Act"])
        if schema is RefineOps:
            return RefineOps(exclude_cities=["Detroit"])
        if schema is Pitch:
            return Pitch(subject="Tour partnership", body="Hello")
        if schema is Brief:
            self.compose_calls += 1
            if self.compose_plan == "down":
                raise LLMUnavailable("both providers down")
            bad = self.compose_plan == "always_bad" or (self.compose_plan == "bad_then_good" and self.compose_calls == 1)
            f = facts_from(prompt)
            stops = []
            for s in f["route"]:
                city = f["cities"][s["metro"]]
                stops.append(StopPlan(
                    metro=s["metro"], date=s["date"], venue_id="INVENTED" if bad else city["venues"][0]["id"],
                    opener_ids=[city["openers"][0]["id"]], sponsor_ids=["B1"], promo_ids=[city["promo"][0]["id"]],
                    why="Sold 9,999 tickets here." if bad else "Strong demand for your sound.",
                ))
            return Brief(headline="Spring run", summary="A short Midwest loop.", stops=stops, sponsor_strategy="Pitch Baggu.")
        raise AssertionError(f"unexpected schema {schema}")


def agent(compose_plan: str = "good") -> tuple[TourAgent, FakeLLM, FakeTools]:
    llm, tools = FakeLLM(compose_plan), FakeTools()
    return TourAgent(AgentContext(llm, tools)), llm, tools  # type: ignore[arg-type]


HOVVDY = {"artist": "Hovvdy", "home_base": "Chicago", "regions": ["Midwest"], "start_date": "2027-04-01",
          "n_shows": 4, "max_drive_km": 700, "past_cities": ["Chicago"]}


async def test_full_auto_run_is_grounded_and_complete() -> None:
    a, llm, _ = agent()
    out = await a.start("t1", intake=HOVVDY, reach_input={"rows": [{"city": "Chicago", "listeners": 12000}]}, auto_approve=True)
    plan = out["state"]["plan"]
    assert out["done"] and out["interrupt"] is None
    assert plan["composed_by"] == "llm" and plan["on_qloo"] is True
    assert len(plan["stops"]) == 4 and all(s["venue"] for s in plan["stops"])
    assert [s["date"] for s in plan["stops"]] == sorted(s["date"] for s in plan["stops"])
    assert plan["outreach"]["sponsor_pitch"]["brand"] == "Baggu" and "opener_dm" in plan["outreach"]
    nodes = [e["node"] for e in out["state"]["events"]]
    assert nodes[:3] == ["intake", "resolve", "confirm_artist"] and nodes[-1] == "outputs"
    assert "intake" not in llm.purposes  # structured intake given: no LLM call needed


async def test_free_text_request_uses_intake_model() -> None:
    a, llm, _ = agent()
    out = await a.start("t2", request="I'm Hovvdy, 4 shows in the Midwest from April", auto_approve=True)
    assert llm.purposes[0] == "intake" and out["done"]


async def test_sounds_like_path_for_artist_not_on_qloo() -> None:
    a, llm, tools = agent()
    out = await a.start("t3", intake={**HOVVDY, "artist": "Easy Wanderlings"}, auto_approve=True)
    artist = out["state"]["artist"]
    assert artist["on_qloo"] is False and artist["signal_names"] == ["Prateek Kuhad", "Fleet Foxes"]
    assert artist["headliner_id"] == "PK"  # the smaller similar artist sets the opener size cap
    assert "similar_artists" in llm.purposes  # no sounds_like given → the LLM suggested names, Qloo grounded them
    assert any(c.startswith("demand:PK,FF") for c in tools.calls)


async def test_human_checkpoints_pause_and_resume() -> None:
    a, _, _ = agent()
    first = await a.start("t4", intake=HOVVDY)
    assert first["interrupt"]["type"] == "confirm_artist" and first["interrupt"]["candidates"][0]["id"] == "HV"
    second = await a.resume("t4", {"choice": "HV"})
    assert second["interrupt"]["type"] == "pick_cities"
    picked = second["interrupt"]["selected"][:2]
    final = await a.resume("t4", {"selected": picked})
    assert final["done"] and [s["metro"] for s in final["state"]["route"]["stops"]] != []
    assert {s["metro"] for s in final["state"]["plan"]["stops"]} == set(picked)


async def test_validator_sends_bad_brief_back_once() -> None:
    a, llm, _ = agent("bad_then_good")
    out = await a.start("t5", intake=HOVVDY, auto_approve=True)
    assert llm.compose_calls == 2 and out["state"]["plan"]["composed_by"] == "llm"
    msgs = [e["message"] for e in out["state"]["events"] if e["node"] == "validate"]
    assert "problems" in msgs[0] and msgs[-1] == "grounded ✓"


async def test_falls_back_to_automatic_plan_when_llm_never_grounds() -> None:
    for mode, calls, composed in (("always_bad", 3, "llm (4 stops auto-filled)"), ("down", 1, "fallback")):
        a, llm, _ = agent(mode)
        out = await a.start(f"t6-{mode}", intake=HOVVDY, auto_approve=True)
        plan = out["state"]["plan"]
        assert llm.compose_calls == calls and plan["composed_by"] == composed
        assert all(s["venue"]["id"].startswith("V-") for s in plan["stops"])  # still only real candidates
        assert not any("9,999" in s["why"] for s in plan["stops"])


def test_aliases_shrink_ids_and_map_back() -> None:
    from tourscout_api.agent.graph import aliased, dealias

    intel = {"Chicago, IL": {"venues": [{"id": "UUID-V"}], "openers": [], "sponsors": [{"id": "UUID-B"}], "promo": []},
             "Columbus, OH": {"venues": [], "openers": [], "sponsors": [{"id": "UUID-B"}], "promo": []}}
    cities, to_id = aliased(intel, ["Chicago, IL", "Columbus, OH"])
    assert cities["Chicago, IL"]["venues"][0]["id"] == "c1v1" and cities["Columbus, OH"]["sponsors"][0]["id"] == "b1"
    brief = Brief(headline="h", summary="s", sponsor_strategy="x", stops=[
        StopPlan(metro="Chicago, IL", date="2027-04-01", venue_id="c1v1", sponsor_ids=["b1", "b9"], why="w")])
    out = dealias(brief, to_id).stops[0]
    assert out.venue_id == "UUID-V" and out.sponsor_ids == ["UUID-B", "b9"]  # unknown alias left for the validator


async def test_cities_without_venues_are_swapped_out() -> None:
    a, _, tools = agent()
    tools.no_venues = {"Madison, WI"}
    out = await a.start("t8", intake={**HOVVDY, "n_shows": 3}, auto_approve=True)
    first_pick = [m for m in out["state"]["selected"]]
    stops = [s["metro"] for s in out["state"]["plan"]["stops"]]
    assert "Madison, WI" not in stops and len(stops) == 3 and first_pick == out["state"]["selected"]
    assert any("swapping" in e["message"] for e in out["state"]["events"])


async def test_refine_reruns_from_scoring_on_same_thread() -> None:
    a, _, _ = agent()
    intake = {**HOVVDY, "n_shows": 5}
    before = await a.start("t7", intake=intake, auto_approve=True)
    assert "Detroit, MI" in [s["metro"] for s in before["state"]["plan"]["stops"]]
    after = await a.refine("t7", "skip Detroit")
    metros = [s["metro"] for s in after["state"]["plan"]["stops"]]
    assert "Detroit, MI" not in metros and after["done"]
    assert any(e["node"] == "refine" for e in after["state"]["events"])


async def test_stream_yields_steps_then_exactly_one_outcome() -> None:
    a, _, _ = agent()
    payload = TourAgent.start_payload(intake=HOVVDY)
    kinds = [k async for k, _ in a.stream("t9", payload)]
    assert kinds == ["step", "step", "interrupt"]  # intake, resolve, then ⏸ confirm_artist
    resumed = [(k, v) async for k, v in a.stream("t9", Command(resume={"choice": "HV"}))]
    assert resumed[-1][0] == "interrupt" and resumed[-1][1]["type"] == "pick_cities"
    final = [(k, v) async for k, v in a.stream("t9", Command(resume={"accept": True}))]  # {} would not resume
    assert final[-1][0] == "plan" and final[-1][1]["stops"]


async def test_stream_turns_user_errors_into_an_error_event() -> None:
    a, _, _ = agent()
    out = [(k, v) async for k, v in a.stream("t10", TourAgent.start_payload(intake={**HOVVDY, "artist": "Nobody", "sounds_like": ["Nobody Else"]}, auto_approve=True))]
    assert out[-1][0] == "error" and "on Qloo" in out[-1][1]


async def test_sqlite_checkpointer_survives_a_new_agent(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from tourscout_api.core import checkpoint

    monkeypatch.setattr(checkpoint, "DEFAULT_SQLITE", tmp_path / "cp.sqlite")
    async with checkpoint.open_checkpointer("") as saver:
        llm, tools = FakeLLM(), FakeTools()
        first = TourAgent(AgentContext(llm, tools), saver)  # type: ignore[arg-type]
        await first.start("t11", intake=HOVVDY)
    async with checkpoint.open_checkpointer("") as saver:  # "restart": new connection, new agent
        second = TourAgent(AgentContext(FakeLLM(), FakeTools()), saver)  # type: ignore[arg-type]
        assert (await second.state("t11"))["interrupt"]["type"] == "confirm_artist"
        done = await second.resume("t11", {"choice": "HV"})
        assert done["interrupt"]["type"] == "pick_cities"


async def test_refine_with_human_in_the_loop_doesnt_ask_again() -> None:
    a, _, _ = agent()
    await a.start("t12", intake={**HOVVDY, "n_shows": 5})
    await a.resume("t12", {"choice": "HV"})
    await a.resume("t12", {"accept": True})
    after = await a.refine("t12", "skip Detroit")
    assert after["done"] and after["interrupt"] is None


async def test_pick_cities_lists_every_suggested_city() -> None:
    a, _, _ = agent()
    await a.start("t13", intake=HOVVDY, reach_input={"rows": [{"city": "Milwaukee", "listeners": 9000}]})
    pick = (await a.resume("t13", {"choice": "HV"}))["interrupt"]
    listed = [m["metro"] for m in pick["metros"]]
    assert set(pick["selected"]) <= set(listed) and listed[: len(pick["selected"])] == [
        m for m in listed if m in pick["selected"]]
