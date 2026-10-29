"""TourScout HTTP API.

    uv run tourscout-api                 # http://127.0.0.1:8000  (docs at /docs)

Flow for the web app:
    POST /api/sessions                          → {session_id}          (send it as X-Session-Id afterwards)
    POST /api/upload            (optional)      → {upload_id, preview}
    POST /api/plans                             → SSE: thread, step…, then interrupt | plan | error
    POST /api/plans/{id}/resume  {answer}       → SSE (answer a checkpoint)
    POST /api/plans/{id}/refine  {message}      → SSE ("skip Detroit")
    GET  /api/plans/{id}                        → current state
    POST /api/plans/{id}/compare                → LLM-only baseline for the same request
    POST /api/plans/{id}/outreach               → sponsor pitch / opener DM on demand
    GET  /api/plans/{id}/export.csv | .ics
    PATCH /api/plans/{id} {title}  · DELETE /api/plans/{id}
    GET  /api/me · GET /api/me/plans · POST /api/me/claim {session_id} · DELETE /api/me/plans

Who is asking: a signed-in user sends `Authorization: Bearer <Neon Auth JWT>`, a guest sends `X-Session-Id`.
    /mcp                                        → the TourScout MCP server (streamable HTTP)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

import anyio
import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from langgraph.types import Command
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

from .. import personas
from ..agent.outputs import opener_dm, sponsor_pitch, to_csv, to_ics
from ..agent.runner import TourAgent
from ..baseline import plan_baseline
from ..core import checkpoint
from ..core.llm import LLMUnavailable
from .auth import AccountDeleter, AuthError, JwtVerifier, User
from .plans import PlanStore, make_plan_store
from .ratelimit import Limiter
from .sessions import Session, SessionStore
from .settings import ApiSettings
from .uploads import UploadError, UploadStore

log = logging.getLogger("tourscout.api")


async def with_heartbeat(events: AsyncIterator[str], every_s: float) -> AsyncIterator[str]:
    """Pass SSE chunks through, adding a ": ping" comment whenever nothing was sent for every_s seconds.

    A cold-cache fan-out can be silent for a minute, and proxies on the way cut idle connections (seen on the live
    prewarm). Browsers and our client ignore comment lines. The pending chunk is awaited, never cancelled, on a ping.
    """
    it = events.__aiter__()
    pending: asyncio.Future[str] | None = None
    try:
        while True:
            pending = pending or asyncio.ensure_future(it.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=every_s)
            if not done:
                yield ": ping\n\n"
                continue
            try:
                chunk = pending.result()
            except StopAsyncIteration:
                return
            pending = None
            yield chunk
    finally:
        if pending and not pending.done():
            pending.cancel()  # the visitor left mid-run: stop the agent too


# ---------------------------------------------------------------- request bodies


class PlanRequest(BaseModel):
    message: str = Field("", max_length=2000, description="free-text request, e.g. 'I'm Hovvdy, 8 shows in the Midwest'")
    persona_id: str | None = Field(None, description="a demo persona instead of free text")
    upload_id: str | None = Field(None, description="from POST /api/upload: listener data")
    auto_approve: bool = Field(False, description="skip the two checkpoints")


class ResumeRequest(BaseModel):
    answer: dict[str, Any] = Field(description='{"choice": id} | {"choice": null, "sounds_like": [...]} | {"selected": [...]}')


class RefineRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)


class RenameRequest(BaseModel):
    title: str = Field(max_length=120)


class ClaimRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64, description="the guest session whose plans move to this account")


@dataclass(frozen=True)
class Owner:
    """Whoever is calling: a signed-in user or a guest session. `key` is what the plans table stores."""

    key: str
    user: User | None = None
    session: Session | None = None


class OutreachRequest(BaseModel):
    kind: Literal["sponsor", "opener"]
    brand_id: str | None = None
    metro: str | None = None


# ---------------------------------------------------------------- app


def create_app(agent: TourAgent | None = None, settings: ApiSettings | None = None, mount_mcp: bool = True,
               plan_store: PlanStore | None = None, verifier: JwtVerifier | None = None,
               deleter: AccountDeleter | None = None) -> FastAPI:
    """Tests inject the agent, a memory plan store and a verifier with a local key; production reads the env."""
    settings = settings or ApiSettings()
    if plan_store is None:
        from .plans import MemoryPlanStore

        plan_store = MemoryPlanStore() if agent is not None else make_plan_store()
    plans: PlanStore = plan_store
    if verifier is None and agent is None:
        verifier = JwtVerifier.from_env()
    if deleter is None and agent is None:
        deleter = AccountDeleter.from_env()
    sessions = SessionStore(settings.session_ttl_s)
    uploads = UploadStore(settings.upload_max_bytes, settings.upload_ttl_s)
    limiter = Limiter(
        {"plan": (settings.plans_per_ip_per_hour, 3600), "llm": (settings.llm_actions_per_ip_per_hour, 3600),
         "plan_user": (settings.plans_per_user_per_hour, 3600), "llm_user": (settings.llm_actions_per_user_per_hour, 3600),
         "upload": (settings.uploads_per_ip_per_hour, 3600), "mcp": (120, 3600)},
        {"plan": settings.plans_per_day},
    )
    running = anyio.Semaphore(settings.concurrent_plans)
    mcp_server = None
    if mount_mcp:
        from tourscout_mcp.server import mcp as mcp_server

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            if agent is None:
                saver = await stack.enter_async_context(checkpoint.open_checkpointer())
                app.state.agent = TourAgent.from_env(checkpointer=saver)
                stack.push_async_callback(app.state.agent.aclose)
                log.info("checkpointer: %s", checkpoint.describe(None))
            else:
                app.state.agent = agent
            if mcp_server is not None:
                await stack.enter_async_context(mcp_server.session_manager.run())
            if aclose := getattr(plans, "aclose", None):
                stack.push_async_callback(aclose)
            log.info("sign-in: %s", "Neon Auth" if verifier else "off (guests only)")
            yield

    app = FastAPI(title="TourScout API", version="0.1.0", lifespan=lifespan,
                  description="Tour planning for independent musicians, grounded in Qloo taste data.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.web_origins,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"],
                       allow_headers=["Content-Type", "X-Session-Id", "Authorization"], expose_headers=["Retry-After"])

    # ------------------------------------------------------------ helpers

    def client_ip(request: Request) -> str:
        if settings.trust_proxy and (fwd := request.headers.get("x-forwarded-for")):
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def limit(name: str, request: Request, owner: Owner | None = None) -> None:
        # Signed-in users are limited per account (their own, larger window); guests per IP.
        if owner is not None and owner.user is not None:
            decision = limiter.check(name, owner.key, window=f"{name}_user")
        else:
            decision = limiter.check(name, client_ip(request))
        if not decision.allowed:
            raise HTTPException(429, decision.reason, headers={"Retry-After": str(decision.retry_after_s)})

    def session_dep(x_session_id: str | None = Header(None)) -> Session:
        session = sessions.get(x_session_id)
        if session is None:
            raise HTTPException(401, "missing or expired session: POST /api/sessions first")
        return session

    async def owner_dep(authorization: str | None = Header(None), x_session_id: str | None = Header(None)) -> Owner:
        if authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                raise HTTPException(401, "send the sign-in token as 'Authorization: Bearer <token>'")
            if verifier is None:
                raise HTTPException(401, "sign-in isn't enabled on this server; continue as a guest")
            try:
                user = await verifier.verify(token)
            except AuthError as exc:
                log.info("rejected token: %s", exc)
                raise HTTPException(401, "your sign-in has expired; please sign in again") from None
            return Owner(f"user:{user.id}", user=user)
        session = session_dep(x_session_id)
        return Owner(f"guest:{session.id}", session=session)

    def user_dep(owner: Owner = Depends(owner_dep)) -> Owner:
        if owner.user is None:
            raise HTTPException(401, "sign in to do this")
        return owner

    async def owned(owner: Owner, thread_id: str) -> str:
        # Same 404 for "doesn't exist" and "someone else's", so plan ids can't be probed.
        if await plans.owner_of(thread_id) != owner.key:
            raise HTTPException(404, "no such plan in your tours")
        return thread_id

    def agent_of(request: Request) -> TourAgent:
        return request.app.state.agent

    def sse(kind: str, data: Any) -> str:
        return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

    def stream(agent_: TourAgent, thread_id: str, payload: Any) -> StreamingResponse:
        async def body() -> AsyncIterator[str]:
            yield sse("thread", {"thread_id": thread_id})
            try:
                running.acquire_nowait()
            except anyio.WouldBlock:
                # Queue instead of turning people away (Phase 7 drill: 7 of 10 simultaneous visitors were rejected).
                yield sse("step", {"node": "queue", "message": "Other tours are being planned; you're in line"})
                with anyio.move_on_after(settings.queue_timeout_s) as wait:
                    await running.acquire()
                if wait.cancelled_caught:
                    yield sse("error", {"message": "TourScout is very busy right now; please try again in a few minutes"})
                    return
            try:
                async for kind, value in agent_.stream(thread_id, payload):
                    if kind == "plan" and isinstance(value, dict):
                        await plans.update(thread_id, artist=str(value.get("artist") or ""),
                                           headline=str(value.get("headline") or ""))
                    yield sse(kind, value if kind != "error" else {"message": value})
            except Exception:  # never leak a stack trace to the browser
                log.exception("plan %s failed", thread_id)
                yield sse("error", {"message": "something went wrong on our side; please try again"})
            finally:
                running.release()

        return StreamingResponse(with_heartbeat(body(), settings.heartbeat_s), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def plan_of(agent_: TourAgent, thread_id: str) -> dict[str, Any]:
        state = await agent_.state(thread_id)
        plan = state["state"].get("plan")
        if not plan:
            raise HTTPException(409, "this plan isn't finished yet")
        return {"plan": plan, "state": state["state"]}

    # ------------------------------------------------------------ routes

    @app.get("/health")
    async def health(request: Request) -> dict[str, Any]:
        agent_ = agent_of(request)
        deps = getattr(agent_.ctx.tools, "deps", None)
        llm = agent_.ctx.llm.s
        return {
            "ok": True,
            "checks": {
                "qloo_key": bool(getattr(getattr(deps, "qloo", None), "http", None)) if deps else True,
                "geonames": bool(getattr(deps, "metros", None)) if deps else True,
                "gemini_key": bool(llm.gemini_key),
                "groq_key": bool(llm.groq_key),
            },
            "checkpointer": checkpoint.describe(None) if agent is None else "injected",
        }

    @app.post("/api/sessions", status_code=201)
    async def new_session() -> dict[str, Any]:
        session = sessions.create()
        return {"session_id": session.id, "expires_in_s": settings.session_ttl_s}

    @app.get("/api/personas")
    async def list_personas() -> list[dict[str, Any]]:
        rows = [personas.summary(p) for p in personas.all_personas().values()]
        return sorted(rows, key=lambda p: (not p["featured"], personas.FEATURED.index(p["id"]) if p["featured"] else 0))

    @app.post("/api/upload", status_code=201)
    async def upload(request: Request, file: UploadFile = File(...), owner: Owner = Depends(owner_dep)) -> dict[str, Any]:
        limit("upload", request, owner)
        data = await file.read(settings.upload_max_bytes + 1)
        try:
            item, preview = uploads.add(data, file.filename or "", owner.key)
        except ValueError as exc:  # UploadError or a CSV parse error
            raise HTTPException(422, str(exc)) from None
        return {"upload_id": item.id, "preview": preview}

    @app.post("/api/plans")
    async def start_plan(body: PlanRequest, request: Request, owner: Owner = Depends(owner_dep)) -> StreamingResponse:
        intake, reach_input = None, {}
        if body.persona_id:
            try:
                intake, reach_input = personas.load(body.persona_id)
            except KeyError:
                raise HTTPException(404, f"unknown persona {body.persona_id}") from None
        elif len(body.message.strip()) < 10:
            raise HTTPException(422, "describe the tour (artist, region, number of shows) or pick a demo artist")
        if body.upload_id:
            try:
                reach_input = uploads.take(body.upload_id, owner.key)
            except UploadError as exc:
                raise HTTPException(422, str(exc)) from None
        limit("plan", request, owner)
        thread_id = secrets.token_hex(8)
        await plans.add(thread_id, owner.key)
        payload = TourAgent.start_payload(body.message, intake, reach_input, body.auto_approve)
        return stream(agent_of(request), thread_id, payload)

    @app.post("/api/plans/{thread_id}/resume")
    async def resume(thread_id: str, body: ResumeRequest, request: Request,
                     owner: Owner = Depends(owner_dep)) -> StreamingResponse:
        await owned(owner, thread_id)
        agent_ = agent_of(request)
        if not (await agent_.state(thread_id))["interrupt"]:
            raise HTTPException(409, "this plan isn't waiting for an answer")
        limit("llm", request, owner)
        # LangGraph treats an empty resume value as "no answer"; always send something.
        return stream(agent_, thread_id, Command(resume=body.answer or {"accept": True}))

    @app.post("/api/plans/{thread_id}/refine")
    async def refine(thread_id: str, body: RefineRequest, request: Request,
                     owner: Owner = Depends(owner_dep)) -> StreamingResponse:
        await owned(owner, thread_id)
        agent_ = agent_of(request)
        await plan_of(agent_, thread_id)
        limit("llm", request, owner)
        return stream(agent_, thread_id, {"refine_request": body.message})

    @app.get("/api/plans/{thread_id}")
    async def get_plan(thread_id: str, request: Request, owner: Owner = Depends(owner_dep)) -> dict[str, Any]:
        await owned(owner, thread_id)
        state = await agent_of(request).state(thread_id)
        values = state["state"]
        return {
            "thread_id": thread_id,
            "status": "done" if values.get("plan") and state["done"] else "waiting" if state["interrupt"] else "running",
            "interrupt": state["interrupt"],
            "plan": values.get("plan"),
            "metros": values.get("metros", [])[:40],
            "events": values.get("events", []),
            "llm_calls": values.get("llm_calls", []),
        }

    @app.post("/api/plans/{thread_id}/compare")
    async def compare(thread_id: str, request: Request, owner: Owner = Depends(owner_dep)) -> dict[str, Any]:
        await owned(owner, thread_id)
        agent_ = agent_of(request)
        done = await plan_of(agent_, thread_id)
        limit("llm", request, owner)
        try:
            baseline = await plan_baseline(agent_.ctx.llm, intake=done["state"]["intake"])
        except LLMUnavailable as exc:
            raise HTTPException(503, f"the language model is unavailable: {exc}") from None
        return {"tourscout": done["plan"], "llm_only": baseline}

    @app.post("/api/plans/{thread_id}/outreach")
    async def outreach(thread_id: str, body: OutreachRequest, request: Request,
                       owner: Owner = Depends(owner_dep)) -> dict[str, Any]:
        await owned(owner, thread_id)
        agent_ = agent_of(request)
        done = await plan_of(agent_, thread_id)
        limit("llm", request, owner)
        try:
            if body.kind == "sponsor":
                if not body.brand_id:
                    raise HTTPException(422, "brand_id is required for a sponsor pitch")
                msg = await sponsor_pitch(agent_.ctx.llm, done["plan"], body.brand_id,
                                          done["state"].get("national_sponsors", []))
            else:
                if not body.metro:
                    raise HTTPException(422, "metro is required for an opener DM")
                msg = await opener_dm(agent_.ctx.llm, done["plan"], body.metro)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None
        except LLMUnavailable as exc:
            raise HTTPException(503, f"the language model is unavailable: {exc}") from None
        return msg.model_dump()

    @app.get("/api/plans/{thread_id}/export.{fmt}")
    async def export(thread_id: str, fmt: Literal["csv", "ics"], request: Request, session_id: str | None = None,
                     authorization: str | None = Header(None), x_session_id: str | None = Header(None)) -> PlainTextResponse:
        # Guests may pass ?session_id= so a plain <a href download> works; signed-in users fetch with their token.
        owner = await owner_dep(authorization, x_session_id or session_id)
        await owned(owner, thread_id)
        plan = (await plan_of(agent_of(request), thread_id))["plan"]
        name = f"tourscout-{(plan.get('artist') or 'tour').lower().replace(' ', '-')}.{fmt}"
        body, media = (to_csv(plan), "text/csv") if fmt == "csv" else (to_ics(plan), "text/calendar")
        return PlainTextResponse(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.patch("/api/plans/{thread_id}")
    async def rename_plan(thread_id: str, body: RenameRequest, owner: Owner = Depends(owner_dep)) -> dict[str, Any]:
        await owned(owner, thread_id)
        await plans.update(thread_id, title=body.title.strip())
        return {"thread_id": thread_id, "title": body.title.strip()}

    @app.delete("/api/plans/{thread_id}", status_code=204)
    async def delete_plan(thread_id: str, request: Request, owner: Owner = Depends(owner_dep)) -> None:
        await owned(owner, thread_id)
        await agent_of(request).delete(thread_id)
        await plans.delete(thread_id)

    @app.get("/api/me")
    async def me(owner: Owner = Depends(owner_dep)) -> dict[str, Any]:
        u = owner.user
        return {"signed_in": u is not None, "sign_in_enabled": verifier is not None,
                "user": {"id": u.id, "email": u.email, "name": u.name, "email_verified": u.email_verified} if u else None}

    @app.get("/api/me/plans")
    async def my_plans(owner: Owner = Depends(owner_dep)) -> list[dict[str, Any]]:
        return [row.public() for row in await plans.list_for(owner.key)]

    @app.post("/api/me/claim")
    async def claim(body: ClaimRequest, owner: Owner = Depends(user_dep)) -> dict[str, Any]:
        """After sign-in: move the tours this browser planned as a guest into the account."""
        if sessions.get(body.session_id) is None:
            return {"moved": 0}  # expired or unknown: nothing to move (no error, the web app calls this blindly)
        return {"moved": await plans.transfer(f"guest:{body.session_id}", owner.key)}

    async def delete_tours_of(request: Request, owner: Owner) -> int:
        rows = await plans.list_for(owner.key, limit=10_000)
        for row in rows:
            await agent_of(request).delete(row.thread_id)
            await plans.delete(row.thread_id)
        return len(rows)

    @app.delete("/api/me/plans")
    async def delete_my_plans(request: Request, owner: Owner = Depends(user_dep)) -> dict[str, Any]:
        """Every tour of this account and its saved run; the account stays."""
        return {"deleted": await delete_tours_of(request, owner)}

    @app.delete("/api/me")
    async def delete_account(request: Request, owner: Owner = Depends(user_dep)) -> dict[str, Any]:
        """Delete the account: tours first (they're ours), then the login in Neon Auth."""
        deleted = await delete_tours_of(request, owner)
        if deleter is None:
            log.warning("account deletion for %s: NEON_API_KEY/NEON_PROJECT_ID/NEON_BRANCH_ID not set", owner.key)
            return {"deleted": deleted, "login_deleted": False}
        try:
            await deleter.delete(owner.user.id)  # type: ignore[union-attr]
        except (httpx.HTTPError, RuntimeError):
            log.exception("couldn't delete login %s in Neon Auth", owner.key)
            raise HTTPException(502, "your tours are deleted, but removing the login failed; please try again") from None
        return {"deleted": deleted, "login_deleted": True}

    if mcp_server is not None:
        local = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
        mcp_app = mcp_server.streamable_http_app(transport_security=TransportSecuritySettings(
            allowed_hosts=[*local, "127.0.0.1", "localhost", *settings.mcp_hosts],
            allowed_origins=[f"http://{h}" for h in local] + settings.web_origins))

        @app.middleware("http")
        async def limit_mcp(request: Request, call_next):  # type: ignore[no-untyped-def]
            if request.url.path.startswith("/mcp"):
                decision = limiter.check("mcp", client_ip(request))
                if not decision.allowed:
                    return JSONResponse({"detail": decision.reason}, status_code=429,
                                        headers={"Retry-After": str(decision.retry_after_s)})
            return await call_next(request)

        app.mount("/", mcp_app)  # serves /mcp; mounted last so the API routes above match first

    return app


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the TourScout API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("tourscout_api.api.app:create_app", factory=True, host=args.host, port=args.port, reload=args.reload)
