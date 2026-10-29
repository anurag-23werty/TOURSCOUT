"""Sliding-window rate limits per key (IP) and per day, in memory.

Limits protect the free tiers (Groq 1,000 requests/day, Qloo hackathon key) from one visitor or a bot burning the day's
budget before the judges arrive.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class Decision:
    allowed: bool
    retry_after_s: int = 0
    reason: str = ""


class SlidingWindow:
    def __init__(self, limit: int, window_s: float, clock=time.monotonic) -> None:  # type: ignore[no-untyped-def]
        self.limit, self.window_s, self.clock = limit, window_s, clock
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, consume: bool = True) -> Decision:
        now = self.clock()
        q = self.hits[key]
        while q and now - q[0] >= self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return Decision(False, max(1, int(self.window_s - (now - q[0])) + 1))
        if consume:
            q.append(now)
        return Decision(True)


class Limiter:
    """Named limits: limiter.check("plan", ip) checks the per-IP window and the global daily cap together."""

    def __init__(self, per_key: dict[str, tuple[int, float]], global_daily: dict[str, int],
                 clock=time.monotonic) -> None:  # type: ignore[no-untyped-def]
        self.per_key = {name: SlidingWindow(n, w, clock) for name, (n, w) in per_key.items()}
        self.daily = {name: SlidingWindow(n, 86_400, clock) for name, n in global_daily.items()}

    def check(self, name: str, key: str) -> Decision:
        if name in self.daily:
            d = self.daily[name].check("*", consume=False)
            if not d.allowed:
                return Decision(False, d.retry_after_s, f"the demo's daily {name} budget is used up; try again later")
        if name in self.per_key:
            d = self.per_key[name].check(key)
            if not d.allowed:
                return Decision(False, d.retry_after_s, f"too many {name} requests from you; wait {d.retry_after_s}s")
        if name in self.daily:
            self.daily[name].check("*")
        return Decision(True)
