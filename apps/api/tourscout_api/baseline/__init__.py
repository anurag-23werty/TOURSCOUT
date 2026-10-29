"""LLM-only tour planner: the same request with no tools, for the Compare tab and the evals."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from ..agent.prompts import prompt
from ..core.llm import LLM, dumps


class BaselineStop(BaseModel):
    city: str
    date: str
    venue: str
    openers: list[str] = Field(default_factory=list)
    sponsors: list[str] = Field(default_factory=list)
    why: str = ""


class BaselinePlan(BaseModel):
    stops: list[BaselineStop]


def describe(intake: dict[str, Any]) -> str:
    """The same facts the agent gets from the user, as text (no Qloo data)."""
    keys = ("artist", "sounds_like", "home_base", "regions", "start_date", "end_date", "n_shows",
            "draw_min", "draw_max", "max_drive_km", "past_cities", "exclude_cities")
    return dumps({k: intake[k] for k in keys if intake.get(k) not in (None, [], "")})


async def plan_baseline(llm: LLM, request: str = "", intake: dict[str, Any] | None = None) -> dict[str, Any]:
    text = request or describe(intake or {})
    result = await llm.json(BaselinePlan, prompt("baseline", today=date.today().isoformat(), request=text),
                            purpose="baseline")
    return {"stops": [s.model_dump() for s in result.stops], "llm_calls": llm.usage()[-1:]}
