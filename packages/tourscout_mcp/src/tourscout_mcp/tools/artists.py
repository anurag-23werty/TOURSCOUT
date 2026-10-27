"""resolve_artist, search_tags and find_openers."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..geo import fold
from ..musicbrainz import local_badge
from ..qloo import affinity, genre_tags, round_or_none, trim_artist
from . import Deps, gather

ARTIST = "urn:entity:artist"
OPENER_LOCATION_WEIGHT = 25  # Phase 1: the default weight returned mostly non-local acts
OPENER_POPULARITY_MARGIN = 0.05  # openers must be smaller than the headliner
FIT_WEIGHT, LOCAL_WEIGHT = 0.6, 0.4
BADGE_BONUS = {"based_here": 0.15, "unknown": 0.0, "elsewhere": -0.25}
NATIONAL_MIN_CITIES = 3  # an act in the top list of ≥ 3 cities is a national act, not a local one


async def resolve_artist(deps: Deps, name: str, take: int = 5) -> dict[str, Any]:
    found = await deps.qloo.search(name, ARTIST, take)
    candidates = [
        {"id": a.get("entity_id"), "name": a.get("name"), "popularity": round_or_none(a.get("popularity")),
         "genres": genre_tags(a)[:6]}
        for a in found
    ]
    exact = bool(candidates) and fold(candidates[0]["name"] or "") == fold(name)
    return {
        "query": name,
        "candidates": candidates,
        # Fuzzy search can return a different artist ("Kayan" → Kayano Ai), so the agent asks the user unless exact.
        "needs_confirmation": not exact,
    }


async def search_tags(deps: Deps, query: str, take: int = 10) -> list[dict[str, Any]]:
    tags = await deps.qloo.get("/v2/tags", {"filter.query": query, "take": take})
    return [{"id": t.get("id") or t.get("tag_id"), "name": t.get("name"), "type": t.get("type")} for t in tags]


def _genre_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(name))  # "Hip - Hop" == "Hip Hop", "R & B" == "R&B"


def genre_fit(headliner: list[str], opener: list[str]) -> float:
    """Jaccard overlap of genre tags, 0–1."""
    a, b = {_genre_key(g) for g in headliner}, {_genre_key(g) for g in opener}
    return round(len(a & b) / len(a | b), 3) if a | b else 0.0


async def find_openers(
    deps: Deps, headliner_id: str, cities: list[str], take: int = 6, check_local: bool = True
) -> dict[str, Any]:
    headliner = await deps.qloo.entity(headliner_id)
    if not headliner:
        raise ValueError(f"no Qloo artist with id {headliner_id}")
    head_pop = float(headliner.get("popularity") or 1.0)
    head_genres = genre_tags(headliner)
    cap = round(max(head_pop - OPENER_POPULARITY_MARGIN, 0.05), 3)

    def fetch(city: str):  # type: ignore[no-untyped-def]
        return lambda: deps.qloo.insights(
            ARTIST,
            **{
                "signal.interests.entities": headliner_id,
                "signal.location.query": city,
                "signal.location.weight": OPENER_LOCATION_WEIGHT,
                "filter.popularity.max": cap,
                "filter.exclude.entities": headliner_id,
                "take": 20,
            },
        )

    raw = await gather([fetch(c) for c in cities])

    # National acts: show up near the top in many cities (Jack Antonoff in Columbus and Chicago in Phase 1).
    tops = Counter(a["entity_id"] for rows in raw for a in rows[: take * 2])
    national = {eid for eid, n in tops.items() if n >= NATIONAL_MIN_CITIES} if len(cities) >= NATIONAL_MIN_CITIES else set()

    out = []
    for city, rows in zip(cities, raw):
        affs = [affinity(a) or 0.0 for a in rows]
        lo, hi = min(affs, default=0.0), max(affs, default=1.0)
        ranked, dropped = [], []
        for a in rows:
            if a["entity_id"] in national:
                dropped.append({"name": a.get("name"), "reason": f"national act (top list in ≥ {NATIONAL_MIN_CITIES} cities)"})
                continue
            row = trim_artist(a)
            row["fit"] = genre_fit(head_genres, genre_tags(a))
            row["local_pull"] = round(((affinity(a) or 0.0) - lo) / (hi - lo), 3) if hi > lo else 1.0
            row["qloo_city_tag"] = fold(city.split(",")[0]) in {fold(g) for g in genre_tags(a)}
            row["score"] = round(FIT_WEIGHT * row["fit"] + LOCAL_WEIGHT * row["local_pull"], 3)
            ranked.append(row)
        ranked.sort(key=lambda r: r["score"], reverse=True)
        out.append({"city": city, "openers": ranked[: take * 2], "dropped": dropped})

    if check_local and deps.musicbrainz:
        for entry in out:
            names = deps.metro_names(entry["city"])
            for row in entry["openers"][:take]:
                home = await deps.musicbrainz.home(row["name"])
                row["badge"] = local_badge(home, names)
                row["home"] = (home or {}).get("begin_area") or (home or {}).get("area")
                row["score"] = round(row["score"] + BADGE_BONUS[row["badge"]], 3)
    for entry in out:
        entry["openers"] = sorted(entry["openers"][:take], key=lambda r: r["score"], reverse=True)

    return {
        "headliner": {"id": headliner_id, "name": headliner.get("name"), "popularity": round(head_pop, 3), "genres": head_genres[:8]},
        "popularity_cap": cap,
        "scoring": f"score = {FIT_WEIGHT}·genre fit + {LOCAL_WEIGHT}·local pull (+0.15 based here / −0.25 based elsewhere, MusicBrainz)",
        "cities": out,
    }
