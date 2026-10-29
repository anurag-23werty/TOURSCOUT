from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from tourscout_api.core.config import LLMSettings
from tourscout_api.core.llm import LLM, LLMUnavailable

pytestmark = pytest.mark.anyio


class Intake(BaseModel):
    artist: str
    n_shows: int


SETTINGS = LLMSettings(gemini_key="g", groq_key="q", primary="gemini", primary_timeout_s=1, cooldown_s=60)
GOOD = {"artist": "Hovvdy", "n_shows": 6}


def gemini_ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json={
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}], "modelVersion": "gemini-3.8-flash",
    })


def groq_ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json={"model": "openai/gpt-oss-120b", "choices": [{"message": {"content": json.dumps(payload)}}]})


def router(gemini, groq):  # type: ignore[no-untyped-def]
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        provider = "gemini" if "googleapis" in request.url.host else "groq"
        seen.append(provider)
        return (gemini if provider == "gemini" else groq)(request)

    return handler, seen


async def test_gemini_answers_when_healthy() -> None:
    handler, seen = router(lambda r: gemini_ok(GOOD), lambda r: pytest.fail("groq called"))
    llm = LLM(SETTINGS, httpx.MockTransport(handler))
    assert (await llm.json(Intake, "parse this")).artist == "Hovvdy"
    assert seen == ["gemini"] and llm.calls[0].model_version == "gemini-3.8-flash"


async def test_503_tries_lite_then_groq_and_opens_breakers() -> None:
    handler, seen = router(lambda r: httpx.Response(503, json={"error": {"message": "high demand"}}), lambda r: groq_ok(GOOD))
    llm = LLM(SETTINGS, httpx.MockTransport(handler))
    assert (await llm.json(Intake, "x")).n_shows == 6
    assert seen == ["gemini", "gemini", "groq"]
    assert "high demand" in llm.calls[0].error
    await llm.json(Intake, "again")  # breaker open: straight to Groq, no waiting on Gemini
    assert seen[3:] == ["groq"]


async def test_timeout_falls_back() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    handler, seen = router(slow, lambda r: groq_ok(GOOD))
    llm = LLM(SETTINGS, httpx.MockTransport(handler))
    await llm.json(Intake, "x")
    assert seen == ["gemini", "gemini", "groq"] and "timeout" in llm.calls[0].error


async def test_invalid_json_from_gemini_goes_to_groq() -> None:
    handler, seen = router(lambda r: gemini_ok({"artist": "Hovvdy"}), lambda r: groq_ok(GOOD))
    llm = LLM(SETTINGS, httpx.MockTransport(handler))
    assert (await llm.json(Intake, "x")).n_shows == 6
    assert seen == ["gemini", "gemini", "groq"] and llm.calls[0].ok is False  # main, lite, then Groq


async def test_groq_primary_skips_gemini() -> None:
    handler, seen = router(lambda r: pytest.fail("gemini called"), lambda r: groq_ok(GOOD))
    llm = LLM(LLMSettings(gemini_key="g", groq_key="q", primary="groq"), httpx.MockTransport(handler))
    await llm.json(Intake, "x")
    assert seen == ["groq"]


async def test_images_never_go_to_groq() -> None:
    handler, seen = router(lambda r: httpx.Response(503, json={}), lambda r: pytest.fail("groq got an image"))
    llm = LLM(SETTINGS, httpx.MockTransport(handler))
    with pytest.raises(LLMUnavailable):
        await llm.json(Intake, "read screenshot", image=(b"png", "image/png"))
    assert seen == ["gemini", "gemini"]


async def test_strips_markdown_fences() -> None:
    fenced = {"candidates": [{"content": {"parts": [{"text": "```json\n" + json.dumps(GOOD) + "\n```"}]}}]}
    handler, _ = router(lambda r: httpx.Response(200, json=fenced), lambda r: pytest.fail("groq called"))
    assert (await LLM(SETTINGS, httpx.MockTransport(handler)).json(Intake, "x")).artist == "Hovvdy"


async def test_groq_429_waits_for_retry_after_once() -> None:
    answers = iter([httpx.Response(429, headers={"retry-after": "0.01"}, json={}), groq_ok(GOOD)])
    handler, seen = router(lambda r: pytest.fail("gemini called"), lambda r: next(answers))
    llm = LLM(LLMSettings(gemini_key="", groq_key="q"), httpx.MockTransport(handler))
    assert (await llm.json(Intake, "x")).artist == "Hovvdy" and seen == ["groq", "groq"]


async def test_groq_schema_rejection_retries_in_json_mode() -> None:
    bodies = []

    def groq(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return httpx.Response(400, json={"error": {"message": "Failed to validate JSON. Please adjust your prompt."}})
        return groq_ok(GOOD)

    handler, _ = router(lambda r: pytest.fail("gemini called"), groq)
    llm = LLM(LLMSettings(gemini_key="", groq_key="q"), httpx.MockTransport(handler))
    await llm.json(Intake, "x")
    assert bodies[0]["response_format"]["type"] == "json_schema" and bodies[1]["response_format"] == {"type": "json_object"}


async def test_lite_tier_never_uses_main_model() -> None:
    models = []

    def gemini(request: httpx.Request) -> httpx.Response:
        models.append(request.url.path.split("/")[-1])
        return gemini_ok(GOOD)

    handler, _ = router(gemini, lambda r: pytest.fail("groq called"))
    llm = LLM(LLMSettings(gemini_key="g", groq_key="q", gemini_main="main-m", gemini_lite="lite-m"), httpx.MockTransport(handler))
    await llm.json(Intake, "x", tier="lite")
    assert models == ["lite-m:generateContent"]
