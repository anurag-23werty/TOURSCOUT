# tourscout-api

The TourScout agent: deterministic scoring, the LangGraph tour planner, the LLM-only baseline and (Phase 4) the FastAPI
backend. It calls the same tool functions as the MCP server in `packages/tourscout_mcp`, in-process.

## Run
```bash
cd apps/api
uv sync
uv run tourscout --persona us-02 --auto                 # Hovvdy, Midwest: no checkpoints
uv run tourscout --persona nq-02 --auto --compare       # Easy Wanderlings (not on Qloo) + LLM-only baseline
uv run tourscout --persona us-02                        # answer the two checkpoints in the terminal
uv run tourscout --persona us-02 --auto --refine "skip Detroit"
uv run tourscout "I'm Hovvdy, 8 shows in the Midwest in April, leaving from Austin"
```
Plans (JSON, CSV, ICS) go to `~/.cache/tourscout/plans/`, outside the repo, because they contain Qloo-derived data.
Needs `QLOO_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY` in the repo-root `.env`, and GeoNames (`uv run ../../data/download_geonames.py`).

Speed tip: when `gemini-flash-latest` is overloaded, `GEMINI_MAIN_MODEL=gemini-flash-lite-latest` brought a 10-date plan from
56 s to 17 s in our test.

## Layout
| Path | What |
|---|---|
| `tourscout_api/scoring/opportunity.py` | demand, reach, gap, labels, city selection (pure functions) |
| `tourscout_api/scoring/route.py` | nearest-neighbour + 2-opt routing, travel/rest days, drive and date limits |
| `tourscout_api/core/llm.py` | Gemini main → lite → Groq with circuit breakers, Pydantic validation, call log |
| `tourscout_api/agent/graph.py` | the LangGraph state machine (nodes, checkpoints, venue swap loop, compose ⇄ validate, refine) |
| `tourscout_api/agent/runner.py` | `TourAgent.start / resume / refine` on a thread id |
| `tourscout_api/agent/validate.py` | grounding validator + salvage |
| `tourscout_api/agent/outputs.py` | plan builder (names from ids), CSV / ICS, sponsor pitch, opener DM, refine parser |
| `tourscout_api/agent/reach.py` | listeners from rows, CSV or a dashboard screenshot (Gemini vision) |
| `tourscout_api/agent/prompts/*.md` | every prompt, as a readable file |
| `tourscout_api/baseline/` | the same request with no tools (Compare tab, evals) |
| `tourscout_api/cli.py` | the command above |

## Test
```bash
uv run pytest          # 46 tests: scoring, model fallback, reach, validator, outputs, agent graph (fake tools + fake LLM)
```
