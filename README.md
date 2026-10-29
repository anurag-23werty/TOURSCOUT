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
proves the difference with a built-in **Compare** tab and the eval results below.

## Results: TourScout vs an LLM on its own
30 test artists (US, Europe, India, 4 not on Qloo, 4 edge cases), same request to both planners; the LLM-only planner gets no
tools. Full method and per-artist numbers: [`evals/reports/summary.md`](evals/reports/summary.md).

| | TourScout | LLM only |
|---|---|---|
| Openers actually based in the show's city (MusicBrainz) | **53%** | 3% |
| Openers that are smaller than the headliner and share a genre | **77%** | 19% |
| Venues that exist in that city | **100%** | 69% (India: 47%) |
| Back-to-back long drives without a day off | **0** | 9 |
| Sponsor lists preferred by a blind judge (Groq gpt-oss-120b) | **19** | 10 |
| Behaviour checks (prompt injection, empty region, impossible dates, name traps) | **13 / 13** | — |

**Backtest against real tours** (setlist.fm, 12 artists): the share of cities from each artist's most recent real tour
that land in the top 10 of a ranking. TourScout's demand ranking **42%**, population ranking 34%, random 1%. TourScout
wins for 9 of the 12 artists. In the top 25 the two are close (63% vs 60%). [`evals/reports/backtest.md`](evals/reports/backtest.md)

**Where TourScout loses or falls short**
- Speed: a full plan takes **51 s** (p50) vs ~6 s for the LLM alone, above our 45 s goal. Most of it is waiting on the LLM
  when Gemini's free quota runs out and the fallback chain takes over.
- 23% of its openers are based somewhere else (Qloo finds acts popular *in* a city, not *from* it; the MusicBrainz badge
  shows this, and it's why the badge exists).
- In the US, sponsor quality is a tie (6–6): the LLM's knowledge of who sponsors indie tours (gear, beer) is strong there.
- 12 artists is a small backtest, and a real tour isn't the best possible tour. Caveats are in each report.

## Tech
LangGraph agent · custom TourScout MCP server (Qloo tools) · FastAPI · React + Vite · Google Gemini (primary) ·
Groq `gpt-oss-120b` (fallback) · Postgres · Langfuse

## Privacy
No account needed. Uploaded screenshots are parsed and then deleted. Inputs are sent to Google Gemini (free tier) and Groq
to generate plans, and may be used by those providers under their terms.

## Run locally
```bash
cp .env.example .env                                   # add QLOO_API_KEY, GEMINI_API_KEY, GROQ_API_KEY
cd apps/api && uv sync && uv run python ../../data/download_geonames.py
uv run tourscout-api                                   # API on :8000
cd ../web && npm install && npm run dev                # app on :5173
```
More: [`apps/api/README.md`](apps/api/README.md), [`apps/web/README.md`](apps/web/README.md),
[`docs/mcp-claude-desktop.md`](docs/mcp-claude-desktop.md) (use the Qloo tools from Claude Desktop).

## Credits
Taste data: [Qloo](https://www.qloo.com). Planned: city data [GeoNames](https://www.geonames.org) (CC BY 4.0),
artist areas [MusicBrainz](https://musicbrainz.org), past tours [setlist.fm](https://www.setlist.fm) (evals).

## License
[MIT](LICENSE)
