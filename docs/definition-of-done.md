# Scope and definition of done

## MVP (we don't submit without these)
| # | Feature | Done when |
|---|---|---|
| 1 | Taste input → resolved Qloo entities | User sees confirmable chips (name, type, image) for each input; can remove/fix them |
| 2 | Destination discovery | 3–5 destinations from Qloo `destination` insights, each with a Qloo-grounded "why" |
| 3 | Place discovery | Places per category from Qloo `place` insights with map coordinates |
| 4 | Itinerary | Day-by-day plan; **100% of items are Qloo-returned IDs** (validator enforced) |
| 5 | Group mode | 2–4 travellers; fairness-ranked picks; per-person match bar |
| 6 | Refinement | "Make day 2 more chill" style edits work without restarting |
| 7 | Live agent timeline | Each node/tool call streams to the UI as it happens |
| 8 | Compare mode | LLM-only plan next to TourScout plan; unverifiable venues flagged |
| 9 | Demo personas | One click → full trip, works even if the LLM providers are rate-limited (cached) |
| 10 | Qloo MCP server | Public endpoint; documented setup for Claude Desktop |
| 11 | Evals | Persona set run against the baseline; results table in README |
| 12 | Hosted | Public URL, no login, no cold start, works on phone and desktop |
| 13 | Repo | Public, MIT license in About, run instructions, no secrets or Qloo data in history |

## Stretch (only after all MVP items are green)
Photo input · voice input · shareable trip link · ICS export · budget estimates · accessibility filters

## Out of scope (explicitly)
Bookings/payments · user accounts · flights/hotel prices · native mobile apps · real-time availability

## Quality bar
- A stranger completes a trip end-to-end in under 2 minutes with no instructions.
- p50 time to the first destination cards < 10 s; full itinerary < 30 s (streamed progress throughout).
- No unhandled error screens: every failure shows a friendly message and a retry path.
