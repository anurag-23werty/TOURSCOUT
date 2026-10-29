"""Run the graph: start a plan, answer a checkpoint, or refine a finished plan, all on one thread id."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from ..core.llm import LLM
from .graph import AgentContext, build_graph
from .toolbox import Toolbox


class TourAgent:
    def __init__(self, ctx: AgentContext, checkpointer: Any = None) -> None:
        self.ctx = ctx
        # InMemorySaver for the CLI and tests; the API passes a Postgres checkpointer (Phase 4).
        self.graph = build_graph(ctx, checkpointer or InMemorySaver())

    @classmethod
    def from_env(cls, outreach: bool = True) -> "TourAgent":
        return cls(AgentContext(LLM(), Toolbox.from_env(), outreach))

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}

    async def _run(self, thread_id: str, payload: Any) -> dict[str, Any]:
        config = self._config(thread_id)
        await self.graph.ainvoke(payload, config)
        snapshot = await self.graph.aget_state(config)
        pending = [i.value for i in snapshot.interrupts] if snapshot.interrupts else []
        return {"state": snapshot.values, "interrupt": pending[0] if pending else None, "done": not snapshot.next}

    async def start(self, thread_id: str, request: str = "", intake: dict[str, Any] | None = None,
                    reach_input: dict[str, Any] | None = None, auto_approve: bool = False) -> dict[str, Any]:
        payload = {"request": request, "auto_approve": auto_approve, "reach_input": reach_input or {}}
        if intake:
            payload["intake"] = intake
        return await self._run(thread_id, payload)

    async def resume(self, thread_id: str, answer: dict[str, Any]) -> dict[str, Any]:
        return await self._run(thread_id, Command(resume=answer))

    async def refine(self, thread_id: str, request: str) -> dict[str, Any]:
        return await self._run(thread_id, {"refine_request": request})

    async def aclose(self) -> None:
        await self.ctx.llm.aclose()
        await self.ctx.tools.aclose()
