from __future__ import annotations

import json

import httpx
import pytest

from tourscout_api.baseline import describe, plan_baseline
from tourscout_api.core.config import LLMSettings
from tourscout_api.core.llm import LLM

pytestmark = pytest.mark.anyio


async def test_baseline_gets_no_tools_and_no_qloo_data() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen["body"] = body
        plan = {"stops": [{"city": "Chicago", "date": "2027-04-01", "venue": "Metro", "openers": ["Some Band"]}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan)}}]})

    llm = LLM(LLMSettings(gemini_key="", groq_key="q"), httpx.MockTransport(handler))
    out = await plan_baseline(llm, intake={"artist": "Hovvdy", "regions": ["Midwest"], "n_shows": 1, "past_cities": []})
    assert out["stops"][0]["venue"] == "Metro"
    assert "tools" not in seen["body"]
    assert "Hovvdy" in seen["body"]["messages"][-1]["content"]


def test_describe_drops_empty_fields() -> None:
    assert describe({"artist": "Hovvdy", "past_cities": [], "end_date": None}) == '{"artist":"Hovvdy"}'
