# Models: confirmed names and limits

Fill this in during Phase 0 once you have the keys. **Don't trust a model name until it shows up in a live listing.**

## Check what is available
```bash
# Gemini: list models (look for gemini-flash-latest, gemini-3.8-flash, gemini-3.5-flash-lite, any flash-lite "-latest" alias)
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" \
  | python3 -c "import sys,json; [print(m['name'], '|', m.get('displayName')) for m in json.load(sys.stdin)['models']]"

# Groq: list models (look for openai/gpt-oss-120b)
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY" \
  | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data']]"
```
Free-tier rate limits: AI Studio → *Usage / Rate limits* page; Groq console → *Settings → Limits*.

## Record (fill in)
| Role | Model ID | Confirmed in listing? | RPM | RPD | TPM | Notes |
|---|---|---|---|---|---|---|
| Main agent | `gemini-flash-latest` | ☐ | | | | resolves to: |
| Cheap steps | `gemini-3.5-flash-lite` (or `-latest` alias) | ☐ | | | | |
| Fallback + eval judge | `openai/gpt-oss-120b` | ☐ | | ~1000 | | text-only |

## Quick capability checks (Phase 0, by hand in AI Studio / Groq playground)
- [ ] Gemini: tool call with a dummy `search_entities` function → returns a function call
- [ ] Gemini: structured output with an enum field (for vibe labels)
- [ ] Gemini: image input → describes a sample travel photo
- [ ] Gemini: audio input → transcribes a 10-second clip
- [ ] Groq gpt-oss-120b: same dummy tool call works

## Budget estimate (fill in after checks)
Calls per trip ≈ extract 1 + plan 1 + compose 1–3 + explain 1 + routing 1–2 (lite) ≈ **5–8 LLM calls per trip**.
Daily trips the free tier supports = RPD(main) ÷ ~5 = ______. This sets the per-IP and global caps in Phase 4.
