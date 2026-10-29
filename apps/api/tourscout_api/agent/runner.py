"""Run the graph: start a plan, answer a checkpoint, or refine a finished plan, all on one thread id.

`stream()` yields what the UI shows live: ("step", event) as each node finishes, then exactly one of
("interrupt", payload) | ("plan", plan) | ("error", message). The other methods wrap it for the CLI and tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from ..core.llm import LLM, LLMUnavailable
from tourscout_mcp.allowlist import ParamNotAllowed
from tourscout_mcp.qloo import QlooError
from .graph import AgentContext, build_graph
from .toolbox import Toolbox

Event = tuple[str, Any]
USER_ERRORS = (ValueError, QlooError, ParamNotAllowed, LLMUnavailable)


class TourAgent:
    def __init__(self, ctx: AgentContext, checkpointer: Any = None) -> None:
        self.ctx = ctx
        # In-memory unless the caller passes a durable one (core/checkpoint.py: SQLite locally, Postgres in production).
        self.graph = build_graph(ctx, checkpointer or InMemorySaver())

    @classmethod
    def from_env(cls, outreach: bool = True, checkpointer: Any = None) -> "TourAgent":
        return cls(AgentContext(LLM(), Toolbox.from_env(), outreach), checkpointer)

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}

    @staticmethod
    def start_payload(request: str = "", intake: dict[str, Any] | None = None,
                      reach_input: dict[str, Any] | None = None, auto_approve: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {"request": request, "auto_approve": auto_approve, "reach_input": reach_input or {}}
        if intake:
            payload["intake"] = intake
        return payload

    async def stream(self, thread_id: str, payload: Any) -> AsyncIterator[Event]:
        config = self._config(thread_id)
        try:
            async for chunk in self.graph.astream(payload, config, stream_mode="updates"):
                for node, update in chunk.items():
                    if node == "__interrupt__" or not isinstance(update, dict):
                        continue
                    for event in update.get("events", []):
                        yield "step", event
        except USER_ERRORS as exc:
            yield "error", str(exc)
            return
        snapshot = await self.graph.aget_state(config)
        if snapshot.interrupts:
            yield "interrupt", snapshot.interrupts[0].value
        elif snapshot.values.get("plan") and not snapshot.next:
            yield "plan", snapshot.values["plan"]
        else:
            yield "error", "the run stopped without a plan"

    async def state(self, thread_id: str) -> dict[str, Any]:
        snapshot = await self.graph.aget_state(self._config(thread_id))
        pending = [i.value for i in snapshot.interrupts] if snapshot.interrupts else []
        return {"state": snapshot.values, "interrupt": pending[0] if pending else None,
                "done": bool(snapshot.values) and not snapshot.next}

    async def _run(self, thread_id: str, payload: Any) -> dict[str, Any]:
        async for kind, value in self.stream(thread_id, payload):
            if kind == "error":
                raise ValueError(value)
        return await self.state(thread_id)

    async def start(self, thread_id: str, request: str = "", intake: dict[str, Any] | None = None,
                    reach_input: dict[str, Any] | None = None, auto_approve: bool = False) -> dict[str, Any]:
        return await self._run(thread_id, self.start_payload(request, intake, reach_input, auto_approve))

    async def resume(self, thread_id: str, answer: dict[str, Any]) -> dict[str, Any]:
        return await self._run(thread_id, Command(resume=answer))

    async def refine(self, thread_id: str, request: str) -> dict[str, Any]:
        return await self._run(thread_id, {"refine_request": request})

    async def aclose(self) -> None:
        await self.ctx.llm.aclose()
        await self.ctx.tools.aclose()
