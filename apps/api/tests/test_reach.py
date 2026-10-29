from __future__ import annotations

import base64
import json

import httpx
import pytest

from tourscout_api.agent.reach import ingest, parse_csv, parse_number, to_metros
from tourscout_api.core.config import LLMSettings
from tourscout_api.core.llm import LLM
from tourscout_mcp.geo import City, MetroIndex

pytestmark = pytest.mark.anyio

INDEX = MetroIndex([
    City("New York City", "US", "NY", 40.71, -74.01, 8_800_000),
    City("Brooklyn", "US", "NY", 40.65, -73.95, 2_600_000),
    City("Columbus", "US", "OH", 39.96, -83.00, 900_000),
])


def test_parse_number() -> None:
    assert parse_number("12,400") == 12400
    assert parse_number("12.4K") == 12400
    assert parse_number("1.2M") == 1_200_000
    assert parse_number("n/a") is None


def test_parse_csv_with_loose_headers() -> None:
    rows = parse_csv("City,Country,Listeners\nBrooklyn,US,3.1K\nColumbus,US,900\nNowhere,US,\n")
    assert rows == [{"city": "Brooklyn", "listeners": 3100}, {"city": "Columbus", "listeners": 900}]
    with pytest.raises(ValueError, match="city column"):
        parse_csv("name,value\na,1")


def test_to_metros_merges_boroughs_and_reports_unmatched() -> None:
    rows = [{"city": "Brooklyn", "listeners": 3000}, {"city": "New York", "listeners": 1000},
            {"city": "Atlantis", "listeners": 5}]
    out = to_metros(rows, ["Columbus", "El Dorado"], INDEX.find)
    assert out["listeners"] == {"New York City, NY": 3000}
    assert out["played"] == ["Columbus, OH"]
    assert out["unmatched"] == ["New York", "Atlantis", "El Dorado"]


async def test_screenshot_goes_to_gemini_as_inline_image() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen["image"] = body["contents"][0]["parts"][1]["inline_data"]
        rows = {"rows": [{"city": "Columbus", "listeners": 2500}, {"city": "Blurry", "listeners": 0}]}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(rows)}]}}]})

    llm = LLM(LLMSettings(gemini_key="g", groq_key=""), httpx.MockTransport(handler))
    png = base64.b64encode(b"\x89PNG fake").decode()
    rows, source = await ingest(llm, {"image_b64": png, "mime": "image/png"})
    assert source == "screenshot" and rows == [{"city": "Columbus", "listeners": 2500}]
    assert seen["image"]["mime_type"] == "image/png" and seen["image"]["data"] == png


async def test_ingest_without_data() -> None:
    assert await ingest(LLM(LLMSettings(gemini_key="", groq_key="")), None) == ([], "none")
