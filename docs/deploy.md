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

## Accounts (sign-in), optional
Guests keep working without this. With it, people can sign in with Google or email and keep **My tours** on every device.

1. **Neon** → project → **Auth** → enable. Sign-in methods: **Email & password** and **Google**.
   **Configuration → Domains:** add `https://<project>.vercel.app` (and `http://localhost:5173` for local dev).
   Copy the **Auth URL** (`https://ep-….neonauth.….aws.neon.tech/neondb/auth`). It's public, not a secret.
2. **Render** → `tourscout-api` → Environment: `NEON_AUTH_URL` = the Auth URL → Save, rebuild, and deploy.
   `/health` stays the same; the log says `sign-in: Neon Auth`.
3. **Vercel** → project → Settings → Environment Variables: `VITE_NEON_AUTH_URL` = the same Auth URL →
   **Deployments → ⋯ → Redeploy** (Vite bakes it in at build time).
4. Optional, so **Delete account** also removes the login (managed Neon Auth has no self-service delete):
   Neon → Account settings → **API keys** → create one; add `NEON_API_KEY`, `NEON_PROJECT_ID` (Settings → General)
   and `NEON_BRANCH_ID` (Branches → production → ID, `br-…`) on Render. Without them, deleting an account removes
   the tours and asks you to remove the login in Neon → Auth → Users.

**Before real users:** in Neon → Auth, use your own Google OAuth client (Google Cloud → Credentials → OAuth client,
redirect URI `<Auth URL>/callback/google`), set a custom SMTP sender (e.g. Resend) and turn on email verification, set
the app name, and turn off **Allow localhost**. See Neon's production checklist.

How it works: the browser signs in with Neon Auth directly (session cookie `SameSite=None; Partitioned`); the API only
sees a 15-minute EdDSA JWT (`Authorization: Bearer`), checked against `<Auth URL>/.well-known/jwks.json`. Who owns which
tour is in the `plans` table next to the checkpoints; tours planned as a guest move into the account at sign-in.

## Use the hosted MCP server
Besides the website, the API serves TourScout's Qloo tools (demand map, venues, openers, sponsors, promo spots…) as an
**MCP server**, so any MCP client can call them directly:

```
https://tourscout-api.onrender.com/mcp
```
Streamable HTTP, no key needed; limited to 120 requests per IP per hour.

- **Claude Code:** `claude mcp add --transport http tourscout https://tourscout-api.onrender.com/mcp`
- **Claude Desktop / claude.ai:** Settings → Connectors → **Add custom connector** → paste the URL.
- **Cursor / others:** add an HTTP (streamable) MCP server with that URL.

Then ask, e.g. *"Where are Hovvdy's fans under-served in the US Midwest? Suggest local openers."*

Only `RENDER_EXTERNAL_HOSTNAME` (set by Render) and `MCP_ALLOWED_HOSTS` are accepted as the `Host`: other hosts get
`421` (DNS-rebinding protection). On a custom domain, add it to `MCP_ALLOWED_HOSTS`.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Web app says it can't reach the API | `VITE_API_URL` wrong (redeploy Vercel after changing it) or `WEB_ORIGINS` missing the Vercel URL |
| `/health` shows `"checkpointer": "sqlite"` | `DATABASE_URL` not set on Render |
| First request after a while takes ~50 s | Render free tier was asleep: check the UptimeRobot monitor is running |
| "AI models … at their free-tier limit" | Gemini overloaded and/or Groq's 200k tokens/day used up (evals and drills burn it fast). Wait, or run fewer plans; never run evals on demo day |
| MCP client gets `421 Misdirected Request` | the hostname isn't allowed: add it to `MCP_ALLOWED_HOSTS` on Render |
| "Sign in" button missing on the site | `VITE_NEON_AUTH_URL` not set on Vercel, or set but not redeployed |
| Signed in, but the API says "sign-in isn't enabled" | `NEON_AUTH_URL` not set on Render |
| Google sign-in returns an "untrusted origin" / redirect error | the site URL isn't in Neon → Auth → Configuration → Domains |
| Local API hangs at "Waiting for application startup" | `DATABASE_URL` points at Neon and your network blocks port 5432: run with `DATABASE_URL= TOURSCOUT_CACHE_URL=` (SQLite) |
| Build fails downloading GeoNames | geonames.org was briefly down: **Manual Deploy → Clear build cache & deploy** |
