"""Reach ingest: what the artist already reaches, from their own data.

Three ways in: rows typed in the UI, a CSV export, or a screenshot of a streaming dashboard (Spotify for Artists /
Apple Music for Artists "top cities") that Gemini reads. Everything is mapped to the same metro labels as the demand map.
Uploads are parsed in memory and never stored.
"""

from __future__ import annotations

import base64
import csv
import io
import re
from collections.abc import Callable
from typing import Any

from tourscout_mcp.geo import Metro

from ..core.llm import LLM
from .prompts import prompt
from .schemas import ReachTable

CITY_HEADERS = {"city", "town", "location", "market", "metro"}
COUNT_HEADERS = {"listeners", "monthly listeners", "streams", "fans", "count", "audience"}


def parse_number(text: str) -> int | None:
    """'12,400' → 12400 · '12.4K' → 12400 · '1.2M' → 1200000."""
    m = re.fullmatch(r"\s*([\d.,]+)\s*([kKmM])?\s*", text or "")
    if not m:
        return None
    value = float(m.group(1).replace(",", "")) if m.group(1).count(".") <= 1 else None
    if value is None:
        return None
    return int(value * {"k": 1_000, "m": 1_000_000}.get((m.group(2) or "").lower(), 1))


def parse_csv(text: str) -> list[dict[str, Any]]:
    """CSV with a city column and a listeners/streams column (header names are matched loosely)."""
    reader = csv.DictReader(io.StringIO(text.strip()))
    fields = {f.strip().lower(): f for f in reader.fieldnames or []}
    city_col = next((fields[f] for f in fields if f in CITY_HEADERS), None)
    count_col = next((fields[f] for f in fields if f in COUNT_HEADERS), None)
    if not city_col or not count_col:
        raise ValueError(f"CSV needs a city column and a listeners column; got {list(fields)}")
    rows = []
    for row in reader:
        n = parse_number(row.get(count_col, ""))
        city = (row.get(city_col) or "").strip()
        if city and n:
            rows.append({"city": city, "listeners": n})
    return rows


async def read_screenshot(llm: LLM, image_b64: str, mime: str) -> list[dict[str, Any]]:
    table = await llm.json(
        ReachTable, prompt("reach_screenshot"), tier="main", purpose="reach_screenshot",
        image=(base64.b64decode(image_b64), mime),
    )
    return [r.model_dump() for r in table.rows if r.listeners > 0]


def to_metros(
    rows: list[dict[str, Any]], past_cities: list[str], find: Callable[[str], Metro | None]
) -> dict[str, Any]:
    """City names → metro labels. Listeners in the same metro add up (Brooklyn + New York)."""
    listeners: dict[str, int] = {}
    unmatched: list[str] = []
    for row in rows:
        metro = find(row["city"])
        if metro is None:
            unmatched.append(row["city"])
            continue
        listeners[metro.label] = listeners.get(metro.label, 0) + int(row["listeners"])
    played = []
    for city in past_cities:
        metro = find(city)
        if metro:
            played.append(metro.label)
        else:
            unmatched.append(city)
    return {"listeners": listeners, "played": played, "unmatched": unmatched}


async def ingest(llm: LLM, reach_input: dict[str, Any] | None) -> tuple[list[dict[str, Any]], str]:
    """Any supported input → (rows, source). Raises ValueError with a user-facing message."""
    reach_input = reach_input or {}
    if reach_input.get("rows"):
        return [{"city": r["city"], "listeners": int(r["listeners"])} for r in reach_input["rows"]], "rows"
    if reach_input.get("csv"):
        return parse_csv(reach_input["csv"]), "csv"
    if reach_input.get("image_b64"):
        return await read_screenshot(llm, reach_input["image_b64"], reach_input.get("mime", "image/png")), "screenshot"
    return [], "none"
