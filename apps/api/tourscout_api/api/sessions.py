"""Guest sessions: an anonymous id per browser, expiring after session_ttl_s.

Which plans a guest owns is stored in the plans table under "guest:<id>" (api/plans.py), so signing in can move them to
the account. The ids themselves are kept in memory (one API instance): a restart starts guests on a fresh session.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


@dataclass
class Session:
    id: str
    created: float


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

    def _sweep(self) -> None:
        now = self.clock()
        for sid in [s.id for s in self._sessions.values() if now - s.created > self.ttl_s]:
            del self._sessions[sid]
