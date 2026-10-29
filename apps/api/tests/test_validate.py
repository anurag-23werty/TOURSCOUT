from __future__ import annotations

from tourscout_api.agent.schemas import Brief, StopPlan
from tourscout_api.agent.validate import allowed_numbers, bad_numbers, validate_brief

ROUTE = {"stops": [{"metro": "Columbus, OH", "date": "2027-04-02", "drive_km": 444}], "total_km": 444}
INTEL = {"Columbus, OH": {
    "venues": [{"id": "V1", "name": "Rumba Café"}],
    "openers": [{"id": "O1", "name": "Snarls"}],
    "sponsors": [{"id": "B1", "name": "Baggu"}],
    "promo": [{"id": "P1", "name": "Used Kids Records"}],
}}
FACTS = {"route": ROUTE, "metros": [{"metro": "Columbus, OH", "demand": 82.4, "reach": 12.0, "gap": 70.4, "affinity": 0.81}]}


def brief(**stop) -> Brief:  # type: ignore[no-untyped-def]
    base = {"metro": "Columbus, OH", "date": "2027-04-02", "venue_id": "V1", "opener_ids": ["O1"], "sponsor_ids": ["B1"],
            "promo_ids": ["P1"], "why": "Demand 82 vs reach 12: a gap of 70 fans you aren't reaching; 81% affinity."}
    return Brief(headline="Hovvdy: 1 date", summary="444 km total.", stops=[StopPlan(**{**base, **stop})],
                 sponsor_strategy="Pitch Baggu.")


def test_grounded_brief_passes() -> None:
    assert validate_brief(brief(), ROUTE, INTEL, FACTS) == []


def test_invented_ids_and_numbers_are_caught() -> None:
    v = validate_brief(brief(venue_id="FAKE", opener_ids=["O1", "X"], why="Sold 5,000 tickets last year."), ROUTE, INTEL, FACTS)
    assert any("venue_id FAKE" in x for x in v)
    assert any("opener_ids contains X" in x for x in v)
    assert any("5,000" in x for x in v)


def test_route_metros_must_be_covered() -> None:
    assert validate_brief(brief(date="2027-04-03"), ROUTE, INTEL, FACTS) == []  # a wrong date is ignored: code owns dates
    v = validate_brief(brief(metro="Toledo, OH"), ROUTE, INTEL, FACTS)
    assert any("missing ['Columbus, OH'], unknown ['Toledo, OH']" in x for x in v)


def test_number_tolerance_and_ignored_tokens() -> None:
    allowed = allowed_numbers(FACTS)
    assert bad_numbers("demand 82.4 (82), 2 openers, April 2027, on 2027-04-02", allowed) == []
    assert bad_numbers("capacity 450", allowed) == ["450"]


def test_empty_venue_allowed_only_when_city_has_no_candidates() -> None:
    no_venues = {"Columbus, OH": {**INTEL["Columbus, OH"], "venues": []}}
    assert validate_brief(brief(venue_id=""), ROUTE, no_venues, FACTS) == []
    assert any("venue_id" in x for x in validate_brief(brief(venue_id=""), ROUTE, INTEL, FACTS))


def test_salvage_keeps_good_stops_and_replaces_bad_ones() -> None:
    from tourscout_api.agent.validate import salvage

    good, bad = brief(), brief(venue_id="FAKE", why="Sold 5,000 tickets.")
    fallback = brief(why="automatic")
    kept, replaced = salvage(good, fallback, INTEL, FACTS)
    assert replaced == 0 and kept.stops[0].why == good.stops[0].why
    fixed, replaced = salvage(bad, fallback, INTEL, FACTS)
    assert replaced == 1 and fixed.stops[0].why == "automatic"
