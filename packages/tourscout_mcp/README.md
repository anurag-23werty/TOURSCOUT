# tourscout-mcp

An MCP server that turns [Qloo](https://qloo.com) taste data into tour-planning tools for independent musicians.
Any MCP client (Claude Desktop, MCP Inspector, the TourScout agent) can call it.

| Tool | What it answers |
|---|---|
| `resolve_artist(name)` | Which Qloo artist is this? (`needs_confirmation` when the match isn't exact) |
| `search_tags(query)` | Qloo tag ids for a word |
| `demand_map(artist_ids, region)` | Where is the audience? Metros ranked by demand 0–100 + hotspot cells. Regions like "Midwest" expand to states; several ids = "sounds like" audience |
| `find_venues(artist_ids, city)` | Which rooms do these fans like? (capacity always "verify") |
| `find_openers(headliner_id, cities)` | Which smaller local acts would pull a crowd? Genre fit + local pull + MusicBrainz "based here" badge; national acts dropped |
| `find_sponsors(artist_ids, cities)` | Which brands do the fans love, nationally and per city (uplift, new in city)? |
| `find_promo_spots(artist_ids, city)` | Record stores, book stores, cafés and bars for posters and in-stores |

## Run
```bash
cd packages/tourscout_mcp
uv sync
uv run python ../../data/download_geonames.py   # once: GeoNames cities → data/raw/ (git-ignored)
uv run tourscout-mcp                             # stdio
uv run tourscout-mcp --http --port 8001          # streamable HTTP at http://127.0.0.1:8001/mcp
```
Needs `QLOO_API_KEY` in the repo-root `.env` (see `.env.example`). Connect it to Claude Desktop: [`docs/mcp-claude-desktop.md`](../../docs/mcp-claude-desktop.md).

## Test
```bash
uv run pytest                       # unit tests on synthetic fixtures, no network
TOURSCOUT_LIVE=1 uv run pytest -m live   # one smoke test against the real Qloo + MusicBrainz APIs
```

## Design notes
- **Param allow-list** (`allowlist.py`): Qloo silently ignores unsupported params, so every request is checked against the
  params we verified in Phase 1. Known-bad params fail with the reason (e.g. `filter.location.query` on artists).
- **Cache** (`cache.py`): SQLite in `~/.cache/tourscout/` locally, Postgres in production (`TOURSCOUT_CACHE_URL`). It lives
  outside the repo on purpose: Qloo data must never be committed.
- **Metros** (`geo.py`): GeoNames cities are grouped into metros (Evanston → Chicago) but small far-away college towns stay
  separate (Athens OH), because those are the unserved markets the product is about.
- **Retries:** Qloo 429/5xx with backoff; MusicBrainz at 1 request/second with a retry on 503.

Data: Qloo (hackathon API terms), GeoNames (CC BY 4.0), MusicBrainz (CC0).
