# Deploy TourScout (free tiers)

| Piece | Service | Why |
|---|---|---|
| API + agent + `/mcp` | **Render** (free web service, Docker) | deploys `infra/api.Dockerfile` from GitHub; handles SSE |
| Web app | **Vercel** (Hobby) | static Vite build from `apps/web` |
| Saved runs + Qloo cache | **Neon** Postgres (free) | survives Render restarts and redeploys |
| Traces | **Langfuse Cloud** (Hobby) | one trace per plan run |
| Keep-alive + uptime | **UptimeRobot** (free) | pings `/health` every 5 min so Render's free tier doesn't sleep |

Do the steps in order: each one gives you a value the next one needs. Sign in to every service with GitHub.

## 1. Neon (database), about 3 min
1. https://neon.tech → **Sign up** → create a project `tourscout`, region near Oregon (`AWS us-west-2`) to sit next to Render.
2. **Connection string** → copy the *pooled* string (host contains `-pooler`). It looks like
   `postgresql://user:pass@ep-xxx-pooler.us-west-2.aws.neon.tech/neondb?sslmode=require`.
3. Keep it for step 3 (it's used twice: `DATABASE_URL` and `TOURSCOUT_CACHE_URL`). Tables are created automatically on first start.

## 2. Langfuse (traces), about 2 min
1. https://cloud.langfuse.com → sign up → new organisation + project `tourscout`.
2. **Settings → API keys → Create** → copy the public key (`pk-lf-…`) and secret key (`sk-lf-…`).
   If your project is on the US region, also note the host `https://us.cloud.langfuse.com` (set `LANGFUSE_HOST`).

## 3. Render (API), about 10 min (most of it is the first build)
1. https://render.com → sign up with GitHub → allow access to the `TOURSCOUT` repo.
2. **New → Blueprint** → pick the repo. Render reads `render.yaml` and proposes the `tourscout-api` service (free plan).
3. Fill in the secret values it asks for:

| Key | Value |
|---|---|
| `QLOO_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY` | from your local `.env` |
| `DATABASE_URL` | the Neon string |
| `TOURSCOUT_CACHE_URL` | the same Neon string |
| `WEB_ORIGINS` | leave `http://localhost:5173` for now; you'll add the Vercel URL in step 5 |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | from step 2 |
| `LANGFUSE_HOST` | `https://us.cloud.langfuse.com` (US project) or `https://cloud.langfuse.com` (EU) |

4. **Apply**. When the deploy is live, open `https://<your-service>.onrender.com/health`: you should see
   `"ok": true`, every check `true`, and `"checkpointer": "postgres"`.

## 4. Vercel (web app), about 3 min
1. https://vercel.com → **Add New → Project** → import the repo.
2. **Root Directory:** `apps/web` (Framework: Vite is detected; `vercel.json` sets the rest).
3. **Environment Variables:** `VITE_API_URL` = `https://<your-service>.onrender.com` (no trailing slash).
4. **Deploy** → you get `https://<project>.vercel.app`.

## 5. Connect them
1. Render → `tourscout-api` → **Environment** → set `WEB_ORIGINS` to
   `https://<project>.vercel.app,http://localhost:5173` → **Save** (it redeploys).
2. Open the Vercel URL → click **Hovvdy** → the plan should stream in.

## 6. UptimeRobot (keep-alive), about 2 min
1. https://uptimerobot.com → **Add New Monitor** → type **HTTP(s)**, URL `https://<your-service>.onrender.com/health`,
   interval **5 minutes**. This keeps the free Render service awake and emails you if it goes down.

## 7. Warm up and drill, about 5 min
```bash
uv run scripts/live_check.py prewarm --url https://<your-service>.onrender.com   # caches the demo artists in Neon
uv run scripts/live_check.py drills  --url https://<your-service>.onrender.com --skip-load   # failure drills, must print all ✅
```
The 10-visitor burst (`drills` without `--skip-load`) is worth running once, but not right before the demo: it uses a lot
of the free LLM quota. Then by hand: open the site in an incognito window, on your phone (mobile data, not your Wi-Fi), and run one plan with
"Let me confirm" on.

## 8. GitHub About box (hackathon requirement)
Repo page → ⚙️ next to **About** → **Website**: the Vercel URL; description: "Tour-planning agent for independent
musicians, grounded in Qloo taste data"; topics `qloo ai-agent langgraph mcp music touring`. Check **MIT License** shows.

## Use the hosted MCP server
Any MCP client can connect to `https://<your-service>.onrender.com/mcp` (streamable HTTP, rate-limited to 120 requests
per IP per hour).

## Troubleshooting
| Symptom | Fix |
|---|---|
| Web app says it can't reach the API | `VITE_API_URL` wrong (redeploy Vercel after changing it) or `WEB_ORIGINS` missing the Vercel URL |
| `/health` shows `"checkpointer": "sqlite"` | `DATABASE_URL` not set on Render |
| First request after a while takes ~50 s | Render free tier was asleep: check the UptimeRobot monitor is running |
| "AI models … at their free-tier limit" | Gemini overloaded and/or Groq's 200k tokens/day used up (evals and drills burn it fast). Wait, or run fewer plans; never run evals on demo day |
| Build fails downloading GeoNames | geonames.org was briefly down: **Manual Deploy → Clear build cache & deploy** |
