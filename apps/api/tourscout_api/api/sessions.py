"""Guest sessions: no accounts. A session owns the plan threads it started; it expires after session_ttl_s.

Kept in memory on purpose (one API instance on the free tier). The plans themselves live in the checkpointer, so a restart
only forgets which browser owns which thread.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    created: float
    threads: set[str] = field(default_factory=set)


class SessionStore:
    def __init__(self, ttl_s: float, clock=time.monotonic) -> None:  # type: ignore[no-untyped-def]
        self.ttl_s, self.clock = ttl_s, clock
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        self._sweep()
        session = Session(secrets.token_urlsafe(16), self.clock())
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str | None) -> Session | None:
        session = self._sessions.get(session_id or "")
        if session and self.clock() - session.created > self.ttl_s:
            del self._sessions[session.id]
            return None
        return session

    def new_thread(self, session: Session) -> str:
        thread_id = secrets.token_hex(8)
        session.threads.add(thread_id)
        return thread_id

    def owns(self, session: Session, thread_id: str) -> bool:
        return thread_id in session.threads

    def _sweep(self) -> None:
        now = self.clock()
        for sid in [s.id for s in self._sessions.values() if now - s.created > self.ttl_s]:
            del self._sessions[sid]
