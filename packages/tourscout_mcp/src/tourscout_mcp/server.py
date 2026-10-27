"""TourScout MCP server.

    uv run tourscout-mcp                      # stdio (Claude Desktop, MCP Inspector)
    uv run tourscout-mcp --http --port 8001   # streamable HTTP at /mcp (the hosted agent)
"""

from __future__ import annotations

import argparse
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .allowlist import ParamNotAllowed
from .config import Settings
from .qloo import QlooError
from .tools import Deps, artists, demand, places

INSTRUCTIONS = """\
TourScout plans tours for independent musicians from Qloo taste data.
Typical flow: resolve_artist (confirm the right artist with the user if needs_confirmation) → demand_map for a region →
pick cities → find_venues / find_openers / find_sponsors / find_promo_spots per city.
Only name venues, openers and brands that these tools returned, and quote their numbers as given. Venue capacity is
unknown ("verify"); never invent one. If an artist is not on Qloo, pass 2–4 similar artists' ids to demand_map."""

mcp = MCPServer("TourScout", instructions=INSTRUCTIONS)
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
_deps: Deps | None = None


def deps() -> Deps:
    global _deps
    if _deps is None:
        _deps = Deps.from_settings(Settings())
    return _deps


async def _call(func: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await func(deps(), *args, **kwargs)
    except (QlooError, ParamNotAllowed, ValueError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(annotations=READ_ONLY)
async def resolve_artist(name: str) -> dict[str, Any]:
    """Find an artist on Qloo by name. Returns candidates (id, name, popularity 0–1, genres) and needs_confirmation=true
    when the top match isn't an exact name match, so you should confirm with the user before using the id."""
    return await _call(artists.resolve_artist, name)


@mcp.tool(annotations=READ_ONLY)
async def search_tags(query: str, take: int = 10) -> list[dict[str, Any]]:
    """Look up Qloo tag ids by word, e.g. 'record store' or 'shoegaze'."""
    return await _call(artists.search_tags, query, take)


@mcp.tool(annotations=READ_ONLY)
async def demand_map(artist_ids: list[str], region: str, top_n: int = 15) -> dict[str, Any]:
    """Where the artist's taste audience is. region is a country, state or city ('United States', 'Ohio', 'Chicago').
    Returns metros ranked by demand (0–100 within the region) with population, affinity and cell count, plus the top
    hotspot cells (a city region gives neighbourhood-level hotspots). Several artist_ids blend into a 'sounds like'
    audience for artists not on Qloo."""
    return await _call(demand.demand_map, artist_ids, region, top_n)


@mcp.tool(annotations=READ_ONLY)
async def find_venues(artist_ids: list[str], city: str, take: int = 10) -> dict[str, Any]:
    """Live music venues in a city ranked by how much the artist's fans like them (affinity). Includes address and rating.
    Capacity is always 'verify': Qloo has no capacity data."""
    return await _call(places.find_venues, artist_ids, city, take)


@mcp.tool(annotations=READ_ONLY)
async def find_openers(headliner_id: str, cities: list[str], take: int = 6, check_local: bool = True) -> dict[str, Any]:
    """Opening acts per city: smaller than the headliner (popularity cap), popular with the headliner's fans in that city,
    ranked by genre fit and local pull. badge comes from MusicBrainz: based_here / elsewhere / unknown. Acts that top
    the list in 3+ cities are dropped as national acts. check_local=false skips MusicBrainz (faster, ~1 s per artist)."""
    return await _call(artists.find_openers, headliner_id, cities, take, check_local)


@mcp.tool(annotations=READ_ONLY)
async def find_sponsors(artist_ids: list[str], cities: list[str] | None = None, take: int = 10) -> dict[str, Any]:
    """Brands the artist's fans love, nationally and per city. uplift = city affinity − national affinity;
    new_in_city=true means the brand only shows up with the city signal (a local sponsor angle)."""
    return await _call(places.find_sponsors, artist_ids, cities, take)


@mcp.tool(annotations=READ_ONLY)
async def find_promo_spots(artist_ids: list[str], city: str, kinds: list[str] | None = None, take: int = 5) -> dict[str, Any]:
    """Places to put up posters or do in-store sessions: record_store, book_store, coffee_shop, bar (default: all),
    ranked by the artist's fans' affinity."""
    return await _call(places.find_promo_spots, artist_ids, city, kinds, take)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.http:
        mcp.run("streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
