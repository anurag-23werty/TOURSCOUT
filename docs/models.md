# Models: confirmed names and limits

Re-check with `uv run scripts/check_keys.py`. **Don't trust a model name until it shows up in a live listing.**

## Results of the 27 Oct check
| Role | Model ID | In listing? | Test call | Notes |
|---|---|---|---|---|
| Main agent | `gemini-flash-latest` | ✅ | ⚠️ **503 "high demand"** | temporary per Google; this is why the Groq fallback must exist from day 1 |
| Cheap steps | `gemini-flash-lite-latest` | ✅ | — | alias exists → use it instead of the numbered lite model |
| (numbered lite) | `gemini-3.5-flash-lite` | ✅ | ✅ works | resolves to `gemini-3.5-flash-lite` |
| Fallback + eval judge | `openai/gpt-oss-120b` | ✅ | ✅ works | Groq limits: 1,000 requests/day, 8,000 tokens/min |
| (pinned main, option) | `gemini-3.8-flash`, `gemini-3.7-flash` | ✅ | ⚠️ 503 too | the whole Flash family was overloaded during the check |

Other Flash models in the listing: `gemini-3.8-flash`, `3.7-flash`, `3.6-flash`, `3.5-flash`, `gemini-3-flash-preview`, `2.5-flash`
(+ image/TTS/live variants). Pinning `gemini-3.8-flash` is an option for reproducible evals; keep the alias in production.

## Free-tier limits (fill in)
| Model | RPM | RPD | TPM | Where to see |
|---|---|---|---|---|
| gemini-flash-latest | | | | AI Studio → Usage / Rate limits |
| gemini-flash-lite-latest | | | | AI Studio |
| openai/gpt-oss-120b | | 1,000 | 8,000 | from Groq's `x-ratelimit-*` headers |

## Capability checks (by hand, Phase 1)
| Check | gemini-flash-lite-latest | gemini-flash-latest / 3.8 / 3.7 | Groq gpt-oss-120b |
|---|---|---|---|
| Tool call (dummy `find_venues`) | ✅ correct args · **21 s** | ⚠️ 503 / timeout | ✅ correct args · **0.8 s** |
| Structured output (intake schema) | ✅ valid JSON · **33 s** | ⚠️ 503 | ✅ valid JSON (`json_schema`) · **1.0 s** |
| Screenshot → `{city, value}` rows | ☐ needs a sample image (Phase 3) | ☐ | n/a (text only) |

### What this means for the design
- Gemini stays the default as planned, but **every LLM call gets a fast-fail timeout (≈ 8 s) and one retry, then falls over to Groq.**
  With today's latency, a plan that waited on Gemini would break the "< 45 s" quality bar.
- Groq's 8,000 tokens/min is the tight limit: keep prompts trimmed (the composer gets IDs + numbers, not raw Qloo JSON).
- The screenshot reader is Gemini-only (Groq's gpt-oss is text-only). If Gemini is down, the UI asks for a CSV paste instead.
- Log `modelVersion` and the provider on every call to Langfuse, so the Compare tab and evals show which model answered.

## Budget estimate
LLM calls per tour plan ≈ intake 1 (lite) + screenshot 0–1 + compose 1–3 + pitch/DM 2–4 (on demand) + refine 1 (lite) ≈ **5–10**.
Daily plans the free tier supports ≈ RPD(main) ÷ ~6. This sets the per-IP and global caps in Phase 4.
