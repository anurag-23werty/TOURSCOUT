"""Structured shapes the LLM must produce (validated with Pydantic) and the agent's state."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- LLM outputs


class Intake(BaseModel):
    artist: str = Field(description="the artist or band name as written by the user")
    sounds_like: list[str] = Field(default_factory=list, description="similar artists the user mentioned")
    home_base: str = Field(description="city the tour starts from")
    regions: list[str] = Field(description="countries, states or regions like 'Midwest'")
    start_date: str | None = Field(None, description="YYYY-MM-DD")
    end_date: str | None = Field(None, description="YYYY-MM-DD")
    n_shows: int = Field(8, ge=1, le=30)
    draw_min: int | None = Field(None, description="typical crowd size, low end")
    draw_max: int | None = Field(None, description="typical crowd size, high end")
    max_drive_km: int = Field(600, ge=0, description="0 = flying between cities, no drive limit")
    past_cities: list[str] = Field(default_factory=list, description="cities played in the last 12 months")
    exclude_cities: list[str] = Field(default_factory=list)
    include_cities: list[str] = Field(default_factory=list)


class SimilarArtists(BaseModel):
    artists: list[str] = Field(description="3-4 well-known artists with a similar sound and audience")


class ReachRow(BaseModel):
    city: str
    listeners: int


class ReachTable(BaseModel):
    rows: list[ReachRow]


class StopPlan(BaseModel):
    metro: str
    date: str | None = None  # informational: dates and order always come from the computed route
    venue_id: str
    opener_ids: list[str] = Field(default_factory=list, max_length=2)
    sponsor_ids: list[str] = Field(default_factory=list, max_length=2)
    promo_ids: list[str] = Field(default_factory=list, max_length=3)
    why: str = Field(description="one or two sentences using only the given numbers")


class Brief(BaseModel):
    headline: str
    summary: str
    stops: list[StopPlan]
    sponsor_strategy: str
    risks: list[str] = Field(default_factory=list)


class RefineOps(BaseModel):
    exclude_cities: list[str] = Field(default_factory=list)
    include_cities: list[str] = Field(default_factory=list)
    regions: list[str] | None = None
    n_shows: int | None = None
    max_drive_km: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    note: str = Field("", description="anything the request asked for that these fields can't express")


class Pitch(BaseModel):
    subject: str
    body: str


# ---------------------------------------------------------------- graph state


class TourState(TypedDict, total=False):
    request: str  # free-text ask (or empty when a structured intake is given)
    intake: dict[str, Any]
    auto_approve: bool  # true = no human checkpoints (CLI, evals)
    reach_input: dict[str, Any]  # {"rows": [...]} | {"csv": "..."} | {"image_b64": "...", "mime": "image/png"}

    artist: dict[str, Any]  # name, id, on_qloo, signal_ids, signal_names, headliner_id, popularity
    candidates: list[dict[str, Any]]
    reach: dict[str, Any]  # listeners {metro: n}, played [metro], source
    metros: list[dict[str, Any]]
    selected: list[str]
    route: dict[str, Any]
    intel: dict[str, Any]  # metro → venues / openers / sponsors / promo
    national_sponsors: list[dict[str, Any]]
    brief: dict[str, Any]
    violations: list[str]
    attempts: int
    plan: dict[str, Any]  # final, names resolved from ids
    refine_request: str
    refine_next: str
    no_venue_cities: list[str]  # swapped out because Qloo has no venue data there
    swaps: int
    refined: bool  # set by refine so the pick-cities checkpoint isn't asked again

    events: Annotated[list[dict[str, Any]], operator.add]  # streamed to the UI
    llm_calls: Annotated[list[dict[str, Any]], operator.add]
