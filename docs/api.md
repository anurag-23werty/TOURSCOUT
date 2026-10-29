# TourScout HTTP API

Run locally: `cd apps/api && uv run tourscout-api` → http://127.0.0.1:8000 (interactive docs at `/docs`).

All `/api/plans…` calls need a guest session header: `X-Session-Id: <id from POST /api/sessions>`.
Sessions last 6 hours and own the plans they start; another session gets 404 for them.

## Endpoints
| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | – | `{ok, checks: {qloo_key, geonames, gemini_key, groq_key}, checkpointer}` |
| POST | `/api/sessions` | – | `{session_id, expires_in_s}` |
| GET | `/api/personas` | – | demo artists, featured first |
| POST | `/api/upload` | multipart `file`: PNG/JPEG/WebP screenshot or CSV (≤ 2 MB) | `{upload_id, preview}` (CSV rows parsed; single use, 15 min) |
| POST | `/api/plans` | `{message}` or `{persona_id}`, optional `upload_id`, `auto_approve` | **SSE** |
| POST | `/api/plans/{id}/resume` | `{answer}` | **SSE** |
| POST | `/api/plans/{id}/refine` | `{message: "skip Detroit"}` | **SSE** |
| GET | `/api/plans/{id}` | – | `{status, interrupt, plan, metros, events, llm_calls}` |
| POST | `/api/plans/{id}/compare` | – | `{tourscout, llm_only}` |
| POST | `/api/plans/{id}/outreach` | `{kind: "sponsor", brand_id}` or `{kind: "opener", metro}` | `{subject, body}` |
| GET | `/api/plans/{id}/export.csv` · `.ics` | (`?session_id=` works for plain links) | file download |
| * | `/mcp` | MCP streamable HTTP | the 7 TourScout tools for any MCP client |

## SSE events
Every streaming call sends `event: <kind>` + `data: <json>`:
| kind | data | when |
|---|---|---|
| `thread` | `{thread_id}` | first, always |
| `step` | `{node, message, data?}` | each agent step as it finishes |
| `interrupt` | `{type: "confirm_artist", question, candidates, sounds_like}` or `{type: "pick_cities", question, selected, metros}` | the run paused for the user |
| `plan` | the final plan | done |
| `error` | `{message}` | user-facing error (never a stack trace) |

Answers for `resume`:
- confirm_artist: `{"choice": "<qloo id>"}`, or `{"choice": null, "sounds_like": ["Artist A", "Artist B"]}`
- pick_cities: `{"selected": ["Chicago, IL", …]}`, or `{}` to accept the suggestion

## Limits (env, see `.env.example`)
6 plans/IP/hour, 150 plans/day overall, 30 LLM actions (resume/refine/compare/outreach)/IP/hour, 10 uploads/IP/hour,
3 plans running at once, 120 MCP requests/IP/hour. Over a limit → HTTP 429 with `Retry-After`.

## Example
```bash
SID=$(curl -s -X POST localhost:8000/api/sessions | jq -r .session_id)
curl -N -X POST localhost:8000/api/plans -H "X-Session-Id: $SID" -H 'Content-Type: application/json' \
     -d '{"persona_id": "us-02", "auto_approve": true}'
```

## Privacy
Uploads stay in memory, are deleted when a plan uses them (or after 15 minutes), and are never logged. Plans and the Qloo
cache live in the checkpoint store / private cache, never in git.
