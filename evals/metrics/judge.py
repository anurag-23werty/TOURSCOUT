"""Blind pairwise sponsor judge: Groq gpt-oss (a different model family from the Gemini planner) picks A or B.

Order is randomised per persona with a fixed seed, so position bias averages out and the run is reproducible.
"""

from __future__ import annotations

import random
from typing import Any, Literal

from pydantic import BaseModel

from tourscout_api.core.llm import LLM

PROMPT = """You are judging tour-sponsorship ideas for an independent musician.

Artist: {artist}
Fans' genres: {genres}
Tour cities: {cities}

Sponsor list A: {a}
Sponsor list B: {b}

Which list is the more realistic and relevant set of brands for THIS artist to approach for a tour sponsorship? Consider
fit with the fan base and the artist's size (a mid-sized indie act rarely lands a global megabrand). Answer "tie" only
if they are genuinely equivalent."""


class Verdict(BaseModel):
    winner: Literal["A", "B", "tie"]
    reason: str


async def judge_sponsors(judge: LLM, persona_id: str, artist: str, genres: list[str], cities: list[str],
                         tourscout: list[str], baseline: list[str]) -> dict[str, Any] | None:
    if not tourscout or not baseline:
        return None
    flip = random.Random(persona_id).random() < 0.5
    a, b = (baseline, tourscout) if flip else (tourscout, baseline)
    verdict = await judge.json(Verdict, PROMPT.format(
        artist=artist, genres=", ".join(genres[:8]) or "unknown", cities=", ".join(cities),
        a=", ".join(a), b=", ".join(b)), purpose="eval_judge")
    winner = {"A": "baseline" if flip else "tourscout", "B": "tourscout" if flip else "baseline", "tie": "tie"}[verdict.winner]
    return {"winner": winner, "reason": verdict.reason}
