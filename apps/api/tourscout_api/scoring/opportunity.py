"""Demand vs reach → where the unserved fans are.

Pure functions, no I/O, so every number in a tour plan can be traced back to a formula here.

    demand  D (0–100)  how much the artist's taste audience over-indexes in a metro (from the Qloo heatmap)
    reach   R (0–100)  how much the artist already reaches it (their streaming listeners, past shows)
    gap     D − R      positive = fans the artist isn't reaching yet
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

Label = Literal["unserved", "proven", "potential", "low"]

# Bayesian shrinkage: a metro backed by one heatmap cell with affinity 1.0 shouldn't outrank Chicago's 40 cells.
# Each metro's affinity is pulled toward the region mean as if it had PRIOR_CELLS extra cells at that mean.
PRIOR_CELLS = 2
SERVED_REACH = 60.0  # a city the artist played recently counts as reached at least this much
HIGH_DEMAND, LOW_DEMAND = 60.0, 35.0
UNSERVED_GAP = 25.0
PROVEN_REACH = 50.0
ANCHOR_SHARE = 1 / 3  # up to a third of the dates go to proven cities that will sell tickets


@dataclass
class MetroScore:
    metro: str
    lat: float
    lon: float
    population: int
    affinity: float
    cells: int
    demand: float = 0.0
    reach: float = 0.0
    gap: float = 0.0
    label: Label = "low"
    listeners: int | None = None
    played_recently: bool = False
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def shrunk_affinity(affinity: float, cells: int, prior: float, k: int = PRIOR_CELLS) -> float:
    return (cells * affinity + k * prior) / (cells + k)


def demand_scores(metros: list[dict[str, Any]]) -> list[MetroScore]:
    """Metros from the demand_map tool → MetroScore with demand 0–100 (min–max within the candidate set)."""
    if not metros:
        return []
    total_cells = sum(m["cells"] for m in metros) or 1
    prior = sum(m["affinity"] * m["cells"] for m in metros) / total_cells
    raw = [shrunk_affinity(m["affinity"], m["cells"], prior) * math.log10(max(m["population"], 10)) for m in metros]
    lo, hi = min(raw), max(raw)
    out = []
    for m, r in zip(metros, raw):
        out.append(MetroScore(
            metro=m["metro"], lat=m["lat"], lon=m["lon"], population=m["population"], affinity=m["affinity"],
            cells=m["cells"], demand=round(100 * (r - lo) / (hi - lo), 1) if hi > lo else 100.0,
        ))
    return out


def reach_scores(
    scores: list[MetroScore], listeners: dict[str, int] | None = None, played: set[str] | None = None
) -> None:
    """Fill reach in place. listeners and played are keyed by metro label (match city names to metros upstream).

    R = 100 · sqrt(listeners / max listeners); a city played recently gets at least SERVED_REACH.
    (A log scale was tried first: it rated 300 listeners vs a 40k top city as reach 54, i.e. "proven". sqrt gives 9.)
    Without any data R = 0, so every city reads as potential and the UI says so.
    """
    listeners, played = listeners or {}, played or set()
    top = max(listeners.values(), default=0)
    for s in scores:
        n = listeners.get(s.metro)
        s.listeners = n
        s.reach = round(100 * math.sqrt(n / top), 1) if n and top else 0.0
        if s.metro in played:
            s.played_recently = True
            s.reach = max(s.reach, SERVED_REACH)


def label(s: MetroScore) -> Label:
    # The artist's own fans outrank the taste model: a city with real listeners is an anchor even if Qloo's
    # over-index is modest there (Phase 3: Mumbai/Pune for an Indian band were "low" on demand alone).
    if s.reach >= PROVEN_REACH:
        return "proven"
    if s.demand < LOW_DEMAND:
        return "low"
    if s.demand >= HIGH_DEMAND and s.gap >= UNSERVED_GAP:
        return "unserved"
    return "potential"


def score(
    metros: list[dict[str, Any]], listeners: dict[str, int] | None = None, played: set[str] | None = None
) -> list[MetroScore]:
    scores = demand_scores(metros)
    reach_scores(scores, listeners, played)
    for s in scores:
        s.gap = round(s.demand - s.reach, 1)
        s.label = label(s)
        s.reasons = _reasons(s)
    return sorted(scores, key=lambda s: s.demand, reverse=True)


def _reasons(s: MetroScore) -> list[str]:
    reasons = [f"demand {s.demand:.0f}/100 from {s.cells} heatmap cells"]
    if s.listeners:
        reasons.append(f"{s.listeners:,} listeners → reach {s.reach:.0f}")
    if s.played_recently:
        reasons.append("played recently")
    if s.label == "unserved":
        reasons.append(f"gap {s.gap:+.0f}: fans you aren't reaching yet")
    return reasons


def select_cities(
    scores: list[MetroScore], n_shows: int, exclude: set[str] | None = None, include: set[str] | None = None
) -> list[MetroScore]:
    """Pick n_shows metros: forced includes, then up to a third proven anchors (by demand), then the biggest gaps."""
    exclude, include = exclude or set(), include or set()
    pool = [s for s in scores if s.metro not in exclude]
    chosen = [s for s in pool if s.metro in include][:n_shows]

    def take(candidates: list[MetroScore], limit: int) -> None:
        for s in candidates:
            if len(chosen) >= limit:
                return
            if s not in chosen:
                chosen.append(s)

    anchors = sorted((s for s in pool if s.label == "proven"), key=lambda s: s.demand, reverse=True)
    take(anchors, len(chosen) + max(1, round(n_shows * ANCHOR_SHARE)) if anchors else len(chosen))
    growth = sorted((s for s in pool if s.label in ("unserved", "potential")), key=lambda s: (s.gap, s.demand), reverse=True)
    take(growth, n_shows)
    take(sorted(pool, key=lambda s: s.demand, reverse=True), n_shows)  # top up with anything left
    return chosen[:n_shows]
