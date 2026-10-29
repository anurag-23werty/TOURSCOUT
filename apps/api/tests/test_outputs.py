from __future__ import annotations

import json

import httpx
import pytest

from tourscout_api.agent.outputs import build_plan, fallback_brief, opener_dm, sponsor_pitch, to_csv, to_ics
from tourscout_api.core.config import LLMSettings
from tourscout_api.core.llm import LLM

pytestmark = pytest.mark.anyio

ROUTE = {"stops": [{"metro": "Columbus, OH", "date": "2027-04-02", "drive_km": 444, "travel_day_before": False}],
         "total_km": 444, "days_off": [], "dropped": []}
INTEL = {"Columbus, OH": {
    "venues": [{"id": "V1", "name": "Rumba Café", "address": "2507 Summit St, Columbus, OH"}, {"id": "V2", "name": "Ace of Cups"}],
    "openers": [{"id": "O1", "name": "Snarls", "badge": "based_here"}],
    "sponsors": [{"id": "B1", "name": "Baggu", "affinity": 0.98}],
    "promo": [{"id": "P1", "name": "Used Kids Records"}],
}}
METROS = {"Columbus, OH": {"label": "unserved", "demand": 82.0, "reach": 12.0, "gap": 70.0, "lat": 39.96, "lon": -83.0}}
ARTIST = {"name": "Hovvdy", "on_qloo": True}


def plan() -> dict:
    return build_plan(ARTIST, fallback_brief("Hovvdy", ROUTE, INTEL, METROS), ROUTE, INTEL, METROS, grounded=True)


def test_plan_resolves_names_from_ids() -> None:
    p = plan()
    stop = p["stops"][0]
    assert stop["venue"]["name"] == "Rumba Café" and stop["backup_venues"][0]["name"] == "Ace of Cups"
    assert stop["openers"][0]["name"] == "Snarls" and stop["label"] == "unserved"
    assert (stop["lat"], stop["lon"]) == (39.96, -83.0)  # the web map draws the route from these
    assert "demand 82" in stop["why"]


def test_csv_and_ics_exports() -> None:
    p = plan()
    rows = to_csv(p).splitlines()
    assert rows[0].startswith("date,city") and "Rumba Café" in rows[1] and "verify" in rows[1]
    ics = to_ics(p)
    assert ics.startswith("BEGIN:VCALENDAR") and "DTSTART;VALUE=DATE:20270402" in ics
    assert "SUMMARY:Hovvdy @ Rumba Café\\, Columbus\\, OH" in ics and ics.endswith("END:VCALENDAR\r\n")


def fake_llm(capture: dict) -> LLM:
    def handler(request: httpx.Request) -> httpx.Response:
        capture["prompt"] = json.loads(request.content)["messages"][-1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"subject": "Hi", "body": "Hello"})}}]})

    return LLM(LLMSettings(gemini_key="", groq_key="q"), httpx.MockTransport(handler))


async def test_pitch_and_dm_get_only_plan_facts() -> None:
    seen: dict = {}
    llm = fake_llm(seen)
    await sponsor_pitch(llm, plan(), "B1", national=[{"id": "B1", "name": "Baggu"}])
    assert "Baggu" in seen["prompt"] and '"national_rank":1' in seen["prompt"]
    await opener_dm(llm, plan(), "Columbus, OH")
    assert "Snarls" in seen["prompt"] and "Rumba Café" in seen["prompt"]
    with pytest.raises(ValueError):
        await sponsor_pitch(llm, plan(), "NOPE", national=[])
