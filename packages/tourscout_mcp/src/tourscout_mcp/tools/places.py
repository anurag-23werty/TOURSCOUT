"""find_venues, find_promo_spots and find_sponsors."""

from __future__ import annotations

from typing import Any

from ..qloo import affinity, trim_brand, trim_place
from . import Deps, gather

PLACE, BRAND = "urn:entity:place", "urn:entity:brand"
# Phase 1: the category tag returns theatres and halls, the setting tag returns clubs; merged they cover room sizes.
VENUE_TAGS = ["urn:tag:category:place:live_music_venue", "urn:tag:setting:qloo:music_venue"]
PROMO_TAGS = {
    "record_store": "urn:tag:category:place:record_store",
    "book_store": "urn:tag:category:place:book_store",
    "coffee_shop": "urn:tag:category:place:coffee_shop",
    "bar": "urn:tag:category:place:bar",
}


def _places(deps: Deps, artist_ids: list[str], city: str, tag: str, take: int):  # type: ignore[no-untyped-def]
    return lambda: deps.qloo.insights(
        PLACE,
        **{"signal.interests.entities": artist_ids, "filter.location.query": city, "filter.tags": tag, "take": take},
    )


async def find_venues(deps: Deps, artist_ids: list[str], city: str, take: int = 10) -> dict[str, Any]:
    batches = await gather([_places(deps, artist_ids, city, tag, take) for tag in VENUE_TAGS])
    merged: dict[str, dict[str, Any]] = {}
    for tag, rows in zip(VENUE_TAGS, batches):
        for p in rows:
            if not (p.get("properties") or {}).get("address"):
                continue  # entities without an address are areas, not rooms
            row = merged.setdefault(p["entity_id"], {**trim_place(p), "matched_tags": []})
            row["affinity"] = max(row["affinity"] or 0, affinity(p) or 0)
            row["matched_tags"].append(tag.rsplit(":", 1)[-1])
    venues = sorted(merged.values(), key=lambda r: r["affinity"] or 0, reverse=True)[:take]
    for v in venues:
        v["capacity"] = "verify"  # Qloo has no capacity field; never guess one
    return {"city": city, "venues": venues}


async def find_promo_spots(
    deps: Deps, artist_ids: list[str], city: str, kinds: list[str] | None = None, take: int = 5
) -> dict[str, Any]:
    kinds = kinds or list(PROMO_TAGS)
    unknown = [k for k in kinds if k not in PROMO_TAGS]
    if unknown:
        raise ValueError(f"unknown promo kinds {unknown}; choose from {list(PROMO_TAGS)}")
    batches = await gather([_places(deps, artist_ids, city, PROMO_TAGS[k], take) for k in kinds])
    return {
        "city": city,
        "spots": {
            kind: [trim_place(p) for p in rows if (p.get("properties") or {}).get("address")][:take]
            for kind, rows in zip(kinds, batches)
        },
    }


async def find_sponsors(deps: Deps, artist_ids: list[str], cities: list[str] | None = None, take: int = 10) -> dict[str, Any]:
    cities = cities or []

    def fetch(city: str | None):  # type: ignore[no-untyped-def]
        params: dict[str, Any] = {"signal.interests.entities": artist_ids, "take": take}
        if city:
            params["signal.location.query"] = city
        return lambda: deps.qloo.insights(BRAND, **params)

    national, *per_city = await gather([fetch(None), *(fetch(c) for c in cities)])
    nat = {b["entity_id"]: affinity(b) or 0.0 for b in national}
    city_out = []
    for city, rows in zip(cities, per_city):
        brands = []
        for b in rows:
            row = trim_brand(b)
            if b["entity_id"] in nat:
                row["uplift"] = round((row["affinity"] or 0) - nat[b["entity_id"]], 3)
                row["new_in_city"] = False
            else:
                row["uplift"], row["new_in_city"] = None, True  # not in the national top list: a local angle
            brands.append(row)
        city_out.append({"city": city, "brands": brands})
    return {"national": [trim_brand(b) for b in national], "cities": city_out}
