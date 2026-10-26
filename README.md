# TourScout 🧭

**A travel agent that knows what you (and your friends) actually love.**

TourScout is an AI agent that plans solo and group trips from people's real tastes (movies, music, food, brands, photos).
Every destination, café and night out comes from **Qloo's taste graph** (250M+ entities). The agent never guesses a venue.

> 🚧 Under construction for the **Qloo LLM Hackathon**. Live demo and MCP endpoint links will appear here.

| | |
|---|---|
| 🌐 Live demo | _coming soon_ |
| 🔌 Qloo MCP server | _coming soon_ |
| 📐 Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 🗺️ Build plan | [PLAN.md](PLAN.md) |

## Why it needs Qloo
An LLM on its own recommends what is *popular* and sometimes invents places. TourScout:
- grounds every recommendation in Qloo affinity data (a validator rejects anything Qloo didn't return),
- blends several travellers' tastes and ranks options by fairness, so the least-matched person still enjoys the trip,
- explains each pick from Qloo's tags ("because you love X and Y").

A built-in **LLM-only vs TourScout** compare mode and an eval report show the difference with numbers.

## Tech
LangGraph agent · custom Qloo MCP server · FastAPI · React + Vite · Google Gemini (primary) · Groq `gpt-oss-120b` (fallback) · Postgres · Langfuse

## Privacy
TourScout needs no account and stores no personal data beyond your session. Inputs are sent to Google Gemini (free tier)
and Groq to generate plans, and may be used by those providers under their terms.

## Run locally
_Setup instructions will be added in Phase 2–4._ Copy `.env.example` to `.env` and fill in your keys.

## License
[MIT](LICENSE)
