# Phase 0: Accounts, keys and repo setup

Do these **by hand** (they need your login). Tick each one off.

## 1. Request the Qloo key first (slowest step)
- [ ] Fill in the form: https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide#getting-your-api-key
- [ ] Join the Qloo Hackathon Discord and check `#api-help`
- [ ] Keys arrive by email in a few business days. **Check spam.** Resubmit if nothing comes after several days.
- Base URL is `https://hackathon.api.qloo.com`; the header is `X-Api-Key`. Hackathon keys fail (401) on the staging/prod URLs.

## 2. LLM keys
| Service | Get key | `.env` variable |
|---|---|---|
| Google AI Studio (Gemini, primary) | https://aistudio.google.com/apikey | `GEMINI_API_KEY` |
| Groq (fallback) | https://console.groq.com/keys | `GROQ_API_KEY` |

Then follow `docs/models.md` to confirm the model names and free-tier limits.

## 3. Hosting and tooling accounts (sign in with GitHub)
| Service | Used for | Free tier note |
|---|---|---|
| GitHub | public repo, CI | — |
| Vercel | frontend hosting | fine |
| Railway **or** Fly.io | API + MCP containers | pick one that doesn't sleep (cold starts lose judges) |
| Neon | Postgres (sessions, checkpoints, private Qloo cache) | fine |
| Langfuse Cloud | agent traces | fine |
| UptimeRobot | `/health` pings, keep-alive | fine |

## 4. Create the public repo
`gh` isn't installed here, so create it on github.com:
1. New repository → name `tourscout` → **Public** → *don't* add a README/license (we already have them).
2. Locally (you run these; Claude doesn't commit):
   ```bash
   cd ~/Tourscout
   git init -b main
   git add .
   git commit -m "chore: phase 0 scaffolding (license, docs, personas, wireframes)"
   git remote add origin https://github.com/<your-username>/tourscout.git
   git push -u origin main
   ```
3. On the repo page → ⚙️ next to **About** → add the description, website (later) and topics: `qloo`, `ai-agent`, `langgraph`, `mcp`, `music`, `touring`.
   GitHub detects `LICENSE` automatically and shows **MIT License** in About. Check that it appears.

## 5. Local tools to install (for Phase 1+)
- Python 3.12 (3.13 works, but some agent libraries lag behind; `uv` makes this easy: `brew install uv`)
- Node 20+ (you have it)
- Bruno or Postman (to explore the Qloo API in Phase 1)
- Optional: `brew install gh` for GitHub from the terminal
