# TourScout: Build Plan

> **Hackathon:** Qloo LLM Hackathon (Devpost). Build an *agent* whose output only works because of Qloo's taste graph.
> **Submit:** live hosted demo (end-to-end, public, no login), public repo with all source + instructions, a text
> description of what makes it Qloo-powered, an OSS license visible in the repo's About section. No video required.
> **Architecture:** `ARCHITECTURE.md`. **Commits:** Claude never commits. Each step below lists the exact `git add` + message for you to run.

---

## The problem
A mid-sized indie artist guesses where to tour using last year's streams and gut feel. They can't tell:
- where they have **unserved demand**,
- which **local opener** would actually pull a crowd,
- which **brands** their fans love enough to sponsor a show.

Labels pay analysts for this. Indie artists can't.

## The product
**TourScout, a tour-planning agent for independent musicians.** Enter your artist name (or "sounds like X × Y"), region,
dates and typical draw, and optionally upload a screenshot of your streaming dashboard. The agent:
1. maps where your sound's fans are (Qloo heatmap) and compares that with where you already have listeners, revealing **unserved cities**;
2. builds a **routed tour** (dates, drive distances, days off);
3. for every stop, picks **venues** that match your audience, **local openers** smaller than you who pull that crowd, **promo spots** (record stores, cafés), and **sponsor brands** your fans over-index on;
4. writes the **sponsor pitch** and **opener outreach DM**, quoting real affinity numbers, and exports the plan (CSV/ICS).

**Proof it needs Qloo:** a *Compare* tab (LLM-only picks NYC/LA and famous openers; TourScout finds the unserved
mid-sized cities and openers who are actually local) and an eval report with numbers.

### Already proven with real data (Phase 1, 27 Oct)
- Heatmap for Men I Trust (US): 2,532 cells with affinity + popularity; region filter works (Texas: 384 cells).
- Local openers for Men I Trust in Chicago: Divino Niño, Knox Fortune, Sen Morimoto, NNAMDÏ, KAINA, all Chicago acts.
- Chicago venues by audience fit: Lincoln Hall, Thalia Hall, Concord Music Hall, Los Globos, Reggies.
- Sponsor brands: Urban Outfitters, Dr. Martens, Polaroid nationally; Herschel and VSCO rise in Chicago.
- 27/30 test artists are in Qloo, including Indian indie (Prateek Kuhad, When Chai Met Toast, Peter Cat Recording Co., Seedhe Maut).

---

## Phase 0: Setup ✅ (done)
Repo public with MIT license, keys received (Qloo, Gemini), accounts, docs scaffold.
- [ ] **Still open:** Groq key → `.env`, then `uv run scripts/check_keys.py`.
- [ ] Accounts: Vercel, Railway/Fly, Neon, Langfuse, UptimeRobot; setlist.fm API key (evals).
- [ ] GitHub About: topics `qloo`, `ai-agent`, `langgraph`, `mcp`, `music`, `touring`.

## Phase 1: Understand Qloo for touring (Day 1–2) — in progress
- [x] Exploration tooling: `scripts/check_keys.py`, `scripts/qloo_explore.py`.
- [x] Verified: heatmap, regional heatmap, local openers (signal.location + weight + popularity.max), venue tags, brands, `/v2/tags?filter.query=`.
- [x] Persona artist coverage: 27/30 on Qloo.
- [ ] Run `docs/phase1-runbook.md` fully: `hypothesis` (different artists → different demand metros), `probe` for each type, `shape` for heatmap/place/artist/brand.
- [ ] Fill the **param allow-list** per `filter.type` in `docs/qloo-notes.md`.
- [ ] Check heatmap aggregation by hand for 2 artists (do the top metros look sane?).
- [ ] Decide the opener popularity margin (e.g. ≤ headliner − 0.05) and location weight from probes.

**Exit:** allow-list complete; hypothesis PASS with a number; scoring inputs understood.

| Step | `git add` | Commit message |
|---|---|---|
| 1.1 Musician pivot docs | `git add ARCHITECTURE.md PLAN.md README.md docs/ evals/ .env.example .gitignore` | `docs: pivot TourScout to tour planning for independent musicians` |
| 1.2 Explorer for touring | `git add scripts/` | `feat(phase1): heatmap, opener, venue and sponsor probes in qloo_explore` |
| 1.3 Findings | `git add docs/qloo-notes.md docs/models.md` | `docs(phase1): record verified Qloo params and model check results` |

---

## Phase 2: TourScout MCP server (Day 3–5)
- [ ] `packages/tourscout_mcp`: Python package (uv), `httpx` async Qloo client with retries, timeouts, response trimming, allow-list validation.
- [ ] Postgres cache (local SQLite fallback for dev); never in git.
- [ ] GeoNames loader (`data/download_geonames.py` → `data/raw/`), geohash → nearest metro.
- [ ] MusicBrainz helper: artist → home area (1 req/s, cached) for the "local" badge.
- [ ] Tools: `resolve_artist`, `search_tags`, `demand_map`, `find_venues`, `find_openers`, `find_sponsors`, `find_promo_spots`, with clear descriptions.
- [ ] Tests: unit tests with *synthetic* fixtures (no Qloo data), one live smoke test behind a flag.
- [ ] Try it in MCP Inspector and Claude Desktop; write `docs/mcp-claude-desktop.md`.

**Exit:** Claude Desktop answers "Where should Hovvdy tour in the Midwest, and who should open in Chicago?" with grounded results.

| Step | `git add` | Commit message |
|---|---|---|
| 2.1 Package skeleton | `git add packages/tourscout_mcp/pyproject.toml packages/tourscout_mcp/src packages/tourscout_mcp/README.md` | `feat(mcp): scaffold tourscout_mcp package` |
| 2.2 Qloo client | `git add packages/tourscout_mcp/src/tourscout_mcp/qloo.py packages/tourscout_mcp/src/tourscout_mcp/allowlist.py packages/tourscout_mcp/tests/test_qloo.py` | `feat(mcp): async Qloo client with param allow-list, retries and cache` |
| 2.3 Geo + MusicBrainz | `git add data/download_geonames.py packages/tourscout_mcp/src/tourscout_mcp/geo.py packages/tourscout_mcp/src/tourscout_mcp/musicbrainz.py packages/tourscout_mcp/tests/test_geo.py` | `feat(mcp): geohash-to-metro mapping and MusicBrainz home-area lookup` |
| 2.4 Tools | `git add packages/tourscout_mcp/src/tourscout_mcp/server.py packages/tourscout_mcp/src/tourscout_mcp/tools/ packages/tourscout_mcp/tests/test_tools.py` | `feat(mcp): demand_map, venue, opener, sponsor and promo tools` |
| 2.5 Claude Desktop doc | `git add docs/mcp-claude-desktop.md` | `docs(mcp): connect TourScout MCP to Claude Desktop` |

---

## Phase 3: Scoring engine + agent (Day 6–10)
- [ ] `apps/api/scoring/`: metro aggregation, demand, reach, gap labels, route (nearest-neighbour + 2-opt, drive limits). 100% unit-tested.
- [ ] Reach ingest: Gemini reads a streaming-dashboard screenshot → `{city, listeners}` table, confirmed by the user; CSV upload option.
- [ ] LangGraph graph with nodes 1–10, state, Postgres checkpointer, two human-in-the-loop interrupts.
- [ ] "Sounds like" fallback for artists not in Qloo.
- [ ] Grounding validator (IDs + quoted numbers + constraints) with a retry loop.
- [ ] Outputs: tour brief, sponsor pitch, opener DM, CSV/ICS export.
- [ ] Refine router ("skip Texas", "add a day off", "rooms under 500").
- [ ] Model layer: Gemini main/lite with automatic Groq fallback; log `modelVersion`.
- [ ] LLM-only baseline planner.
- [ ] Langfuse tracing.

**Exit:** CLI run produces a full 10-date plan for Hovvdy (on Qloo) and for Easy Wanderlings ("sounds like" path), fully grounded and traced.

| Step | `git add` | Commit message |
|---|---|---|
| 3.1 Scoring | `git add apps/api/scoring/ apps/api/tests/test_scoring.py` | `feat(scoring): demand, reach gap and tour routing with tests` |
| 3.2 Model layer | `git add apps/api/core/llm.py apps/api/tests/test_llm_fallback.py` | `feat(api): Gemini primary with Groq fallback and version logging` |
| 3.3 Agent graph | `git add apps/api/agent/ apps/api/tests/test_agent.py` | `feat(agent): LangGraph tour agent with checkpoints and grounding validator` |
| 3.4 Reach ingest | `git add apps/api/agent/nodes/reach.py apps/api/tests/test_reach.py` | `feat(agent): read streaming-dashboard screenshots into reach data` |
| 3.5 Outputs | `git add apps/api/agent/nodes/outputs.py apps/api/agent/prompts/` | `feat(agent): sponsor pitch, opener DM and CSV/ICS export` |
| 3.6 Baseline | `git add apps/api/baseline/` | `feat(baseline): LLM-only tour planner for compare mode and evals` |

---

## Phase 4: Backend API (Day 11)
- [ ] FastAPI routes (§8 of the architecture) with SSE streaming of agent events.
- [ ] Guest sessions, upload handling (size/type limits, delete after parse).
- [ ] Rate limits: per IP, per session, global daily cap (sized from `docs/models.md`).

**Exit:** the whole flow runs via HTTP with streamed events.

| Step | `git add` | Commit message |
|---|---|---|
| 4.1 Routes + SSE | `git add apps/api/routes/ apps/api/main.py apps/api/tests/test_routes.py` | `feat(api): chat, resume, upload, compare and export endpoints with SSE` |
| 4.2 Limits | `git add apps/api/core/ratelimit.py apps/api/core/sessions.py` | `feat(api): guest sessions and rate limits` |

---

## Phase 5: Frontend (Day 12–15)
- [ ] One-click demo artists (Men I Trust, Hovvdy, Prateek Kuhad, Easy Wanderlings…).
- [ ] Intake form + chat; screenshot upload with an editable extracted table.
- [ ] Live agent timeline.
- [ ] Demand map (heatmap layer + unserved/proven pins) and route line.
- [ ] City cards: venues, openers (with "local" badge), sponsors (affinity bars), promo spots.
- [ ] Sponsor pitch and opener DM drawers with copy buttons; CSV/ICS download.
- [ ] Compare tab: LLM-only vs TourScout with flags (not local, not found, bigger than headliner).
- [ ] Mobile responsive; loading, empty and error states.

**Exit:** a stranger plans a tour end-to-end in under 3 minutes with no instructions.

| Step | `git add` | Commit message |
|---|---|---|
| 5.1 Scaffold | `git add apps/web/package.json apps/web/package-lock.json apps/web/vite.config.ts apps/web/index.html apps/web/src/main.tsx apps/web/tailwind.config.js` | `feat(web): scaffold React + Vite + Tailwind app` |
| 5.2 Intake + timeline | `git add apps/web/src/` | `feat(web): artist intake, demo personas and live agent timeline` |
| 5.3 Map + route | `git add apps/web/src/components/DemandMap.tsx apps/web/src/components/RouteLine.tsx` | `feat(web): demand map with unserved and proven cities and tour route` |
| 5.4 City cards | `git add apps/web/src/components/city/` | `feat(web): city cards for venues, local openers, sponsors and promo spots` |
| 5.5 Compare | `git add apps/web/src/pages/Compare.tsx` | `feat(web): compare LLM-only plan with TourScout plan` |

---

## Phase 6: Evals (Day 16–18)
- [ ] Run all personas through TourScout and the baseline.
- [ ] Metrics: opener locality (MusicBrainz), opener fit, venue grounding, **backtest** (setlist.fm past tours vs our top-N metros vs a population-only baseline), sponsor relevance (blind judge + 5–10 humans), latency/cost.
- [ ] Tune scoring weights on the backtest. Keep a held-out set so we don't overfit.
- [ ] README results table, including where TourScout loses.
- [ ] CI eval smoke test.

**Exit:** numbers like "X% of openers local vs Y% for LLM-only; Z% of real tour cities in our top 10".

| Step | `git add` | Commit message |
|---|---|---|
| 6.1 Harness | `git add evals/run.py evals/metrics/ evals/tests/` | `feat(evals): eval harness for openers, venues and sponsors` |
| 6.2 Backtest | `git add evals/backtest/` | `feat(evals): setlist.fm backtest of demand ranking` |
| 6.3 Results | `git add evals/reports/summary.md README.md` | `docs(evals): publish TourScout vs LLM-only results` |

---

## Phase 7: Harden + deploy (Day 19–20)
- [ ] Dockerfiles; deploy api + mcp to Railway/Fly, web to Vercel, Neon Postgres, Langfuse.
- [ ] Pre-warm the private cache for demo artists; UptimeRobot on `/health`; no cold starts.
- [ ] Failure drills: Gemini 503/429 (→ Groq), Qloo slow heatmap/429, artist not found, empty region, huge or odd uploads, prompt injection.
- [ ] Test in incognito, on a phone, on another network.

**Exit:** the live URL survives 10 rapid sessions and every failure drill degrades gracefully.

| Step | `git add` | Commit message |
|---|---|---|
| 7.1 Docker | `git add infra/ apps/api/Dockerfile packages/tourscout_mcp/Dockerfile` | `chore(infra): Dockerfiles for api and mcp` |
| 7.2 CI/CD | `git add .github/workflows/` | `ci: lint, tests and deploy workflows` |
| 7.3 Hardening | `git add apps/ packages/` | `fix: graceful fallbacks from failure drills` |

---

## Phase 8: Submit (Day 21)
- [ ] README: pitch, **live demo link**, **MCP endpoint**, GIF/screenshots, diagram, "How Qloo powers this", eval table, run steps, credits (GeoNames, MusicBrainz, setlist.fm).
- [ ] Devpost text: problem → agent → why it fails without Qloo (compare + evals) → tech → challenges → next.
- [ ] Final checks: repo public, LICENSE in About, no keys/Qloo data in history (`git log -p | grep -i "hack_"` returns nothing), demo works without login.
- [ ] Submit 24 h early.

| Step | `git add` | Commit message |
|---|---|---|
| 8.1 Submission docs | `git add README.md docs/diagrams/ docs/devpost.md` | `docs: submission README, diagrams and Devpost write-up` |
| 8.2 Release | `git tag v1.0.0 && git push --tags` | (tag: `v1.0.0 – Qloo hackathon submission`) |

## Phase 9: After (resume)
- Blog/LinkedIn: "Building a taste-grounded tour-planning agent with LangGraph + MCP".
- Resume bullets (fill in Phase 6 numbers):
  - *Built TourScout, an agent that plans tours for independent musicians from Qloo's 250M-entity taste graph via a custom MCP server; full stack: FastAPI, LangGraph, React, Postgres.*
  - *Designed deterministic demand-gap scoring and routing; backtest showed X% of real tour cities in the top-10 vs Y% for a population baseline.*
  - *Local-opener precision X% vs Y% for an LLM-only baseline (MusicBrainz-verified).*

---

## Scope guard
| MVP | Stretch |
|---|---|
| Artist resolve + sounds-like fallback, demand map, gap scoring, route, venues, openers, sponsors, sponsor pitch, opener DM, compare, evals, MCP server, hosted | Promo spots, streaming screenshot ingest (CSV/manual first), ICS export, multi-region tours, merch ideas, poster-style suggestions |

## Risks
| Risk | Mitigation |
|---|---|
| Heatmap cells → wrong cities | GeoNames nearest-metro with a 50 km cap; manual sanity check of 2 artists in Phase 1 |
| Affinity favours tiny areas (seen: Ladakh for Prateek Kuhad) | Weight by popularity and population; minimum metro size |
| No venue capacity in Qloo | Say "capacity: verify"; artist enters typical draw; never invent a capacity |
| Opener too big (e.g. Japanese Breakfast for Men I Trust) | `filter.popularity.max` below the headliner; exclude the headliner |
| Gemini 503 (seen in the key check) / free quota | Lite alias for cheap steps, cache, auto-fallback to Groq |
| Qloo quota burn from the public demo | Private cache, caps; ask Discord #api-help for more |
| Artist not in Qloo | "Sounds like" path; 3 such personas in evals |
| Scope creep | Stretch list is cut first |
