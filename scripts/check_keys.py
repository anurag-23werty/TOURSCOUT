# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27", "python-dotenv>=1.0"]
# ///
"""Check that the Qloo, Gemini and Groq keys work, and show which models are available.

Usage (from the repo root):  uv run scripts/check_keys.py
Keys are read from .env and never printed. Paste the output into docs/models.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROQ_BASE = "https://api.groq.com/openai/v1"


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def fail(msg: str) -> bool:
    print(f"  ✗ {msg}")
    return False


def check_qloo() -> bool:
    print("\nQloo")
    key = os.getenv("QLOO_API_KEY")
    if not key:
        return fail("QLOO_API_KEY not set (still waiting for the email?)")
    base = os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com").rstrip("/")
    with httpx.Client(base_url=base, headers={"X-Api-Key": key}, timeout=30) as http:
        r = http.get("/search", params={"query": "Radiohead", "types": "urn:entity:artist", "take": 1})
        if r.status_code != 200:
            hint = " (base URL must be https://hackathon.api.qloo.com)" if r.status_code == 401 else ""
            return fail(f"/search → {r.status_code}{hint}: {r.text[:200]}")
        results = r.json().get("results") or []
        if not results:
            return fail("/search returned no results for 'Radiohead'")
        entity_id = results[0].get("entity_id")
        ok(f"/search → {results[0].get('name')} ({entity_id})")

        r = http.get("/v2/insights", params={"filter.type": "urn:entity:destination",
                                             "signal.interests.entities": entity_id, "take": 3})
        if r.status_code != 200:
            return fail(f"/v2/insights → {r.status_code}: {r.text[:200]}")
        names = [e.get("name") for e in r.json().get("results", {}).get("entities", [])]
        ok(f"/v2/insights destination → {names}")
    return True


def check_gemini() -> bool:
    print("\nGemini (Google AI Studio)")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return fail("GEMINI_API_KEY not set")
    wanted = [os.getenv("GEMINI_MAIN_MODEL", "gemini-flash-latest"), os.getenv("GEMINI_LITE_MODEL", "gemini-3.5-flash-lite")]
    with httpx.Client(headers={"x-goog-api-key": key}, timeout=60) as http:
        r = http.get(f"{GEMINI_BASE}/models", params={"pageSize": 1000})
        if r.status_code != 200:
            return fail(f"list models → {r.status_code}: {r.text[:200]}")
        available = {m["name"].removeprefix("models/") for m in r.json().get("models", [])}
        flash = sorted(m for m in available if "flash" in m)
        print(f"    flash-family models: {', '.join(flash)}")

        all_good = True
        for model in wanted:
            if model not in available:
                all_good = fail(f"{model} not in the model list")
                continue
            r = http.post(f"{GEMINI_BASE}/models/{model}:generateContent",
                          json={"contents": [{"parts": [{"text": "Reply with the single word OK."}]}]})
            if r.status_code != 200:
                all_good = fail(f"{model} generateContent → {r.status_code}: {r.text[:200]}")
                continue
            ok(f"{model} works · resolves to modelVersion={r.json().get('modelVersion')}")
    print("    rate limits: see AI Studio → Usage / Rate limits (not exposed by the API)")
    return all_good


def check_groq() -> bool:
    print("\nGroq")
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return fail("GROQ_API_KEY not set")
    model = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-120b")
    with httpx.Client(base_url=GROQ_BASE, headers={"Authorization": f"Bearer {key}"}, timeout=60) as http:
        r = http.get("/models")
        if r.status_code != 200:
            return fail(f"list models → {r.status_code}: {r.text[:200]}")
        available = {m["id"] for m in r.json().get("data", [])}
        if model not in available:
            return fail(f"{model} not in the model list")

        r = http.post("/chat/completions", json={"model": model, "max_completion_tokens": 64,
                                                 "messages": [{"role": "user", "content": "Reply with the single word OK."}]})
        if r.status_code != 200:
            return fail(f"{model} chat → {r.status_code}: {r.text[:200]}")
        ok(f"{model} works")
        h = r.headers
        print(f"    limits: requests/day={h.get('x-ratelimit-limit-requests')} tokens/min={h.get('x-ratelimit-limit-tokens')}")
    return True


def main() -> None:
    if not (ROOT / ".env").exists():
        print("No .env found. Run: cp .env.example .env  and fill in the keys.")
    results = [check_qloo(), check_gemini(), check_groq()]
    print("\nAll keys OK ✅" if all(results) else "\nSome checks failed ❌ (see above)")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
