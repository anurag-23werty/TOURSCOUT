from __future__ import annotations

from datetime import date

import pytest

from tourscout_api.scoring import Stop, plan_route, score, select_cities
from tourscout_api.scoring.opportunity import shrunk_affinity
from tourscout_api.scoring.route import order_stops, road_km

# Synthetic metros in the shape the demand_map tool returns (rounded real coordinates and populations).
METROS = [
    {"metro": "Chicago, IL", "lat": 41.88, "lon": -87.63, "population": 7_000_000, "affinity": 0.75, "cells": 40},
    {"metro": "Columbus, OH", "lat": 39.96, "lon": -83.00, "population": 1_200_000, "affinity": 0.81, "cells": 7},
    {"metro": "Lawrence, KS", "lat": 38.97, "lon": -95.24, "population": 95_000, "affinity": 1.00, "cells": 1},
    {"metro": "Bloomington, IN", "lat": 39.17, "lon": -86.53, "population": 85_000, "affinity": 0.95, "cells": 3},
    {"metro": "Detroit, MI", "lat": 42.33, "lon": -83.05, "population": 3_500_000, "affinity": 0.79, "cells": 7},
    {"metro": "Toledo, OH", "lat": 41.65, "lon": -83.54, "population": 330_000, "affinity": 0.40, "cells": 1},
]


def by_name(scores):  # type: ignore[no-untyped-def]
    return {s.metro: s for s in scores}


# ---------------------------------------------------------------- demand / reach / gap


def test_shrinkage_pulls_single_cell_metros_toward_the_mean() -> None:
    assert shrunk_affinity(1.0, 1, prior=0.8) == pytest.approx(0.8667, abs=1e-3)
    assert shrunk_affinity(0.75, 40, prior=0.8) == pytest.approx(0.752, abs=1e-3)


def test_demand_spans_0_to_100_and_one_cell_doesnt_win() -> None:
    s = by_name(score(METROS))
    assert s["Chicago, IL"].demand == 100.0
    assert s["Toledo, OH"].demand == 0.0
    assert s["Lawrence, KS"].demand < s["Columbus, OH"].demand  # 1 cell at 1.0 no longer beats 7 cells at 0.81


def test_no_reach_data_means_everything_is_potential_or_unserved() -> None:
    labels = {s.label for s in score(METROS)}
    assert "proven" not in labels


def test_reach_and_gap_labels() -> None:
    listeners = {"Chicago, IL": 40_000, "Detroit, MI": 300, "Columbus, OH": 20_000}
    s = by_name(score(METROS, listeners, played={"Bloomington, IN"}))
    assert s["Chicago, IL"].reach == 100.0 and s["Chicago, IL"].label == "proven"
    assert s["Detroit, MI"].label == "unserved" and s["Detroit, MI"].gap > 25
    assert s["Bloomington, IN"].reach == 60.0 and s["Bloomington, IN"].played_recently
    assert s["Toledo, OH"].label == "low"
    toledo = by_name(score(METROS, {"Toledo, OH": 5000}))["Toledo, OH"]
    assert toledo.demand == 0.0 and toledo.label == "proven"  # own listeners beat a low taste score
    assert any("fans you aren't reaching" in r for r in s["Detroit, MI"].reasons)


def test_select_mixes_anchors_and_growth_and_respects_excludes() -> None:
    scores = score(METROS, {"Chicago, IL": 40_000, "Columbus, OH": 30_000})
    chosen = [s.metro for s in select_cities(scores, 3, exclude={"Detroit, MI"})]
    assert len(chosen) == 3 and "Detroit, MI" not in chosen
    assert chosen[0] == "Chicago, IL"  # one proven anchor (a third of 3 dates)
    assert "Columbus, OH" not in chosen  # second proven city loses to growth markets
    forced = [s.metro for s in select_cities(scores, 2, include={"Toledo, OH"})]
    assert forced[0] == "Toledo, OH"


# ---------------------------------------------------------------- routing

HOME = (41.88, -87.63)  # Chicago


def stops(*names: str) -> list[Stop]:
    rows = {m["metro"]: m for m in METROS}
    return [Stop(n, rows[n]["lat"], rows[n]["lon"], priority=i) for i, n in enumerate(names)]


def test_road_km_applies_road_factor() -> None:
    assert road_km(HOME, (39.96, -83.00)) == pytest.approx(444 * 1.25, abs=12)


def test_two_opt_removes_zigzag() -> None:
    # Input order zigzags west–east; the ordered route should be cheaper than the given order.
    zigzag = stops("Columbus, OH", "Lawrence, KS", "Detroit, MI", "Bloomington, IN")
    ordered = order_stops(HOME, zigzag)
    names = [s.metro for s in ordered]
    assert names.index("Detroit, MI") in (0, len(names) - 1) or abs(names.index("Detroit, MI") - names.index("Columbus, OH")) == 1


def test_schedule_adds_travel_days_and_rest_days() -> None:
    route = plan_route(HOME, stops("Detroit, MI", "Columbus, OH", "Bloomington, IN"), date(2027, 4, 1), max_drive_km=300)
    assert [s.metro for s in route.stops][0] in ("Detroit, MI", "Bloomington, IN")
    assert route.stops[0].date == "2027-04-01"
    assert any(s.travel_day_before for s in route.stops[1:])  # some leg is > 300 km
    assert route.total_km > 0 and not route.dropped


def test_city_far_beyond_drive_limit_is_dropped() -> None:
    route = plan_route(HOME, stops("Lawrence, KS", "Detroit, MI"), date(2027, 4, 1), max_drive_km=300)
    # Lawrence is ~800 road km from Chicago: over 2 × 300 → dropped (it has the lower priority, 0).
    assert [d["metro"] for d in route.dropped] == ["Lawrence, KS"]
    assert [s.metro for s in route.stops] == ["Detroit, MI"]


def test_window_too_short_drops_lowest_priority() -> None:
    route = plan_route(HOME, stops("Toledo, OH", "Detroit, MI", "Columbus, OH"), date(2027, 4, 1),
                       end=date(2027, 4, 2), max_drive_km=1000)
    assert len(route.stops) == 2 and route.dropped[0] == {"metro": "Toledo, OH", "reason": "window too short"}


def test_rest_day_after_five_shows() -> None:
    near = [Stop(f"City {i}", 41.88 + i * 0.5, -87.63, priority=i) for i in range(6)]
    route = plan_route(HOME, near, date(2027, 4, 1), max_drive_km=1000)
    assert route.days_off == ["2027-04-06"] and route.stops[-1].date == "2027-04-07"


def test_long_drive_from_home_never_drops_cities() -> None:
    austin = (30.27, -97.74)  # ~1,900 road km from Chicago
    route = plan_route(austin, stops("Chicago, IL", "Detroit, MI"), date(2027, 4, 1), max_drive_km=650)
    assert not route.dropped and route.stops[0].drive_km > 1300
