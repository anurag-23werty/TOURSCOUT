# TourScout 🎸🗺️

**A tour-planning agent for independent musicians.**

A mid-sized indie artist usually guesses where to tour from last year's streams and gut feel. They can't see where they
have **unserved demand**, which **local opener** would actually pull a crowd, or which **brands** their fans love enough to
sponsor a show. Labels pay analysts for this. Indie artists can't.

TourScout is that analyst. It's an AI agent grounded in **Qloo's taste graph** (250M+ entities).

> 🚧 Under construction for the **Qloo LLM Hackathon**. Live demo and MCP endpoint links will appear here.

| | |
|---|---|
| 🌐 Live demo | _coming soon_ |
| 🔌 TourScout MCP server | _coming soon_ |
| 📐 Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 🗺️ Build plan | [PLAN.md](PLAN.md) |

## What it does
1. **Demand map:** where your sound's fans actually are (Qloo heatmap), compared with where you already have listeners, revealing **unserved cities**.
2. **Routed tour:** dates, drive distances and days off.
3. **Per stop:** venues that fit your audience, **local openers** smaller than you who pull that crowd, promo spots, and **sponsor brands** your fans over-index on.
4. **Ready-to-send:** a sponsor pitch and an opener outreach DM quoting real affinity numbers, plus a CSV/ICS export.

## Why it needs Qloo
Without Qloo, an LLM suggests the obvious big cities and famous openers, and sometimes invents venues.
TourScout only recommends Qloo entities returned in the run (a validator enforces it), computes every score in code, and
proves the difference with a built-in **Compare** tab and an eval report (local-opener precision, backtest against real past tours).

## Tech
LangGraph agent · custom TourScout MCP server (Qloo tools) · FastAPI · React + Vite · Google Gemini (primary) ·
Groq `gpt-oss-120b` (fallback) · Postgres · Langfuse

## Privacy
No account needed. Uploaded screenshots are parsed and then deleted. Inputs are sent to Google Gemini (free tier) and Groq
to generate plans, and may be used by those providers under their terms.

## Run locally
_Full setup arrives in Phases 2–4._ For now: `cp .env.example .env`, add your keys, then `uv run scripts/check_keys.py`.

## Credits
Taste data: [Qloo](https://www.qloo.com). Planned: city data [GeoNames](https://www.geonames.org) (CC BY 4.0),
artist areas [MusicBrainz](https://musicbrainz.org), past tours [setlist.fm](https://www.setlist.fm) (evals).

## License
[MIT](LICENSE)
