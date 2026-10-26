# TourScout: Build Plan (Phase 0 → Submission)

> **Hackathon:** Qloo LLM Hackathon (Devpost). Build an *agent* whose recommendations are grounded in Qloo's taste graph.
> **Submission needs:** live hosted demo (end-to-end, public), public repo with all source + run instructions,
> text description of what makes it Qloo-powered, OSS license visible in the repo's About section. No video required.
> **Architecture:** see `ARCHITECTURE.md`.

---

## The pitch

**TourScout is a travel agent that knows what you (and your friends) actually love.**
Tell it your movies, music, food, brands, or drop a few photos. It finds destinations and places through Qloo's
taste graph, plans the trip, and explains every pick from real affinity data.

**The "only works because of Qloo" moment: group trips.**
Four friends with completely different tastes → TourScout blends their Qloo profiles and finds the city, cafés and
nights out that score well for *everyone*, with a per-person match bar. An LLM alone can only guess here. Qloo has the data.

**Proof, not claims:** a built-in *LLM-only vs TourScout* compare mode, plus an eval report in the README.

---

## Phase 0: Setup and unblockers (Day 0–1) ⚠️ start immediately
Qloo hackathon keys are issued **manually by email and can take a few business days**, so request one first.

- [ ] Request the Qloo API key (developer guide form). Check spam. Join the Qloo Discord (#api-help).
- [ ] Get keys/accounts: Google AI Studio (Gemini), Groq, GitHub, Vercel, Railway or Fly, Neon, Langfuse, UptimeRobot.
- [ ] List models from the Gemini and Groq APIs: confirm `gemini-flash-latest`, `gemini-3.5-flash-lite`, `openai/gpt-oss-120b` and their free-tier limits (requests/min, requests/day). Record them in `docs/models.md`.
- [ ] Create the **public** GitHub repo `tourscout` with the MIT `LICENSE` (set it in About), README stub, `.gitignore`, `.env.example`.
- [ ] Lock the scope: write down MVP vs stretch (below) and the definition of done.
- [ ] While waiting for the key: wireframe the 4 screens (Home/personas → Taste chips → Destinations → Trip + map), draft prompts, write 25–30 eval personas (inputs only).
- [ ] Read the Qloo docs: Insights deep dive, Parameter Reference, Entity Type Parameter Guide.

**Exit criteria:** keys requested or received, repo public with license, wireframes and personas drafted.

---

## Phase 1: Understand Qloo's data (Day 2–3)
The goal is to *know* the data before designing prompts around it. Invalid params are silently ignored, so verify everything.

- [ ] Manually explore `/search`, `/v2/tags`, `/v2/insights` for `destination` and `place` (Postman/Bruno collection, committed without responses).
- [ ] Answer and document in `docs/qloo-notes.md`:
  - Which signals/filters actually change results for `destination` vs `place`?
  - How do location filters behave (city name vs coordinates/radius)? Which place categories/tags exist (restaurant, café, bar, museum, hotel)?
  - What do affinity scores look like? What do the tag metadata fields look like (for explanations)?
  - Coverage: big vs small cities, India vs EU/US.
- [ ] Build the **param allow-list per `filter.type`** and a first **vibe label → tag URN** mapping (~40 labels).
- [ ] Sanity check the core hypothesis: do different taste inputs produce clearly different destinations/places? (If not, adjust the idea now, not later.)

**Exit criteria:** documented, reproducible Qloo calls for every agent step; hypothesis confirmed.

---

## Phase 2: Qloo MCP server (Day 4–5)
- [ ] Qloo client: auth, retries/backoff on 429, timeouts, response trimming, private Postgres cache.
- [ ] MCP tools: `search_entities`, `search_tags`, `get_insights`, `blend_tastes`, `explain_affinity`, with clear tool descriptions (LLMs pick tools from these descriptions).
- [ ] Param validation against the allow-list; friendly tool errors the LLM can recover from.
- [ ] Unit tests with recorded *fake* fixtures (not real Qloo data) plus a small live smoke test.
- [ ] Try it in **Claude Desktop / MCP Inspector** and write `docs/mcp-claude-desktop.md`.

**Exit criteria:** any MCP client can ask "places in Lisbon for someone who loves Wes Anderson films" and get grounded results.

---

## Phase 3: Agent core with LangGraph (Day 6–9)
- [ ] State model, nodes 1–9 from the architecture, run from the CLI first (no UI).
- [ ] Structured outputs for extraction and itinerary; human-in-the-loop interrupts (confirm chips, pick destination).
- [ ] **Grounding validator:** every itinerary item maps to a Qloo candidate ID; constraint checks; retry loop (max 2).
- [ ] Explanation step grounded in Qloo tags/affinity ("Because you like X and Y → this place's tags A, B").
- [ ] **Group blend** node with fairness ranking.
- [ ] Refinement router ("make day 2 chill", "swap museum for street food").
- [ ] **LLM-only baseline** planner (same prompt, no tools) for compare mode and evals.
- [ ] Model layer: Gemini primary → automatic fallback to Groq `gpt-oss-120b`; Flash-Lite for cheap steps; resolved model version logged per trace.
- [ ] Langfuse tracing on every node and tool call.

**Exit criteria:** CLI produces a full solo trip and a 3-person group trip, 100% grounded, traced.

---

## Phase 4: Backend API (Day 10)
- [ ] FastAPI: sessions, `/chat` with **SSE streaming** of agent events, `/resume` for interrupts, `/upload`, `/compare`, `/personas`, `/health`.
- [ ] Postgres checkpointer so conversations survive restarts.
- [ ] Rate limiting (per IP, per session, global daily cap), input size limits, CORS.

**Exit criteria:** the whole flow works via HTTP (curl/Bruno) with streamed events.

---

## Phase 5: Frontend (Day 11–14)
- [ ] One-click **demo personas** on the home page (judges can try it in 10 seconds without typing).
- [ ] Taste input (text + chips), confirmable resolved-entity chips with images.
- [ ] **Live agent timeline** showing each step/tool call as it streams.
- [ ] Destination cards with affinity and "why"; itinerary by day; Leaflet map with pins.
- [ ] Group mode: add travellers, per-person match bars.
- [ ] **Compare tab:** LLM-only vs TourScout side by side, with hallucinated venues flagged.
- [ ] Mobile responsive; loading/empty/error states.

**Exit criteria:** a stranger can complete a trip end-to-end on desktop and phone with no instructions.

---

## Phase 6: Multimodal + polish features (Day 15–16)
- [ ] Photos → Gemini image input, structured output limited to our ~40 vibe labels → Qloo tags → extra signals.
- [ ] Voice input → Gemini audio input.
- [ ] Fallback UX: if Gemini is unavailable (Groq is text-only), show "type your vibe instead".
- [ ] Shareable trip link (read-only view of a saved itinerary).
- Stretch only if ahead: calendar/ICS export, budget estimates, accessibility filters.

**Exit criteria:** "drop 3 Pinterest screenshots → trip" works reliably.

---

## Phase 7: Evals, proving Qloo matters (Day 17–18)
- [ ] Run all personas through TourScout and the LLM-only baseline.
- [ ] Metrics: grounding rate, constraint satisfaction, LLM-as-judge pairwise taste relevance, group fairness, latency, cost.
- [ ] Small human preference check (5–10 friends, blind A/B).
- [ ] Results table and short analysis in the README (including where TourScout *loses*: honesty reads well).
- [ ] Add an eval smoke run to CI.

**Exit criteria:** a numbers-backed claim like "X% grounded vs Y% for LLM-only; preferred in Z% of blind comparisons".

---

## Phase 8: Hardening and deploy (Day 19–20)
- [ ] Docker images for api + mcp; deploy to Railway/Fly; web to Vercel; Neon Postgres; env secrets.
- [ ] Pre-warm the private cache for demo personas; UptimeRobot on `/health`; no cold starts.
- [ ] Failure drills: Qloo 429/empty results, Gemini 429 / daily quota exhausted (fallback to Groq), both providers down (cached personas still work), bad uploads, long inputs, prompt injection.
- [ ] Test from incognito on another device and network, phone and desktop.

**Exit criteria:** the live URL survives 10 rapid sessions and every failure drill degrades gracefully.

---

## Phase 9: Submission (Day 21)
- [ ] README: pitch, **live demo link**, **MCP endpoint**, screenshots/GIF, architecture diagram, "How Qloo powers this" section, eval table, local run steps, license badge.
- [ ] Devpost description: problem → what the agent does → why it fails without Qloo (compare + evals) → tech → challenges → what's next.
- [ ] Confirm: repo public, LICENSE visible in About, no keys/Qloo data in git history, demo usable without login.
- [ ] Submit before the deadline (aim 24h early).

---

## Phase 10: After the hackathon (resume value)
- [ ] Short blog post / LinkedIn write-up: "Building a taste-grounded agent with LangGraph + MCP: evals vs an LLM-only baseline".
- [ ] Resume bullets (fill in the real numbers from Phase 7), e.g.:
  - *Built TourScout, a LangGraph travel agent grounded in Qloo's 250M-entity taste graph via a custom MCP server; deployed full-stack (FastAPI, React, Postgres).*
  - *Designed an eval harness over 30 personas; grounding improved from Y% (LLM-only) to X%, preferred in Z% of blind comparisons.*
  - *Implemented group-taste blending with fairness ranking, streaming agent traces, and human-in-the-loop checkpoints.*

---

## Scope guard

| MVP (must ship) | Stretch (only if ahead) |
|---|---|
| Solo + group trip, Qloo MCP server, LangGraph agent with HITL, grounding validator, streaming timeline, map, compare mode, demo personas, evals, hosted | Photos/voice, shareable link, ICS export, budget estimates, accessibility filters, auth/saved profiles |

Note: multimodal is Phase 6, deliberately after the core works. A polished core beats a half-working feature list.

## Risks
| Risk | Mitigation |
|---|---|
| Qloo key arrives late | Request on Day 0; do wireframes/prompts/personas while waiting |
| Weak Qloo coverage for some cities | Phase 1 coverage check; steer personas to well-covered destinations; graceful "broaden search" fallback |
| Silent param failures | Per-type allow-list + tests that assert results change when signals change |
| Quota burn from public demo | Private cache, rate limits, daily cap; ask in Discord #api-help for higher limits |
| LLM hallucinated venues | Grounding validator + retry; compare mode turns this into a selling point |
| Gemini free daily quota burned by public traffic | Flash-Lite for cheap steps, private cache, rate limits, auto-fallback to Groq |
| Numbered Gemini Flash retired during judging | Use the `gemini-flash-latest` alias in production; log the resolved version |
| Deadline crunch | Scope guard above; stretch items are cut first |

> Day numbers assume ~3 weeks. Scale them to the actual deadline on Devpost; the phase order stays the same.
