"""Turn a validated brief into the final plan and its outputs.

Names, addresses and numbers are filled in by code from the ids the brief chose, never copied from LLM text, so a
plan can't contain a venue or artist that no tool returned.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..core.llm import LLM, dumps
from .prompts import prompt
from .schemas import Brief, Pitch, RefineOps, StopPlan


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in rows}


def fallback_brief(artist: str, route: dict[str, Any], intel: dict[str, Any], metros: dict[str, dict[str, Any]]) -> Brief:
    """Used when the LLM is unavailable or can't produce a grounded brief: top-ranked picks, template text."""
    stops = []
    for s in route["stops"]:
        city = intel.get(s["metro"], {})
        m = metros.get(s["metro"], {})
        venues, openers = city.get("venues", []), city.get("openers", [])
        stops.append(StopPlan(
            metro=s["metro"], date=s["date"], venue_id=venues[0]["id"] if venues else "",
            opener_ids=[o["id"] for o in openers[:1]], sponsor_ids=[b["id"] for b in city.get("sponsors", [])[:1]],
            promo_ids=[p["id"] for p in city.get("promo", [])[:2]],
            why=f"{m.get('label', 'potential')}: demand {m.get('demand', 0):.0f}, reach {m.get('reach', 0):.0f}.",
        ))
    return Brief(
        headline=f"{artist}: {len(stops)} dates, {route['total_km']} km",
        summary="Picks are the top-ranked candidates per city (automatic summary: the writing model was unavailable).",
        stops=stops, sponsor_strategy="Start with the brands at the top of each city's sponsor list.",
        risks=["Venue capacity is not in the data: check each room before booking."],
    )


def build_plan(artist: dict[str, Any], brief: Brief, route: dict[str, Any], intel: dict[str, Any],
               metros: dict[str, dict[str, Any]], grounded: bool) -> dict[str, Any]:
    stops = []
    picks = {s.metro: s for s in brief.stops}
    auto = {s.metro: s for s in fallback_brief(artist.get("name", ""), route, intel, metros).stops}
    for r in route["stops"]:
        stop = picks.get(r["metro"]) or auto[r["metro"]]
        city = intel.get(stop.metro, {})
        venues, openers = _by_id(city.get("venues", [])), _by_id(city.get("openers", []))
        sponsors, promo = _by_id(city.get("sponsors", [])), _by_id(city.get("promo", []))
        m = metros.get(stop.metro, {})
        stops.append({
            "date": r["date"],
            "metro": r["metro"],
            "lat": m.get("lat"),
            "lon": m.get("lon"),
            "drive_km": r.get("drive_km"),
            "travel_day_before": r.get("travel_day_before", False),
            "label": m.get("label"),
            "demand": m.get("demand"),
            "reach": m.get("reach"),
            "gap": m.get("gap"),
            "venue": venues.get(stop.venue_id),
            "backup_venues": [v for vid, v in venues.items() if vid != stop.venue_id][:2],
            "openers": [openers[i] for i in stop.opener_ids if i in openers],
            "sponsors": [sponsors[i] for i in stop.sponsor_ids if i in sponsors],
            "promo": [promo[i] for i in stop.promo_ids if i in promo],
            "why": stop.why,
        })
    return {
        "artist": artist.get("name"),
        "on_qloo": artist.get("on_qloo"),
        "signal_names": artist.get("signal_names", []),
        "headline": brief.headline,
        "summary": brief.summary,
        "sponsor_strategy": brief.sponsor_strategy,
        "risks": brief.risks,
        "stops": stops,
        "days_off": route.get("days_off", []),
        "dropped": route.get("dropped", []),
        "total_km": route.get("total_km"),
        "grounded": grounded,
    }


# ---------------------------------------------------------------- exports


def to_csv(plan: dict[str, Any]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["date", "city", "label", "demand", "reach", "venue", "venue_address", "capacity", "openers", "sponsors", "drive_km"])
    for s in plan["stops"]:
        v = s["venue"] or {}
        w.writerow([
            s["date"], s["metro"], s["label"], s["demand"], s["reach"], v.get("name", ""), v.get("address", ""),
            "verify", "; ".join(o["name"] for o in s["openers"]), "; ".join(b["name"] for b in s["sponsors"]), s["drive_km"],
        ])
    return out.getvalue()


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def to_ics(plan: dict[str, Any]) -> str:
    """All-day events, one per show (RFC 5545)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TourScout//EN", "CALSCALE:GREGORIAN"]
    for s in plan["stops"]:
        day = date.fromisoformat(s["date"])
        venue = (s["venue"] or {}).get("name", "venue TBC")
        openers = ", ".join(o["name"] for o in s["openers"]) or "TBC"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{s['date']}-{re.sub(r'[^a-z0-9]+', '-', s['metro'].lower()).strip('-')}@tourscout",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_ics_escape(f'{plan['artist']} @ {venue}, {s['metro']}')}",
            f"LOCATION:{_ics_escape((s['venue'] or {}).get('address') or s['metro'])}",
            f"DESCRIPTION:{_ics_escape(f'Openers: {openers}. {s['why']}')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------- LLM-written outreach


async def sponsor_pitch(llm: LLM, plan: dict[str, Any], brand_id: str, national: list[dict[str, Any]]) -> Pitch:
    cities = [s for s in plan["stops"] if any(b["id"] == brand_id for b in s["sponsors"])]
    brand = next((b for s in cities for b in s["sponsors"] if b["id"] == brand_id), None)
    brand = brand or next((b for b in national if b["id"] == brand_id), None)
    if brand is None:
        raise ValueError(f"brand {brand_id} is not in this plan")
    facts = {
        "brand": brand,
        "national_rank": next((i + 1 for i, b in enumerate(national) if b["id"] == brand_id), None),
        "tour": [{"date": s["date"], "city": s["metro"]} for s in plan["stops"]],
        "cities_where_brand_ranks": [s["metro"] for s in cities],
    }
    return await llm.json(
        Pitch, prompt("sponsor_pitch", artist=plan["artist"], brand=brand["name"], facts=dumps(facts)),
        system=prompt("system"), purpose="sponsor_pitch",
    )


async def opener_dm(llm: LLM, plan: dict[str, Any], metro: str) -> Pitch:
    stop = next((s for s in plan["stops"] if s["metro"] == metro), None)
    if not stop or not stop["openers"]:
        raise ValueError(f"no opener picked for {metro}")
    opener, venue = stop["openers"][0], (stop["venue"] or {}).get("name", "TBC")
    facts = {"opener": opener, "date": stop["date"], "venue": venue, "city": metro}
    return await llm.json(
        Pitch, prompt("opener_dm", artist=plan["artist"], opener=opener["name"], city=metro, date=stop["date"],
                      venue=venue, facts=dumps(facts)),
        system=prompt("system"), tier="lite", purpose="opener_dm",
    )


async def parse_refine(llm: LLM, plan: dict[str, Any] | None, request: str) -> RefineOps:
    current = {"cities": [s["metro"] for s in (plan or {}).get("stops", [])]}
    return await llm.json(RefineOps, prompt("refine", current=dumps(current), request=request),
                          system=prompt("system"), tier="lite", purpose="refine")
