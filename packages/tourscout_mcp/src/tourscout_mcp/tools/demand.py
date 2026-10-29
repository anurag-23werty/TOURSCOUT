"""demand_map: where an artist's taste audience is, rolled up from Qloo heatmap cells to metros."""

from __future__ import annotations

import math
from typing import Any

from ..geo import aggregate_cells, cell_point, fold
from . import Deps, gather

HEATMAP = "urn:heatmap"

# Qloo's heatmap understands countries, states and cities, but musicians plan by region. Regions expand into states
# (US Census regions plus common touring names), queried in parallel and merged.
REGIONS = {
    "midwest": ["Illinois", "Indiana", "Iowa", "Kansas", "Michigan", "Minnesota", "Missouri", "Nebraska",
                "North Dakota", "Ohio", "South Dakota", "Wisconsin"],
    "northeast": ["Connecticut", "Maine", "Massachusetts", "New Hampshire", "New Jersey", "New York", "Pennsylvania",
                  "Rhode Island", "Vermont"],
    "southeast": ["Alabama", "Florida", "Georgia", "Kentucky", "Mississippi", "North Carolina", "South Carolina",
                  "Tennessee", "Virginia"],
    "southwest": ["Arizona", "New Mexico", "Oklahoma", "Texas"],
    "west coast": ["California", "Oregon", "Washington"],
    "pacific northwest": ["Oregon", "Washington"],
    "mountain west": ["Colorado", "Idaho", "Montana", "Nevada", "Utah", "Wyoming"],
    "great lakes": ["Illinois", "Indiana", "Michigan", "Minnesota", "Ohio", "Wisconsin", "New York", "Pennsylvania"],
}
REGIONS["pnw"] = REGIONS["pacific northwest"]


def expand_region(region: str) -> list[str]:
    """'Midwest' → its states; 'Midwest + Texas' or 'Ohio, Michigan' → each part; anything else is passed through."""
    parts = [p.strip() for p in region.replace("+", ",").replace(" and ", ",").split(",") if p.strip()]
    out: list[str] = []
    for part in parts:
        key = fold(part).removeprefix("the ").removeprefix("us ").removeprefix("u.s. ")
        for name in REGIONS.get(key, [part]):
            if name not in out:
                out.append(name)
    return out


def demand_score(affinity: float, population: int) -> float:
    """Raw demand: taste match × size. log10 keeps NYC from drowning out mid-sized markets."""
    return affinity * math.log10(max(population, 10))


async def demand_map(deps: Deps, artist_ids: list[str], region: str, top_n: int = 15) -> dict[str, Any]:
    if not artist_ids:
        raise ValueError("give at least one Qloo artist id (several ids blend into a 'sounds like' audience)")
    areas = expand_region(region)
    batches = await gather([
        (lambda area=area: deps.qloo.insights(HEATMAP, **{"signal.interests.entities": artist_ids, "filter.location.query": area}))
        for area in areas
    ])
    seen: set[str] = set()
    cells = []
    for cell in (c for batch in batches for c in batch):  # neighbouring states can return the same border cell
        geohash = (cell.get("location") or {}).get("geohash")
        if geohash and geohash in seen:
            continue
        seen.add(geohash)
        cells.append(cell)

    ranked_cells = sorted(cells, key=lambda c: (c["query"].get("affinity", 0) * c["query"].get("popularity", 0)), reverse=True)
    hotspots = []
    for c in ranked_cells[:10]:
        point = cell_point(c)
        metro = deps.metros.nearest(*point) if deps.metros and point else None
        hotspots.append({
            "geohash": c.get("location", {}).get("geohash"),
            "lat": round(point[0], 4) if point else None,
            "lon": round(point[1], 4) if point else None,
            "affinity": round(c["query"].get("affinity", 0), 3),
            "popularity": round(c["query"].get("popularity", 0), 3),
            "near": metro.label if metro else None,
        })

    result: dict[str, Any] = {
        "region": region, "queried": areas, "artist_ids": artist_ids, "cells": len(cells), "hotspots": hotspots,
    }
    if not cells:
        result["metros"] = []
        result["note"] = "Qloo returned no cells: use a country, state or city name (or a region like 'Midwest')"
        return result
    if not deps.metros:
        result["metros"] = []
        result["note"] = "metro roll-up unavailable: " + "; ".join(deps.notes)
        return result

    metros, unmapped = aggregate_cells(cells, deps.metros)
    scored = sorted(((demand_score(m.affinity, m.metro.population), m) for m in metros), key=lambda x: x[0], reverse=True)
    best = scored[0][0] if scored else 1.0
    result["unmapped_cells"] = unmapped
    result["metros"] = [
        {
            "metro": m.metro.label,
            "lat": round(m.metro.lat, 4),
            "lon": round(m.metro.lon, 4),
            "population": m.metro.population,
            "affinity": m.affinity,
            "activity": m.activity,
            "cells": m.cells,
            "demand": round(100 * raw / best, 1),  # 0–100 within this region
        }
        for raw, m in scored[:top_n]
    ]
    result["scoring"] = "demand = popularity-weighted cell affinity × log10(metro population), scaled so the top metro = 100"
    return result
