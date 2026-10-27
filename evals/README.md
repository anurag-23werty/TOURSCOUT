# Evals

**Question:** does TourScout (Qloo-grounded agent) plan better tours for indie artists than an LLM-only planner?

## Persona set: `personas/personas.jsonl` (30)
Inputs only. **No Qloo data is stored here** (Qloo terms). `reach_synthetic` values are made-up test inputs, not real stats.
- `us-01…12`: US artists across regions, sizes (Qloo popularity .78–.99) and genres (indie, folk, soul, Spanish-language)
- `eu-01…03`: UK and EU multi-country routes
- `in-01…07`: Indian artists, incl. fly-between-cities tours (`max_drive_km: 0`) and low-coverage acts
- `nq-01…04`: artists **not on Qloo** (verified: search returns a different artist) → "sounds like" path and fuzzy-match traps
- `edge-01…04`: prompt injection, empty region, impossible constraints, everything already served

Fields: `id, artist, sounds_like[], home_base, regions[], window[start,end], n_shows, draw[min,max], max_drive_km, past_cities[], reach_synthetic{city: listeners}, notes?, tests[]`.

## Metrics (implemented in Phase 6)
| Metric | How | Target |
|---|---|---|
| **Opener locality** | % of suggested openers whose MusicBrainz area/begin-area is in the show's metro | TourScout ≫ LLM-only |
| **Opener fit** | % of openers with Qloo popularity < headliner and an overlapping genre tag | ≥ 90% |
| **Venue grounding** | % of venues that resolve to a real Qloo place in the right city (LLM-only names are checked via `/search`) | TourScout 100% |
| **Backtest** | For 10–15 real artists, the share of cities from their last real tour (setlist.fm) that are in TourScout's top-N demand metros, vs a population-only ranking | beat the population baseline |
| **Sponsor relevance** | blind pairwise LLM judge (Groq gpt-oss-120b) + 5–10 humans on a subset | TourScout preferred |
| **Constraint satisfaction** | dates, n_shows, max drive, draw range respected | ≥ 95% |
| **Edge behaviour** | pass/fail per `tests[]` | all pass |
| **Latency / cost** | p50 and p95 time to full plan; LLM calls per plan | p50 < 45 s |

Raw run outputs contain Qloo data → `reports/raw/` (git-ignored). Only aggregate numbers are committed.
Backtest caveat: real tours aren't necessarily optimal, so this measures *signal*, not ground truth. We say so in the README.
