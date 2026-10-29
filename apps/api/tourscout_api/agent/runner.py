"""Run the graph: start a plan, answer a checkpoint, or refine a finished plan, all on one thread id.

`stream()` yields what the UI shows live: ("step", event) as each node finishes, then exactly one of
("interrupt", payload) | ("plan", plan) | ("error", message). The other methods wrap it for the CLI and tests.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from ..core.llm import LLM, LLMUnavailable
from ..core.tracing import Tracer
from tourscout_mcp.allowlist import ParamNotAllowed
from tourscout_mcp.qloo import QlooError
from .graph import AgentContext, build_graph
from .toolbox import Toolbox

Event = tuple[str, Any]
log = logging.getLogger("tourscout.agent")
LLM_BUSY_MESSAGE = ("The AI models behind TourScout are at their free-tier limit right now. "
                    "Please try again in a minute.")
USER_ERRORS = (ValueError, QlooError, ParamNotAllowed, LLMUnavailable)


class TourAgent:
    def __init__(self, ctx: AgentContext, checkpointer: Any = None, tracer: Tracer | None = None) -> None:
        self.ctx = ctx
        self.tracer = tracer or Tracer(None)
        # In-memory unless the caller passes a durable one (core/checkpoint.py: SQLite locally, Postgres in production).
        self.graph = build_graph(ctx, checkpointer or InMemorySaver())

    @classmethod
    def from_env(cls, outreach: bool = True, checkpointer: Any = None) -> "TourAgent":
        return cls(AgentContext(LLM(), Toolbox.from_env(), outreach), checkpointer, Tracer.from_env())

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
        kind = "resume" if isinstance(payload, Command) else "refine" if "refine_request" in payload else "start"
        trace = self.tracer.run(thread_id, kind)
        calls_before = len(self.ctx.llm.calls)
        outcome: Event = ("error", "the run stopped without a plan")
        try:
            async for chunk in self.graph.astream(payload, config, stream_mode="updates"):
                for node, update in chunk.items():
                    if node == "__interrupt__" or not isinstance(update, dict):
                        continue
                    for event in update.get("events", []):
                        trace.step(event)
                        yield "step", event
            snapshot = await self.graph.aget_state(config)
            if snapshot.interrupts:
                outcome = ("interrupt", snapshot.interrupts[0].value)
            elif snapshot.values.get("plan") and not snapshot.next:
                outcome = ("plan", snapshot.values["plan"])
        except LLMUnavailable as exc:  # provider detail goes to the logs and the trace, not to the visitor
            log.warning("LLMs unavailable for %s: %s", thread_id, exc)
            outcome = ("error", LLM_BUSY_MESSAGE)
        except USER_ERRORS as exc:
            outcome = ("error", str(exc))
        finally:
            trace.llm_calls(self.ctx.llm.usage()[calls_before:])
            await trace.finish(outcome[0], outcome[1] if outcome[0] != "plan" else {"stops": len(outcome[1]["stops"])})
        yield outcome

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

    async def delete(self, thread_id: str) -> None:
        """Forget a run entirely (its checkpoints and writes), e.g. when its owner deletes the tour."""
        await self.graph.checkpointer.adelete_thread(thread_id)

    async def aclose(self) -> None:
        await self.ctx.llm.aclose()
        await self.ctx.tools.aclose()
