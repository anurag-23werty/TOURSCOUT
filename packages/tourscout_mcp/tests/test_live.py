"""One end-to-end call against the real APIs. Skipped unless TOURSCOUT_LIVE=1 (needs QLOO_API_KEY in .env)."""

from __future__ import annotations

import os

import pytest

from tourscout_mcp.config import Settings
from tourscout_mcp.tools import Deps, artists, demand, places

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.live,
    pytest.mark.skipif(os.getenv("TOURSCOUT_LIVE") != "1", reason="set TOURSCOUT_LIVE=1 to call the real APIs"),
]


async def test_hovvdy_midwest_smoke() -> None:
    deps = Deps.from_settings(Settings())
    found = await artists.resolve_artist(deps, "Hovvdy")
    assert not found["needs_confirmation"]
    hovvdy = found["candidates"][0]["id"]

    ohio = await demand.demand_map(deps, [hovvdy], "Ohio")
    assert "Columbus, OH" in [m["metro"] for m in ohio["metros"][:5]]

    venues = await places.find_venues(deps, [hovvdy], "Columbus")
    assert venues["venues"] and all(v["id"] for v in venues["venues"])

    openers = await artists.find_openers(deps, hovvdy, ["Columbus"], take=3)
    assert openers["cities"][0]["openers"]
    await deps.qloo.aclose()
