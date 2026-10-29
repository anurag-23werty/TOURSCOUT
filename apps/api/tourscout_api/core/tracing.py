"""Langfuse traces: one per plan run (start, checkpoint answer or refine), a span per agent step, a generation per LLM call.

Off unless LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set. Traces get step messages, models, latencies and errors;
never uploaded files, and never raw Qloo responses (Qloo terms).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anyio

log = logging.getLogger("tourscout.tracing")


class Tracer:
    def __init__(self, client: Any = None) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> "Tracer":
        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            return cls(None)
        try:
            from langfuse import Langfuse

            return cls(Langfuse(base_url=os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com",
                                environment=os.getenv("TOURSCOUT_ENV", "development")))
        except Exception:  # tracing must never break planning
            log.exception("Langfuse disabled")
            return cls(None)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def run(self, thread_id: str, kind: str) -> "RunTrace":
        return RunTrace(self, thread_id, kind)


class RunTrace:
    def __init__(self, tracer: Tracer, thread_id: str, kind: str) -> None:
        self.tracer, self.root = tracer, None
        if tracer.enabled:
            try:
                self.root = tracer.client.start_observation(
                    name=f"tour-plan:{kind}", as_type="agent", input={"thread_id": thread_id, "kind": kind},
                    metadata={"thread_id": thread_id})
            except Exception:
                log.exception("trace start failed")

    def step(self, event: dict[str, Any]) -> None:
        if self.root is None:
            return
        try:
            self.root.start_observation(name=event.get("node", "step"), as_type="span",
                                        output=event.get("message")).end()
        except Exception:
            log.exception("trace step failed")

    def llm_calls(self, calls: list[dict[str, Any]]) -> None:
        if self.root is None:
            return
        for call in calls:
            try:
                self.root.start_observation(
                    name=call.get("purpose") or "llm", as_type="generation", model=call.get("model_version") or call.get("model"),
                    metadata={"provider": call.get("provider"), "seconds": call.get("seconds"), "requested_model": call.get("model")},
                    level="DEFAULT" if call.get("ok") else "ERROR", status_message=call.get("error"),
                ).end()
            except Exception:
                log.exception("trace generation failed")

    async def finish(self, outcome: str, detail: Any = None) -> None:
        if self.root is None:
            return
        try:
            self.root.update(output={"outcome": outcome, "detail": detail},
                             level="ERROR" if outcome == "error" else "DEFAULT")
            self.root.end()
            await anyio.to_thread.run_sync(self.tracer.client.flush)  # flush does network I/O: keep it off the event loop
        except Exception:
            log.exception("trace finish failed")
