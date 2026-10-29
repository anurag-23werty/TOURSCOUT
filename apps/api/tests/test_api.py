"""HTTP tests: the real FastAPI app with the fake toolbox + fake LLM from test_agent (synthetic data only)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from test_agent import FakeLLM, FakeTools

from tourscout_api.agent.graph import AgentContext
from tourscout_api.agent.runner import TourAgent
from tourscout_api.api.app import create_app
from tourscout_api.api.settings import ApiSettings


def events(resp) -> list[tuple[str, dict]]:  # type: ignore[no-untyped-def]
    out = []
    for block in resp.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.fixture
def client():  # type: ignore[no-untyped-def]
    agent = TourAgent(AgentContext(FakeLLM(), FakeTools()))  # type: ignore[arg-type]
    settings = ApiSettings(plans_per_ip_per_hour=3, plans_per_day=50)
    with TestClient(create_app(agent, settings, mount_mcp=False)) as c:
        sid = c.post("/api/sessions").json()["session_id"]
        c.headers["X-Session-Id"] = sid
        yield c


HOVVDY_TEXT = "I'm Hovvdy, 4 shows in the Midwest from April"


def test_health_and_personas(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/health").json()["ok"] is True
    rows = client.get("/api/personas").json()
    assert [r["id"] for r in rows[:3]] == ["us-02", "nq-02", "us-01"] and rows[0]["featured"]


def test_session_required(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/plans", json={"message": HOVVDY_TEXT}, headers={"X-Session-Id": "nope"})
    assert r.status_code == 401


def test_full_flow_over_http_with_checkpoints(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/plans", json={"message": HOVVDY_TEXT})
    assert r.headers["content-type"].startswith("text/event-stream")
    ev = events(r)
    thread = ev[0][1]["thread_id"]
    assert ev[0][0] == "thread" and [k for k, _ in ev[1:]] == ["step", "step", "interrupt"]
    assert ev[-1][1]["type"] == "confirm_artist"

    ev = events(client.post(f"/api/plans/{thread}/resume", json={"answer": {"choice": "HV"}}))
    assert ev[-1][0] == "interrupt" and ev[-1][1]["type"] == "pick_cities"
    ev = events(client.post(f"/api/plans/{thread}/resume", json={"answer": {}}))  # {} = accept the suggestion
    assert ev[-1][0] == "plan" and len(ev[-1][1]["stops"]) == 4

    state = client.get(f"/api/plans/{thread}").json()
    assert state["status"] == "done" and state["plan"]["composed_by"] == "llm" and state["events"]

    csv = client.get(f"/api/plans/{thread}/export.csv")
    assert csv.status_code == 200 and csv.text.startswith("date,city") and "attachment" in csv.headers["content-disposition"]
    sid = client.headers["X-Session-Id"]
    ics = client.get(f"/api/plans/{thread}/export.ics?session_id={sid}", headers={"X-Session-Id": ""})
    assert ics.text.startswith("BEGIN:VCALENDAR")

    ev = events(client.post(f"/api/plans/{thread}/refine", json={"message": "skip Detroit"}))
    assert ev[-1][0] == "plan" and "Detroit, MI" not in [s["metro"] for s in ev[-1][1]["stops"]]

    dm = client.post(f"/api/plans/{thread}/outreach", json={"kind": "opener", "metro": ev[-1][1]["stops"][0]["metro"]})
    assert dm.status_code == 200 and dm.json()["body"]


def test_persona_and_csv_upload(client) -> None:  # type: ignore[no-untyped-def]
    up = client.post("/api/upload", files={"file": ("top.csv", b"City,Listeners\nChicago,12000\n", "text/csv")})
    assert up.status_code == 201 and up.json()["preview"]["rows"][0]["city"] == "Chicago"
    r = client.post("/api/plans", json={"persona_id": "us-02", "upload_id": up.json()["upload_id"], "auto_approve": True})
    assert events(r)[-1][0] == "plan"
    again = client.post("/api/plans", json={"persona_id": "us-02", "upload_id": up.json()["upload_id"]})
    assert again.status_code == 422  # uploads are single-use


def test_bad_inputs(client) -> None:  # type: ignore[no-untyped-def]
    assert client.post("/api/plans", json={"message": "hi"}).status_code == 422
    assert client.post("/api/plans", json={"persona_id": "zz-99"}).status_code == 404
    bad = client.post("/api/upload", files={"file": ("x.pdf", b"%PDF-1.7", "application/pdf")})
    assert bad.status_code == 422 and "PNG" in bad.json()["detail"]
    other = TestClient(client.app)
    other.headers["X-Session-Id"] = other.post("/api/sessions").json()["session_id"]
    thread = events(client.post("/api/plans", json={"message": HOVVDY_TEXT}))[0][1]["thread_id"]
    assert other.get(f"/api/plans/{thread}").status_code == 404  # another session can't read it
    assert client.post(f"/api/plans/{thread}/refine", json={"message": "skip Detroit"}).status_code == 409  # not finished


def test_rate_limit_returns_429_with_retry_after(client) -> None:  # type: ignore[no-untyped-def]
    for _ in range(3):
        assert client.post("/api/plans", json={"message": HOVVDY_TEXT}).status_code == 200
    r = client.post("/api/plans", json={"message": HOVVDY_TEXT})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_busy_server_queues_then_gives_a_clear_message() -> None:
    agent = TourAgent(AgentContext(FakeLLM(), FakeTools()))  # type: ignore[arg-type]
    settings = ApiSettings(concurrent_plans=0, queue_timeout_s=0.05)  # no free slot ever: the queue times out
    with TestClient(create_app(agent, settings, mount_mcp=False)) as c:
        c.headers["X-Session-Id"] = c.post("/api/sessions").json()["session_id"]
        ev = events(c.post("/api/plans", json={"message": HOVVDY_TEXT}))
    assert [k for k, _ in ev] == ["thread", "step", "error"]
    assert ev[1][1]["node"] == "queue" and "very busy" in ev[2][1]["message"]


def test_web_origins_ignore_spaces_and_trailing_slashes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("WEB_ORIGINS", "https://tourscout.vercel.app/ , http://localhost:5173")
    assert ApiSettings().web_origins == ["https://tourscout.vercel.app", "http://localhost:5173"]
