"""Eval metrics: the same checks applied to a TourScout plan and an LLM-only plan.

Each metric takes a normalised plan (see `normalise`) so both planners are scored identically.
"""

from __future__ import annotations

from typing import Any


def normalise_tourscout(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "city": s["metro"],
            "date": s["date"],
            "venue": (s.get("venue") or {}).get("name"),
            "venue_id": (s.get("venue") or {}).get("id"),
            "openers": [o["name"] for o in s.get("openers", [])],
            "sponsors": [b["name"] for b in s.get("sponsors", [])],
            "travel_day_before": s.get("travel_day_before", False),
        }
        for s in plan.get("stops", [])
    ]


def normalise_baseline(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "city": s["city"],
            "date": s["date"],
            "venue": s.get("venue"),
            "venue_id": None,
            "openers": [o for o in s.get("openers", []) if o and o.strip()],
            "sponsors": [b for b in s.get("sponsors", []) if b and b.strip()],
            "travel_day_before": False,
        }
        for s in plan.get("stops", [])
    ]


def rate(hits: int, total: int) -> float | None:
    return round(hits / total, 3) if total else None
