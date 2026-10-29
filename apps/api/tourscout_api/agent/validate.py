"""Grounding validator: the composed brief may only use entities and numbers the tools and scoring produced.

Checks
1. Stops cover every metro of the computed route exactly once (dates and order come from the route, not the model).
2. Every venue / opener / sponsor / promo id was returned by a tool for that metro.
3. Every number in the text is one we computed (with rounding tolerance) or a small count/date part.
Violations go back to the composer for a retry.
"""

from __future__ import annotations

import re
from typing import Any

from .schemas import Brief, StopPlan

NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w])")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
SMALL_OK = set(range(0, 13))  # counts like "2 openers", "10 dates", months


def allowed_numbers(*sources: Any) -> set[float]:
    """Every number found anywhere in the facts, plus percentage and rounded forms."""
    out: set[float] = set()

    def walk(x: Any) -> None:
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            out.update({float(x), float(round(x)), round(float(x), 1)})
            if 0 <= x <= 1:
                out.update({round(x * 100), round(x * 100, 1)})  # 0.95 affinity → "95%"
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
        elif isinstance(x, str) and len(x) < 40:
            for n in NUMBER.findall(x):
                walk(float(n.replace(",", "")))

    for s in sources:
        walk(s)
    return out


def bad_numbers(text: str, allowed: set[float]) -> list[str]:
    text = DATE.sub(" ", text)
    bad = []
    for raw in NUMBER.findall(text):
        value = float(raw.replace(",", ""))
        if value in SMALL_OK or 1900 <= value <= 2100:
            continue
        if any(abs(value - a) <= max(0.51, abs(a) * 0.01) for a in allowed):
            continue
        bad.append(raw)
    return bad


def stop_violations(stop: StopPlan, intel: dict[str, Any], allowed: set[float]) -> list[str]:
    city = intel.get(stop.metro)
    if city is None:
        return [f"{stop.metro} is not on the route"]
    out = []
    ids = {k: {e["id"] for e in city.get(k, [])} for k in ("venues", "openers", "sponsors", "promo")}
    if not ids["venues"] and not stop.venue_id:
        pass  # no venue candidates for this city: an empty pick is the honest answer
    elif stop.venue_id not in ids["venues"]:
        out.append(f"{stop.metro}: venue_id {stop.venue_id} is not one of the candidate venues")
    for field, key in (("opener_ids", "openers"), ("sponsor_ids", "sponsors"), ("promo_ids", "promo")):
        for eid in getattr(stop, field):
            if eid not in ids[key]:
                out.append(f"{stop.metro}: {field} contains {eid}, not a candidate for this city")
    bad = bad_numbers(stop.why, allowed)
    if bad:
        out.append(f"why[{stop.metro}]: numbers {bad} are not in the data; use only given numbers")
    return out


def text_violations(brief: Brief, allowed: set[float]) -> list[str]:
    texts = [("headline", brief.headline), ("summary", brief.summary), ("sponsor_strategy", brief.sponsor_strategy)]
    texts += [("risks", r) for r in brief.risks]
    return [f"{where}: numbers {bad} are not in the data; use only given numbers"
            for where, text in texts if (bad := bad_numbers(text, allowed))]


def validate_brief(brief: Brief, route: dict[str, Any], intel: dict[str, Any], facts: Any) -> list[str]:
    violations: list[str] = []
    expected = [s["metro"] for s in route["stops"]]
    got = [s.metro for s in brief.stops]
    missing, extra = [m for m in expected if m not in got], [m for m in got if m not in expected]
    dupes = sorted({m for m in got if got.count(m) > 1})
    if missing or extra or dupes:
        violations.append(f"stops must cover each route metro exactly once: missing {missing}, unknown {extra}, repeated {dupes}")
    allowed = allowed_numbers(facts)
    for stop in brief.stops:
        violations += stop_violations(stop, intel, allowed)
    return violations + text_violations(brief, allowed)


def salvage(brief: Brief, fallback: Brief, intel: dict[str, Any], facts: Any) -> tuple[Brief, int]:
    """Keep the model's stops and text that pass every check; replace the rest with the automatic picks.

    Returns the merged brief and how many stops were replaced.
    """
    allowed = allowed_numbers(facts)
    good = {s.metro: s for s in brief.stops if s.metro in intel and not stop_violations(s, intel, allowed)}
    stops = [good.get(s.metro, s) for s in fallback.stops]
    texts_ok = not text_violations(brief, allowed)
    merged = Brief(
        headline=brief.headline if texts_ok else fallback.headline,
        summary=brief.summary if texts_ok else fallback.summary,
        sponsor_strategy=brief.sponsor_strategy if texts_ok else fallback.sponsor_strategy,
        risks=brief.risks if texts_ok else fallback.risks,
        stops=stops,
    )
    return merged, sum(s.metro not in good for s in fallback.stops)
