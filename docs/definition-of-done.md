# Scope and definition of done

## MVP (we don't submit without these)
| # | Feature | Done when |
|---|---|---|
| 1 | Artist resolve | Name → Qloo artist with confirm step; not on Qloo → "sounds like" artists used as the signal, and the UI says so |
| 2 | Demand map | Heatmap for the chosen region aggregated to metros; map shows demand per metro |
| 3 | Unserved demand | Artist's reach (manual cities / CSV; screenshot is stretch) compared with demand; cities labelled unserved / proven / low |
| 4 | Route | N stops in the date window, ordered, with drive km per leg and days off; respects max drive per day |
| 5 | Venues | 3–5 per stop from Qloo live-music-venue tags, ranked by audience affinity; capacity marked "verify" |
| 6 | Local openers | 3–5 per stop, smaller than the headliner (Qloo popularity), "local" badge when MusicBrainz confirms |
| 7 | Sponsors | Top brands nationally and per city with affinity and uplift; one-click sponsor pitch email |
| 8 | Opener DM | One-click outreach message per opener |
| 9 | Grounding | 100% of venues/openers/brands are Qloo IDs from this run; every quoted number comes from computed data |
| 10 | Refinement | "skip Texas", "rooms under 500", "add a day off" work without restarting |
| 11 | Live timeline | Each agent step and tool call streams to the UI |
| 12 | Compare | LLM-only plan next to TourScout; flags non-local openers, unverifiable venues, too-big openers |
| 13 | Demo artists | One click → full plan; works even under LLM rate limits (cached) |
| 14 | MCP server | Public endpoint; documented Claude Desktop setup |
| 15 | Evals | Results table in README (opener locality, opener fit, venue grounding, backtest) |
| 16 | Hosted + repo | Public URL, no login, no cold start, phone + desktop; public repo, MIT in About, no secrets/Qloo data in history |

## Stretch (only after all MVP items are green)
Streaming-dashboard screenshot ingest · promo spots · ICS export · multi-region tours · merch and poster-style ideas from fan taste

## Out of scope (explicitly)
Booking or contracting venues · ticketing · real venue capacity/availability · payments · user accounts · flight/van rental prices

## Quality bar
- A stranger completes a plan end-to-end in under 3 minutes without instructions.
- First demand map in < 10 s (streamed progress); full plan in < 45 s.
- No unhandled error screens; every failure has a friendly message and a retry.
