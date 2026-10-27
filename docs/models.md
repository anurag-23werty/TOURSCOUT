# Models: confirmed names and limits

Re-check with `uv run scripts/check_keys.py`. **Don't trust a model name until it shows up in a live listing.**

## Results of the 27 Oct check
| Role | Model ID | In listing? | Test call | Notes |
|---|---|---|---|---|
| Main agent | `gemini-flash-latest` | ✅ | ⚠️ **503 "high demand"** | temporary per Google; this is why the Groq fallback must exist from day 1 |
| Cheap steps | `gemini-flash-lite-latest` | ✅ | — | alias exists → use it instead of the numbered lite model |
| (numbered lite) | `gemini-3.5-flash-lite` | ✅ | ✅ works | resolves to `gemini-3.5-flash-lite` |
| Fallback + eval judge | `openai/gpt-oss-120b` | ☐ | ☐ | **Groq key not added yet** |

Other Flash models in the listing: `gemini-3.8-flash`, `3.7-flash`, `3.6-flash`, `3.5-flash`, `gemini-3-flash-preview`, `2.5-flash`
(+ image/TTS/live variants). Pinning `gemini-3.8-flash` is an option for reproducible evals; keep the alias in production.

## Free-tier limits (fill in)
| Model | RPM | RPD | TPM | Where to see |
|---|---|---|---|---|
| gemini-flash-latest | | | | AI Studio → Usage / Rate limits |
| gemini-flash-lite-latest | | | | AI Studio |
| openai/gpt-oss-120b | | ~1000 | | `check_keys.py` prints Groq's limit headers |

## Capability checks (by hand, Phase 1)
- [ ] Gemini: tool call with a dummy `find_venues` function
- [ ] Gemini: structured output (intake schema)
- [ ] Gemini: read a streaming-dashboard screenshot into `{city, value}` rows
- [ ] Groq gpt-oss-120b: same dummy tool call

## Budget estimate
LLM calls per tour plan ≈ intake 1 (lite) + screenshot 0–1 + compose 1–3 + pitch/DM 2–4 (on demand) + refine 1 (lite) ≈ **5–10**.
Daily plans the free tier supports ≈ RPD(main) ÷ ~6. This sets the per-IP and global caps in Phase 4.
