# Evals

**Question we answer:** does TourScout (Qloo-grounded agent) beat an LLM-only planner on real traveller tastes?

## Persona set: `personas/personas.jsonl`
30 personas (inputs only; **no Qloo data is stored here**, per Qloo's terms):
- `solo-01…18`: varied cross-domain tastes (film, music, books, podcasts, games, brands, food), budgets, paces, India + global
- `group-01…08`: 2–4 travellers, from overlapping to opposite tastes, plus dietary conflicts and fixed destinations
- `edge-01…04`: prompt injection, empty signals, low-coverage destination, out-of-range constraints

Fields: `id`, `mode`, `travellers[{name, input}]`, `constraints{days, budget, pace, dietary, accessibility, origin, destination}`, `tests[]` (what this persona checks).

## Metrics (implemented in Phase 7)
| Metric | How | Target |
|---|---|---|
| Grounding rate | % of recommended venues that resolve to a real Qloo entity (baseline names are checked via `/search`) | TourScout 100% |
| Constraint satisfaction | rule checks: days, budget, dietary, pace | ≥ 95% |
| Taste relevance | blind pairwise LLM judge (Groq `gpt-oss-120b`) + 5–10 humans on a subset | TourScout preferred in most comparisons |
| Group fairness | min per-person affinity across the plan (group personas) | higher than baseline |
| Edge behaviour | pass/fail per `tests[]` | all pass |
| Latency / cost | p50, p95 time; LLM calls per trip | p50 < 30 s |

Raw run outputs (they contain Qloo data) go to `reports/raw/`, which is git-ignored. Only aggregate numbers are committed.
