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
- [x] `packages/tourscout_mcp`: Python package (uv), `httpx` async Qloo client with retries, timeouts, response trimming, allow-list validation.
- [x] Postgres cache (local SQLite fallback for dev); never in git.
- [x] GeoNames loader (`data/download_geonames.py` → `data/raw/`), geohash → nearest metro.
- [x] MusicBrainz helper: artist → home area (1 req/s, cached) for the "local" badge.
- [x] Tools: `resolve_artist`, `search_tags`, `demand_map`, `find_venues`, `find_openers`, `find_sponsors`, `find_promo_spots`, with clear descriptions.
- [x] Tests: unit tests with *synthetic* fixtures (no Qloo data), one live smoke test behind a flag.
- [x] Write `docs/mcp-claude-desktop.md`; stdio + HTTP verified with a real MCP client; Claude Desktop exit test passed (29 Oct).

**Exit:** Claude Desktop answers "Where should Hovvdy tour in the Midwest, and who should open in Chicago?" with grounded results.

| Step | `git add` | Commit message |
|---|---|---|
| 2.1 Package skeleton | `git add packages/tourscout_mcp/pyproject.toml packages/tourscout_mcp/uv.lock packages/tourscout_mcp/README.md packages/tourscout_mcp/src/tourscout_mcp/__init__.py packages/tourscout_mcp/src/tourscout_mcp/config.py` | `feat(mcp): scaffold tourscout_mcp package (mcp 2.x, uv)` |
| 2.2 Qloo client | `git add packages/tourscout_mcp/src/tourscout_mcp/qloo.py packages/tourscout_mcp/src/tourscout_mcp/allowlist.py packages/tourscout_mcp/src/tourscout_mcp/cache.py packages/tourscout_mcp/tests/conftest.py packages/tourscout_mcp/tests/test_qloo.py` | `feat(mcp): async Qloo client with param allow-list, retries and private cache` |
| 2.3 Geo + MusicBrainz | `git add data/download_geonames.py packages/tourscout_mcp/src/tourscout_mcp/geo.py packages/tourscout_mcp/src/tourscout_mcp/musicbrainz.py packages/tourscout_mcp/tests/test_geo.py` | `feat(mcp): geohash-to-metro mapping and MusicBrainz home-area lookup` |
| 2.4 Tools + server | `git add packages/tourscout_mcp/src/tourscout_mcp/server.py packages/tourscout_mcp/src/tourscout_mcp/tools/ packages/tourscout_mcp/tests/test_tools.py packages/tourscout_mcp/tests/test_live.py` | `feat(mcp): demand_map, venue, opener, sponsor and promo tools over MCP` |
| 2.5 Docs | `git add docs/mcp-claude-desktop.md docs/qloo-notes.md ARCHITECTURE.md PLAN.md` | `docs(mcp): Claude Desktop setup and Phase 2 findings` |

---

## Phase 3: Scoring engine + agent (Day 6–10)
- [x] `apps/api/tourscout_api/scoring/`: demand (shrinkage × log population), reach (sqrt listeners), gap labels, city selection, routing (nearest-neighbour + 2-opt, travel/rest days, drive and window limits). Unit-tested.
- [x] Reach ingest: rows, CSV, or a streaming-dashboard screenshot read by Gemini (mocked test; needs a real screenshot check in Phase 5).
- [x] LangGraph graph: intake → resolve → ⏸confirm → reach → demand → score → ⏸pick → route → fan-out (venue swap loop) → compose ⇄ validate → outputs; refine on the same thread.
- [x] "Sounds like" fallback (user names or LLM suggestions, each grounded on Qloo).
- [x] Grounding validator (ids, numbers, route coverage) with ≤ 2 retries and per-stop salvage.
- [x] Outputs: plan with names from ids, CSV/ICS export, sponsor pitch, opener DM.
- [x] Refine router ("skip Detroit", "only 6 shows", "max 400 km a day").
- [x] Model layer: Gemini main → lite → Groq, circuit breakers, Groq retry-after / JSON-mode retry, every call logged.
- [x] LLM-only baseline planner.
- [ ] Postgres checkpointer → Phase 4 (in-memory checkpointer for CLI/tests now).
- [ ] Langfuse tracing → Phase 4 (every LLM call and node event is already in state: `llm_calls`, `events`).

**Exit ✅ (29 Oct):** `uv run tourscout --persona us-02 --auto` → grounded 10-date Hovvdy Midwest plan (17 s with lite as main,
56 s with the overloaded Flash main). `--persona nq-02` (Easy Wanderlings, not on Qloo) → grounded 6-date India plan from a
Prateek Kuhad / Peter Cat Recording Co. / Fleet Foxes audience, with Pune + Mumbai anchors and Ranchi swapped out for
missing venue data.

| Step | `git add` | Commit message |
|---|---|---|
| 3.1 MCP fixes found by the agent | `git add packages/tourscout_mcp/src/tourscout_mcp/qloo.py packages/tourscout_mcp/src/tourscout_mcp/geo.py packages/tourscout_mcp/src/tourscout_mcp/tools/demand.py packages/tourscout_mcp/src/tourscout_mcp/tools/artists.py packages/tourscout_mcp/tests/test_geo.py packages/tourscout_mcp/tests/test_tools.py` | `fix(mcp): gravity cell-to-metro mapping, Qloo concurrency cap and whole-list national-act check` |
| 3.2 API package + scoring | `git add apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md apps/api/tourscout_api/__init__.py apps/api/tourscout_api/scoring/ apps/api/tests/conftest.py apps/api/tests/test_scoring.py` | `feat(scoring): demand, reach gap, city selection and tour routing with tests` |
| 3.3 Model layer | `git add apps/api/tourscout_api/core/ apps/api/tests/test_llm_fallback.py` | `feat(api): Gemini → lite → Groq model chain with circuit breakers and call logging` |
| 3.4 Agent building blocks | `git add apps/api/tourscout_api/agent/__init__.py apps/api/tourscout_api/agent/schemas.py apps/api/tourscout_api/agent/toolbox.py apps/api/tourscout_api/agent/reach.py apps/api/tourscout_api/agent/validate.py apps/api/tourscout_api/agent/prompts/ apps/api/tests/test_reach.py apps/api/tests/test_validate.py` | `feat(agent): schemas, prompts, reach ingest and grounding validator` |
| 3.5 Outputs | `git add apps/api/tourscout_api/agent/outputs.py apps/api/tests/test_outputs.py` | `feat(agent): plan builder, CSV/ICS export, sponsor pitch and opener DM` |
| 3.6 Agent graph | `git add apps/api/tourscout_api/agent/graph.py apps/api/tourscout_api/agent/runner.py apps/api/tests/test_agent.py` | `feat(agent): LangGraph tour agent with checkpoints, venue swaps, retries and refine` |
| 3.7 Baseline | `git add apps/api/tourscout_api/baseline/ apps/api/tests/test_baseline.py` | `feat(baseline): LLM-only tour planner for compare mode and evals` |
| 3.8 CLI | `git add apps/api/tourscout_api/cli.py` | `feat(cli): run personas end to end with checkpoints, refine and compare` |
| 3.9 Docs | `git add ARCHITECTURE.md PLAN.md docs/qloo-notes.md docs/models.md` | `docs(phase3): scoring, model routing and agent as built, with measured results` |

---

## Phase 4: Backend API (Day 11)
- [x] FastAPI app: sessions, personas, upload, plans (SSE), resume, refine, state, compare, outreach, CSV/ICS export, health, `/mcp` mounted.
- [x] Durable checkpoints: SQLite locally, Postgres via `DATABASE_URL` (tested: a new agent resumes a saved run).
- [x] Guest sessions with thread ownership; uploads sniffed by bytes, ≤ 2 MB, single use, memory only.
- [x] Rate limits: per IP (plans, LLM actions, uploads, MCP), global daily plan budget, 3 concurrent plans.
- [x] Fixes found on the way: first drive from home no longer drops cities; refine doesn't re-ask "pick cities";
      sponsor pitch + opener DM are written in parallel.
- [ ] Langfuse → Phase 7 (needs keys; `llm_calls` + `events` are already returned by `GET /api/plans/{id}`).
- [ ] Postgres checkpointer against a real Neon database → Phase 7 (code path ready, only SQLite exercised so far).

**Exit ✅ (29 Oct):** `uv run tourscout-api`, then the Hovvdy persona over HTTP streamed every step as SSE and returned the
plan; CSV export and `/mcp` `initialize` worked against the same server.

| Step | `git add` | Commit message |
|---|---|---|
| 4.1 Durable runs, streaming + agent fixes | `git add apps/api/pyproject.toml apps/api/uv.lock apps/api/tourscout_api/core/checkpoint.py apps/api/tourscout_api/agent/runner.py apps/api/tourscout_api/agent/graph.py apps/api/tourscout_api/agent/schemas.py apps/api/tourscout_api/scoring/route.py apps/api/tests/test_agent.py apps/api/tests/test_scoring.py` | `feat(agent): durable checkpoints, event streaming, and routing/refine fixes` |
| 4.2 Sessions, limits, uploads | `git add apps/api/tourscout_api/api/__init__.py apps/api/tourscout_api/api/settings.py apps/api/tourscout_api/api/sessions.py apps/api/tourscout_api/api/ratelimit.py apps/api/tourscout_api/api/uploads.py apps/api/tests/test_api_limits.py` | `feat(api): guest sessions, rate limits and safe upload handling` |
| 4.3 Routes + SSE | `git add apps/api/tourscout_api/personas.py apps/api/tourscout_api/cli.py apps/api/tourscout_api/api/app.py apps/api/tests/test_api.py` | `feat(api): plan, resume, refine, compare, outreach and export endpoints with SSE and /mcp` |
| 4.4 Docs | `git add docs/api.md .env.example ARCHITECTURE.md PLAN.md apps/api/README.md` | `docs(api): endpoint and SSE reference, settings and Phase 4 status` |

---

## Phase 5: Frontend (Day 12–15)
- [x] `apps/web`: React 19 + Vite + Tailwind 4 + react-leaflet, typed API client with a fetch-based SSE parser.
- [x] Home: request form, featured demo artists, CSV/screenshot upload, "let me confirm" toggle.
- [x] Live agent steps, "Is this you?" (incl. "none of these, use artists I sound like") and "Pick your cities" checkpoints.
- [x] Demand map (circles by label and demand) + numbered route; the plan as a tour poster; city card with venue,
      openers + hometown badge, brands, poster spots, on-demand opener DM.
- [x] Refine bar, CSV / ICS downloads, Compare (LLM-only) and Drafts tabs; responsive to 390 px.
- [x] Verified in headless Chrome against the live API: full flow with both checkpoints, mobile plan view, Compare; 0 console errors.
- [x] Fixes found on the way: CARTO tiles now need a key → Esri light-gray canvas; ratings rounded; plan stops carry
      coordinates; the pick-cities list always includes every suggested city.

**Exit ✅ (29 Oct):** a visitor can plan Hovvdy's tour end to end in the browser, answer both checkpoints, read the poster,
open city details, compare with the LLM-only plan and download the CSV/ICS.

| Step | `git add` | Commit message |
|---|---|---|
| 5.1 Backend support for the UI | `git add packages/tourscout_mcp/src/tourscout_mcp/qloo.py apps/api/tourscout_api/agent/outputs.py apps/api/tourscout_api/agent/graph.py apps/api/tests/test_outputs.py apps/api/tests/test_agent.py` | `feat(api): stop coordinates, rounded ratings and full suggested-city list for the web UI` |
| 5.2 Web scaffold + API client | `git add .gitignore apps/web/package.json apps/web/package-lock.json apps/web/vite.config.ts apps/web/tsconfig.json apps/web/index.html apps/web/.env.example apps/web/public/ apps/web/src/main.tsx apps/web/src/index.css apps/web/src/types.ts apps/web/src/api.ts apps/web/src/format.ts apps/web/src/useTour.ts apps/web/src/api.test.ts apps/web/src/format.test.ts` | `feat(web): Vite + React + Tailwind scaffold, typed API client and SSE run state` |
| 5.3 Screens | `git add apps/web/src/App.tsx apps/web/src/components/` | `feat(web): request form, live steps, checkpoints, demand map, tour poster, city card, compare and drafts` |
| 5.4 Docs | `git add apps/web/README.md PLAN.md` | `docs(web): run, layout and design notes for the web app` |

---

## Phase 6: Evals (Day 16–18)
- [x] All 30 personas through TourScout and the LLM-only baseline (`evals/run.py run`), raw outputs git-ignored.
- [x] Metrics: opener locality (MusicBrainz), opener fit (Qloo popularity + genre), venue grounding (Qloo id or place
      search), constraints, behaviour checks, blind sponsor judge (Groq), latency.
- [x] Backtest: setlist.fm real tours vs TourScout demand vs population vs random (12 artists).
- [x] README results table, including where TourScout loses.
- [x] Fixes the evals found: sponsor categories (beer, headphones, cameras, sneakers) after the judge preferred the
      LLM's gear/beer picks; region names ("US East Coast", "South/North India"); Groq "generate JSON" retry; cooling
      models as a last resort instead of failing a step.
- [ ] Scoring weights **not** tuned on the backtest: 12 artists is too few to tune without overfitting. Revisit with more.
- [ ] CI eval smoke test → Phase 7 (with the rest of CI).
- [ ] Human panel (5–10 people) for sponsor relevance → before submission if time allows.

**Exit ✅ (29 Oct):** 53% vs 3% local openers, 100% vs 69% venues that exist, 13/13 behaviour checks; backtest top-10
recall 42% vs 34% for population.

| Step | `git add` | Commit message |
|---|---|---|
| 6.1 Fixes found by the evals | `git add packages/tourscout_mcp/src/tourscout_mcp/allowlist.py packages/tourscout_mcp/src/tourscout_mcp/tools/places.py packages/tourscout_mcp/src/tourscout_mcp/tools/demand.py packages/tourscout_mcp/src/tourscout_mcp/server.py packages/tourscout_mcp/tests/test_tools.py apps/api/tourscout_api/agent/graph.py apps/api/tourscout_api/agent/prompts/compose.md apps/api/tourscout_api/core/llm.py apps/api/tourscout_api/personas.py apps/api/tests/test_agent.py apps/api/tests/test_llm_fallback.py` | `fix: sponsor categories, more region names and sturdier LLM fallback (found by evals)` |
| 6.2 Eval harness | `git add evals/run.py evals/metrics/ evals/tests/test_metrics.py` | `feat(evals): TourScout vs LLM-only harness for openers, venues, constraints, edge cases and sponsors` |
| 6.3 Backtest | `git add evals/backtest/ evals/tests/test_backtest.py` | `feat(evals): setlist.fm backtest of the demand ranking vs population` |
| 6.4 Results | `git add evals/reports/summary.md evals/reports/backtest.md evals/README.md README.md PLAN.md` | `docs(evals): publish TourScout vs LLM-only results, including where it loses` |

---

## Phase 7: Harden + deploy (Day 19–20)
- [x] One Docker image (API + agent + `/mcp`, GeoNames baked in, non-root): 924 MB → **437 MB** with a two-stage build.
- [x] Postgres for production: pooled Qloo cache + LangGraph checkpoints, tested against a real Postgres (and in CI).
- [x] Langfuse tracing (trace per run, span per step, generation per LLM call), off without keys.
- [x] CI: Python + Postgres tests, eval tests, web build, Docker build. Render (`render.yaml`) + Vercel (`vercel.json`) config.
- [x] Failure drills against the container (`scripts/live_check.py drills`): odd uploads, bad requests, someone else's
      plan, 10 simultaneous visitors (**10/10 got a plan** after adding a queue; it was 3/10), prompt injection (plan, no leak).
- [x] Fixes from the drills: a queue instead of "busy" rejections; readable "free-tier limit" message instead of provider
      errors; a patient intake step; per-IP plan limit 6 → 20 (campus networks share an IP); `/health` checkpointer label.
- [x] Finding: Groq free tier = 200k tokens/day (~25–30 plans); documented in `docs/models.md`.
- [x] Deployed: web https://tourscout-lovat.vercel.app, API https://tourscout-api.onrender.com (Neon Postgres,
      Langfuse US, UptimeRobot every 5 min). Repo public with MIT, website and topics in the About box; CI green.
- [x] Live: prewarm of us-02 / nq-02 / us-01; **11/11 failure drills passed** against the live API.
- [x] Fixes from going live: `WEB_ORIGINS` ignores trailing slashes (a pasted `…vercel.app/` blocked the site);
      **SSE heartbeat** every 15 s, because a cold-cache fan-out was silent for ~1 min and the connection got cut
      (`ReadError` in the live prewarm); CI no longer forces `CHECKPOINTER=memory` over the checkpointer tests.
- [ ] **You:** incognito, phone on mobile data, one plan with "Let me confirm" on.

**Exit:** every failure drill degrades gracefully on the live URL ✅. The 10-visitor burst passed locally (10/10) and is
not rerun live, to save the free LLM quota.

| Step | `git add` | Commit message |
|---|---|---|
| 7.1 Production storage + tracing | `git add packages/tourscout_mcp/src/tourscout_mcp/cache.py packages/tourscout_mcp/pyproject.toml packages/tourscout_mcp/uv.lock packages/tourscout_mcp/tests/test_qloo.py apps/api/pyproject.toml apps/api/uv.lock apps/api/tourscout_api/core/tracing.py apps/api/tourscout_api/core/checkpoint.py apps/api/tourscout_api/agent/runner.py apps/api/tests/test_agent.py` | `feat(api): pooled Postgres cache, Postgres checkpoints and Langfuse tracing` |
| 7.2 Hardening from drills | `git add apps/api/tourscout_api/api/app.py apps/api/tourscout_api/api/settings.py apps/api/tourscout_api/agent/graph.py apps/api/tests/test_api.py apps/web/src/format.ts` | `fix(api): queue plans when busy, readable LLM-limit errors, patient intake` |
| 7.3 Docker + deploy config | `git add infra/api.Dockerfile .dockerignore render.yaml apps/web/vercel.json` | `chore(infra): two-stage Docker image, Render blueprint and Vercel config` |
| 7.4 CI | `git add .github/workflows/ci.yml` | `ci: Python, Postgres, eval, web and Docker checks` |
| 7.5 Drills + docs | `git add scripts/live_check.py docs/deploy.md docs/models.md ARCHITECTURE.md .env.example PLAN.md` | `docs(deploy): free-tier deploy guide, failure drills and Groq daily-limit finding` |
| 7.6 Live fixes | (pushed: CI override, `LANGFUSE_HOST`, `WEB_ORIGINS` slashes, SSE heartbeat) | |
| 7.7 Status | `git add PLAN.md` | `docs(plan): Phase 7 done, live URLs and drill results` |

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

## Phase 10: Accounts (after the first deploy)
TourScout becomes a product people come back to: **sign in with Google or email**, with **Continue as guest** kept as an
equal option (no wall in front of the planner).

**Design**
- **Neon Auth** (managed Better Auth) on the same Neon project: users live in the `neon_auth` schema next to our tables.
  Nothing to host; the browser talks to the Neon Auth URL directly.
- Web: `@neondatabase/auth` client + `@neondatabase/auth-ui` sign-in views. Signed in → `authClient.token()` (15-min
  EdDSA JWT) sent as `Authorization: Bearer`; guests keep `X-Session-Id`.
- API: verify the JWT against `<NEON_AUTH_URL>/.well-known/jwks.json` (PyJWT + cryptography, keys cached, `iss`/`aud`
  checked, EdDSA only). One `Owner` dependency: `user:<sub>` or `guest:<session>`.
- New `plans` table (thread_id, owner, title, created_at): who owns which run, **in Postgres** instead of memory, so
  a signed-in user's tours survive restarts and show up on every device.
- **Claim on sign-in:** plans made as a guest in this browser move to the account.
- Limits: signed-in users get a higher hourly plan limit than guests (per user, not per IP: fixes shared campus IPs).
- **My tours** page: list, reopen, rename, delete (delete removes the checkpoint too).

**Steps**
- [ ] Neon: enable Auth on the branch; enable Google (own OAuth client from Google Cloud) and email/password; set the
      Vercel URL as a trusted origin; custom SMTP (Resend free tier) for verification and reset emails.
- [ ] API: `auth.py` (JWKS verify + Owner), `plans` store (Postgres, SQLite locally), claim endpoint, `GET /api/me/plans`,
      rename/delete, per-user limits. Tests with a locally generated Ed25519 key (no network).
- [ ] Web: auth client, sign-in/up page, account menu, guest choice, token refresh, My tours page.
- [ ] Account deletion (removes user's plans) and a short privacy page (what we store: email, name, plans).
- [ ] Drills: expired token, forged token, another user's plan, guest→user claim, sign-out.

| Step | `git add` | Commit message |
|---|---|---|
| 10.1 API auth | `git add apps/api/` | `feat(api): Neon Auth JWT verification, owners and Postgres plan store` |
| 10.2 My tours API | `git add apps/api/` | `feat(api): my plans, claim guest plans on sign-in, rename/delete, per-user limits` |
| 10.3 Web sign-in | `git add apps/web/` | `feat(web): Google and email sign-in with guest option, account menu` |
| 10.4 My tours page | `git add apps/web/` | `feat(web): my tours page` |
| 10.5 Docs | `git add docs/ ARCHITECTURE.md PLAN.md .env.example render.yaml` | `docs(auth): accounts setup, privacy page and drills` |

**Before inviting real users (not code; decisions and money)**
| Blocker | Why | Options |
|---|---|---|
| **Qloo key is a hackathon key** | Hackathon access is for the event, not a public product | Ask Qloo (Discord / sales) for a startup or commercial key before launch |
| Free LLM tiers | Groq 200k tokens/day ≈ 25–30 plans; Gemini free quota is per day | Paid Gemini Flash-Lite is cents per plan; keep Groq as fallback |
| Render free sleeps / 512 MB | Slow first load, one small instance | Render Starter ($7/mo) when people actually use it |
| Email sending | Neon's shared sender is for testing only | Resend free tier (3k emails/mo) with your own domain |
| Domain | `*.vercel.app` looks like a demo | A domain (~$10/yr) for the site and the email sender |

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
