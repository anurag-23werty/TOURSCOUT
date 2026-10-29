"""Eval personas (evals/personas/personas.jsonl) as agent inputs: used by the CLI, the API demo buttons and the evals."""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from .core.config import REPO_ROOT

PERSONAS = REPO_ROOT / "evals" / "personas" / "personas.jsonl"
# One-click demo artists on the home page: on Qloo (US), not on Qloo (India), a bigger act.
FEATURED = ["us-02", "nq-02", "us-01"]


@cache
def all_personas() -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in PERSONAS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {p["id"]: p for p in rows}


def to_inputs(persona: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persona row → (intake, reach_input)."""
    window, draw = persona.get("window") or [None, None], persona.get("draw") or [None, None]
    intake = {
        # nq-04 is a brand-new act with no name yet: it must go down the "sounds like" path.
        "artist": persona["artist"] or "Untitled new artist", "sounds_like": persona.get("sounds_like", []), "home_base": persona["home_base"],
        "regions": persona["regions"], "start_date": window[0], "end_date": window[1], "n_shows": persona["n_shows"],
        "draw_min": draw[0], "draw_max": draw[1], "max_drive_km": persona.get("max_drive_km", 600),
        "past_cities": persona.get("past_cities", []),
    }
    rows = [{"city": c, "listeners": n} for c, n in (persona.get("reach_synthetic") or {}).items()]
    return intake, {"rows": rows}


def load(persona_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    persona = all_personas().get(persona_id)
    if persona is None:
        raise KeyError(persona_id)
    return to_inputs(persona)


def summary(persona: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": persona["id"], "artist": persona["artist"], "home_base": persona["home_base"],
        "regions": persona["regions"], "n_shows": persona["n_shows"], "window": persona.get("window"),
        "sounds_like": persona.get("sounds_like", []), "featured": persona["id"] in FEATURED,
    }
