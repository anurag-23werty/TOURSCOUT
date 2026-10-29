"""Accounts: Neon Auth token checks, My tours, guest → account claim, rename/delete. A local Ed25519 key stands in for
Neon Auth's JWKS, so nothing here touches the network."""

from __future__ import annotations

import os
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from test_agent import FakeLLM, FakeTools
from test_api import events

from tourscout_api.agent.graph import AgentContext
from tourscout_api.agent.runner import TourAgent
from tourscout_api.api.app import create_app
from tourscout_api.api.auth import AuthError, JwtVerifier
from tourscout_api.api.plans import MemoryPlanStore, PostgresPlanStore, SQLitePlanStore
from tourscout_api.api.settings import ApiSettings

AUTH_URL = "https://ep-test.neonauth.us-east-2.aws.neon.tech/neondb/auth"
ISSUER = "https://ep-test.neonauth.us-east-2.aws.neon.tech"
KEY = Ed25519PrivateKey.generate()
HOVVDY = {"message": "I'm Hovvdy, 4 shows in the Midwest from April", "auto_approve": True}


def token(sub: str = "u1", key=KEY, **claims) -> str:  # type: ignore[no-untyped-def]
    now = int(time.time())
    body = {"sub": sub, "id": sub, "email": f"{sub}@example.com", "name": sub.upper(), "emailVerified": True,
            "role": "authenticated", "iss": ISSUER, "aud": ISSUER, "iat": now, "exp": now + 900, **claims}
    return jwt.encode(body, key, algorithm="EdDSA")


def bearer(sub: str = "u1") -> dict[str, str]:
    return {"Authorization": f"Bearer {token(sub)}"}


verifier = JwtVerifier(AUTH_URL, key_for=lambda _t: KEY.public_key())


# ------------------------------------------------------------------ token checks


@pytest.mark.anyio
async def test_a_valid_neon_token_becomes_a_user() -> None:
    user = await verifier.verify(token("abc"))
    assert (user.id, user.email, user.name, user.email_verified) == ("abc", "abc@example.com", "ABC", True)


@pytest.mark.anyio
@pytest.mark.parametrize("bad", [
    pytest.param(lambda: token(exp=int(time.time()) - 120), id="expired"),
    pytest.param(lambda: token(key=Ed25519PrivateKey.generate()), id="forged (other key)"),
    pytest.param(lambda: token(iss="https://evil.example"), id="other issuer"),
    pytest.param(lambda: token(aud="https://other-app.example"), id="other audience"),
    pytest.param(lambda: jwt.encode({"sub": "u1", "iss": ISSUER, "aud": ISSUER, "exp": int(time.time()) + 900},
                                    "s" * 32, algorithm="HS256"), id="HS256 instead of EdDSA"),
    pytest.param(lambda: token(banned=True), id="banned"),
    pytest.param(lambda: "not.a.jwt", id="garbage"),
])
async def test_bad_tokens_are_rejected(bad) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(AuthError):
        await verifier.verify(bad())


def test_issuer_is_the_auth_url_origin() -> None:
    v = JwtVerifier(AUTH_URL + "/", key_for=lambda _t: None)
    assert v.issuer == ISSUER


# ------------------------------------------------------------------ API


@pytest.fixture
def app_client():  # type: ignore[no-untyped-def]
    agent = TourAgent(AgentContext(FakeLLM(), FakeTools()))  # type: ignore[arg-type]
    settings = ApiSettings(plans_per_ip_per_hour=50, plans_per_day=200)
    with TestClient(create_app(agent, settings, mount_mcp=False, verifier=verifier)) as c:
        yield c


def plan(c: TestClient, headers: dict[str, str]) -> str:
    ev = events(c.post("/api/plans", json=HOVVDY, headers=headers))
    assert ev[-1][0] == "plan", ev[-1]
    return ev[0][1]["thread_id"]


def test_signed_in_user_plans_and_sees_them_in_my_tours(app_client) -> None:  # type: ignore[no-untyped-def]
    me = app_client.get("/api/me", headers=bearer("u1")).json()
    assert me["signed_in"] and me["user"]["email"] == "u1@example.com" and me["sign_in_enabled"]

    thread = plan(app_client, bearer("u1"))
    rows = app_client.get("/api/me/plans", headers=bearer("u1")).json()
    assert [r["thread_id"] for r in rows] == [thread]
    assert rows[0]["artist"] == "Hovvdy" and rows[0]["headline"] and "owner" not in rows[0]
    assert app_client.get(f"/api/plans/{thread}", headers=bearer("u1")).json()["status"] == "done"


def test_other_users_and_guests_cannot_see_or_touch_a_users_plan(app_client) -> None:  # type: ignore[no-untyped-def]
    thread = plan(app_client, bearer("u1"))
    guest = {"X-Session-Id": app_client.post("/api/sessions").json()["session_id"]}
    for who in (bearer("u2"), guest):
        assert app_client.get(f"/api/plans/{thread}", headers=who).status_code == 404
        assert app_client.delete(f"/api/plans/{thread}", headers=who).status_code == 404
        assert app_client.patch(f"/api/plans/{thread}", json={"title": "mine"}, headers=who).status_code == 404
        assert app_client.get(f"/api/plans/{thread}/export.csv", headers=who).status_code == 404
    assert app_client.get("/api/me/plans", headers=bearer("u2")).json() == []


def test_bad_or_expired_tokens_get_401_not_guest_access(app_client) -> None:  # type: ignore[no-untyped-def]
    expired = {"Authorization": f"Bearer {token(exp=int(time.time()) - 120)}"}
    for h in (expired, {"Authorization": "Bearer junk"}, {"Authorization": "Basic dTpw"}):
        r = app_client.get("/api/me/plans", headers=h)
        assert r.status_code == 401, h


def test_guest_plans_move_to_the_account_on_sign_in(app_client) -> None:  # type: ignore[no-untyped-def]
    sid = app_client.post("/api/sessions").json()["session_id"]
    thread = plan(app_client, {"X-Session-Id": sid})
    assert app_client.post("/api/me/claim", json={"session_id": sid}, headers=bearer("u1")).json() == {"moved": 1}
    assert [r["thread_id"] for r in app_client.get("/api/me/plans", headers=bearer("u1")).json()] == [thread]
    assert app_client.get(f"/api/plans/{thread}", headers={"X-Session-Id": sid}).status_code == 404  # no longer the guest's
    # Claiming needs a signed-in user, and an unknown session moves nothing.
    assert app_client.post("/api/me/claim", json={"session_id": sid}, headers={"X-Session-Id": sid}).status_code == 401
    assert app_client.post("/api/me/claim", json={"session_id": "unknown-session"}, headers=bearer("u1")).json() == {"moved": 0}


def test_rename_and_delete_a_tour(app_client) -> None:  # type: ignore[no-untyped-def]
    thread = plan(app_client, bearer("u1"))
    assert app_client.patch(f"/api/plans/{thread}", json={"title": " Spring run "}, headers=bearer("u1")).status_code == 200
    assert app_client.get("/api/me/plans", headers=bearer("u1")).json()[0]["title"] == "Spring run"

    assert app_client.delete(f"/api/plans/{thread}", headers=bearer("u1")).status_code == 204
    assert app_client.get("/api/me/plans", headers=bearer("u1")).json() == []
    assert app_client.get(f"/api/plans/{thread}", headers=bearer("u1")).status_code == 404


def test_delete_all_my_tours_removes_the_saved_runs(app_client) -> None:  # type: ignore[no-untyped-def]
    threads = [plan(app_client, bearer("u1")) for _ in range(2)]
    agent = app_client.app.state.agent
    assert all(app_client.portal.call(agent.state, t)["state"].get("plan") for t in threads)  # saved before…
    assert app_client.delete("/api/me/plans", headers=bearer("u1")).json() == {"deleted": 2}
    for t in threads:
        assert app_client.portal.call(agent.state, t)["state"] == {}  # checkpoints gone, not just the index


def test_guests_still_work_and_sign_in_off_is_explicit() -> None:
    agent = TourAgent(AgentContext(FakeLLM(), FakeTools()))  # type: ignore[arg-type]
    with TestClient(create_app(agent, ApiSettings(), mount_mcp=False)) as c:  # no verifier: guests only
        sid = {"X-Session-Id": c.post("/api/sessions").json()["session_id"]}
        assert c.get("/api/me", headers=sid).json() == {"signed_in": False, "sign_in_enabled": False, "user": None}
        plan(c, sid)
        assert len(c.get("/api/me/plans", headers=sid).json()) == 1
        r = c.get("/api/me/plans", headers=bearer("u1"))
        assert r.status_code == 401 and "guest" in r.json()["detail"]


def test_signed_in_users_are_limited_per_account_not_per_ip() -> None:
    agent = TourAgent(AgentContext(FakeLLM(), FakeTools()))  # type: ignore[arg-type]
    settings = ApiSettings(plans_per_ip_per_hour=1, plans_per_user_per_hour=2, plans_per_day=50)
    with TestClient(create_app(agent, settings, mount_mcp=False, verifier=verifier)) as c:
        plan(c, bearer("u1")), plan(c, bearer("u1"))  # 2 > the per-IP limit of 1: same IP, but counted per account
        assert c.post("/api/plans", json=HOVVDY, headers=bearer("u1")).status_code == 429
        plan(c, bearer("u2"))  # a classmate on the same network isn't blocked


# ------------------------------------------------------------------ plan stores


async def exercise(store) -> None:  # type: ignore[no-untyped-def]
    a, b = f"t-{uuid.uuid4().hex[:8]}", f"t-{uuid.uuid4().hex[:8]}"
    owner, guest = f"user:{uuid.uuid4().hex[:6]}", f"guest:{uuid.uuid4().hex[:6]}"
    await store.add(a, owner)
    await store.add(b, guest)
    await store.update(a, artist="Hovvdy", headline="Spring", owner="user:hacker")  # owner isn't editable
    assert await store.owner_of(a) == owner and await store.owner_of("nope") is None
    assert [(r.thread_id, r.artist, r.headline) for r in await store.list_for(owner)] == [(a, "Hovvdy", "Spring")]
    assert await store.transfer(guest, owner) == 1
    assert {r.thread_id for r in await store.list_for(owner)} == {a, b}
    await store.delete(a)
    assert [r.thread_id for r in await store.list_for(owner)] == [b]
    await store.delete(b)


@pytest.mark.anyio
async def test_memory_and_sqlite_plan_stores(tmp_path) -> None:  # type: ignore[no-untyped-def]
    await exercise(MemoryPlanStore())
    await exercise(SQLitePlanStore(tmp_path / "plans.sqlite"))


@pytest.mark.anyio
@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="set TEST_POSTGRES_URL to test against Postgres")
async def test_postgres_plan_store() -> None:
    store = PostgresPlanStore(os.environ["TEST_POSTGRES_URL"])
    try:
        await exercise(store)
    finally:
        await store.aclose()
