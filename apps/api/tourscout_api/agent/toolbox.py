"""The agent's view of the TourScout tools.

These are the same functions the MCP server exposes (packages/tourscout_mcp), called in-process: one less network hop
and one less container on the free tier. Claude Desktop and other clients use the MCP server; the agent uses this.
"""

from __future__ import annotations

from typing import Any

from tourscout_mcp.config import Settings
from tourscout_mcp.geo import Metro
from tourscout_mcp.tools import Deps, artists, demand, places


class Toolbox:
    def __init__(self, deps: Deps) -> None:
        self.deps = deps

    @classmethod
    def from_env(cls) -> "Toolbox":
        return cls(Deps.from_settings(Settings()))

    async def resolve_artist(self, name: str) -> dict[str, Any]:
        return await artists.resolve_artist(self.deps, name)

    async def demand_map(self, artist_ids: list[str], region: str, top_n: int = 300) -> dict[str, Any]:
        return await demand.demand_map(self.deps, artist_ids, region, top_n)

    async def find_venues(self, artist_ids: list[str], city: str, take: int = 5) -> dict[str, Any]:
        return await places.find_venues(self.deps, artist_ids, city, take)

    async def find_openers(self, headliner_id: str, cities: list[str], take: int = 3) -> dict[str, Any]:
        return await artists.find_openers(self.deps, headliner_id, cities, take)

    async def find_sponsors(self, artist_ids: list[str], cities: list[str], take: int = 6) -> dict[str, Any]:
        return await places.find_sponsors(self.deps, artist_ids, cities, take)

    async def find_promo_spots(self, artist_ids: list[str], city: str, take: int = 3) -> dict[str, Any]:
        return await places.find_promo_spots(self.deps, artist_ids, city, ["record_store", "coffee_shop"], take)

    def metro(self, city: str) -> Metro | None:
        return self.deps.metro(city)

    async def aclose(self) -> None:
        await self.deps.qloo.aclose()
        if self.deps.musicbrainz:
            await self.deps.musicbrainz.aclose()
