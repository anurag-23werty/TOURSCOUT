"""Opener, venue and constraint checks. Network lookups go through the same Qloo/MusicBrainz clients as the app."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from tourscout_mcp.geo import fold, haversine_km
from tourscout_mcp.musicbrainz import local_badge
from tourscout_mcp.qloo import genre_tags
from tourscout_mcp.tools import Deps

from . import rate

VENUE_MATCH_KM = 60.0
STOPWORDS = {"the", "and", "of", "at", "club", "bar", "hall", "live", "music", "venue", "&"}


def name_tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", fold(name)) if t and t not in STOPWORDS}


def same_name(a: str, b: str) -> bool:
    """Loose venue-name match: 'The Empty Bottle' == 'Empty Bottle', 'antiSOCIAL Pune' ~ 'antiSOCIAL'."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return fold(a) == fold(b)
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.6


def genre_overlap(a: list[str], b: list[str]) -> bool:
    key = lambda g: re.sub(r"[^a-z0-9]", "", fold(g))  # noqa: E731
    return bool({key(g) for g in a} & {key(g) for g in b})


async def resolve_artist(deps: Deps, name: str) -> dict[str, Any] | None:
    """Exact-name Qloo artist, or None."""
    for a in await deps.qloo.search(name, "urn:entity:artist", 3):
        if fold(a.get("name", "")) == fold(name):
            return {"id": a["entity_id"], "popularity": a.get("popularity"), "genres": genre_tags(a)}
    return None


async def opener_metrics(deps: Deps, stops: list[dict[str, Any]], headliner: dict[str, Any] | None) -> dict[str, Any]:
    """Locality (MusicBrainz) and fit (Qloo: smaller than the headliner + overlapping genre) for every opener."""
    total = based_here = elsewhere = on_qloo = fits = 0
    for stop in stops:
        metro = deps.metro(stop["city"])
        names = metro.members if metro else {fold(stop["city"].split(",")[0])}
        for opener in stop["openers"]:
            total += 1
            home = await deps.musicbrainz.home(opener) if deps.musicbrainz else None
            badge = local_badge(home, names)
            based_here += badge == "based_here"
            elsewhere += badge == "elsewhere"
            found = await resolve_artist(deps, opener)
            if found:
                on_qloo += 1
                if headliner and found["popularity"] is not None and headliner.get("popularity") is not None:
                    smaller = found["popularity"] < headliner["popularity"]
                    fits += smaller and genre_overlap(found["genres"], headliner.get("genres", []))
    return {
        "openers": total,
        "local_rate": rate(based_here, total),
        "elsewhere_rate": rate(elsewhere, total),
        "on_qloo_rate": rate(on_qloo, total),
        "fit_rate": rate(fits, total),
    }


async def venue_metrics(deps: Deps, stops: list[dict[str, Any]]) -> dict[str, Any]:
    """A venue counts as grounded if it's a Qloo place id, or a Qloo place search finds it in that city."""
    total = grounded = 0
    for stop in stops:
        if not stop["venue"]:
            continue
        total += 1
        if stop["venue_id"]:
            grounded += 1  # TourScout: the id came from a Qloo tool call in this run
            continue
        metro = deps.metro(stop["city"])
        hits = await deps.qloo.search(f"{stop['venue']} {stop['city'].split(',')[0]}", "urn:entity:place", 5)
        for hit in hits:
            loc = hit.get("location") or {}
            near = (metro is not None and loc.get("lat") is not None
                    and haversine_km((loc["lat"], loc["lon"]), (metro.lat, metro.lon)) <= VENUE_MATCH_KM)
            if same_name(stop["venue"], hit.get("name", "")) and near:
                grounded += 1
                break
    return {"venues": total, "grounded_rate": rate(grounded, total), "stops_with_venue": rate(total, len(stops))}


def constraint_metrics(deps: Deps, stops: list[dict[str, Any]], intake: dict[str, Any]) -> dict[str, Any]:
    """Shows requested vs planned, dates inside the window, one show a day, long drives get a day off."""
    window = (intake.get("start_date"), intake.get("end_date"))
    dates = []
    for s in stops:
        try:
            dates.append(date.fromisoformat(s["date"]))
        except (TypeError, ValueError):
            dates.append(None)
    in_window = sum(
        d is not None and (not window[0] or d >= date.fromisoformat(window[0])) and (not window[1] or d <= date.fromisoformat(window[1]))
        for d in dates
    )
    unique_days = len({d for d in dates if d}) == len(stops)
    max_drive = intake.get("max_drive_km") or 0
    drive_violations = 0
    if max_drive:
        for prev, cur, d0, d1 in zip(stops, stops[1:], dates, dates[1:]):
            a, b = deps.metro(prev["city"]), deps.metro(cur["city"])
            if not (a and b and d0 and d1):
                continue
            km = haversine_km((a.lat, a.lon), (b.lat, b.lon)) * 1.25
            if km > max_drive and (d1 - d0).days < 2:
                drive_violations += 1
    return {
        "shows_requested": intake.get("n_shows"),
        "shows_planned": len(stops),
        "dates_in_window_rate": rate(in_window, len(stops)),
        "one_show_per_day": unique_days,
        "drive_violations": drive_violations,
        "unknown_cities": sum(deps.metro(s["city"]) is None for s in stops),
    }


async def headliner(deps: Deps, state: dict[str, Any]) -> dict[str, Any] | None:
    """The act whose size caps the openers: the artist, or the smallest "sounds like" artist."""
    head_id = (state.get("artist") or {}).get("headliner_id")
    entity = await deps.qloo.entity(head_id) if head_id else None
    if not entity:
        return None
    return {"popularity": entity.get("popularity"), "genres": genre_tags(entity)}
