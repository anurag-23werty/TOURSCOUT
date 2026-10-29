"""Who owns which plan, so "My tours" survives restarts and works on every device.

The plan itself lives in the LangGraph checkpointer; this table is only the index: owner, a title and timestamps.
An owner is "user:<neon auth id>" or "guest:<session id>". Postgres in production (same DATABASE_URL as the
checkpoints), SQLite locally, memory in tests.
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import anyio

DEFAULT_SQLITE = Path.home() / ".cache" / "tourscout" / "plans.sqlite"
COLUMNS = "thread_id, owner, artist, headline, title, created, updated"


@dataclass
class PlanRow:
    thread_id: str
    owner: str
    artist: str = ""
    headline: str = ""
    title: str = ""  # set by the user; the list shows title or headline
    created: float = 0.0
    updated: float = 0.0

    def public(self) -> dict[str, Any]:
        row = asdict(self)
        del row["owner"]
        return row


class PlanStore(Protocol):
    async def add(self, thread_id: str, owner: str) -> None: ...
    async def owner_of(self, thread_id: str) -> str | None: ...
    async def list_for(self, owner: str, limit: int = 100) -> list[PlanRow]: ...
    async def update(self, thread_id: str, **fields: str) -> None: ...
    async def delete(self, thread_id: str) -> None: ...
    async def transfer(self, from_owner: str, to_owner: str) -> int: ...


EDITABLE = {"artist", "headline", "title"}


class MemoryPlanStore:
    def __init__(self) -> None:
        self.rows: dict[str, PlanRow] = {}

    async def add(self, thread_id: str, owner: str) -> None:
        now = time.time()
        self.rows[thread_id] = PlanRow(thread_id, owner, created=now, updated=now)

    async def owner_of(self, thread_id: str) -> str | None:
        row = self.rows.get(thread_id)
        return row.owner if row else None

    async def list_for(self, owner: str, limit: int = 100) -> list[PlanRow]:
        rows = [r for r in self.rows.values() if r.owner == owner]
        return sorted(rows, key=lambda r: r.updated, reverse=True)[:limit]

    async def update(self, thread_id: str, **fields: str) -> None:
        if row := self.rows.get(thread_id):
            for k, v in fields.items():
                if k in EDITABLE:
                    setattr(row, k, v)
            row.updated = time.time()

    async def delete(self, thread_id: str) -> None:
        self.rows.pop(thread_id, None)

    async def transfer(self, from_owner: str, to_owner: str) -> int:
        moved = [r for r in self.rows.values() if r.owner == from_owner]
        for r in moved:
            r.owner = to_owner
        return len(moved)


class SQLitePlanStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS plans (thread_id TEXT PRIMARY KEY, owner TEXT NOT NULL, "
                       "artist TEXT DEFAULT '', headline TEXT DEFAULT '', title TEXT DEFAULT '', created REAL, updated REAL)")
            db.execute("CREATE INDEX IF NOT EXISTS plans_owner ON plans (owner, updated)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    async def _run(self, sql: str, args: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        def go() -> list[tuple[Any, ...]]:
            with self._connect() as db:
                cur = db.execute(sql, args)
                return cur.fetchall() if cur.description else [(cur.rowcount,)]
        return await anyio.to_thread.run_sync(go)

    async def add(self, thread_id: str, owner: str) -> None:
        now = time.time()
        await self._run("INSERT OR REPLACE INTO plans (thread_id, owner, created, updated) VALUES (?, ?, ?, ?)",
                        (thread_id, owner, now, now))

    async def owner_of(self, thread_id: str) -> str | None:
        rows = await self._run("SELECT owner FROM plans WHERE thread_id = ?", (thread_id,))
        return rows[0][0] if rows else None

    async def list_for(self, owner: str, limit: int = 100) -> list[PlanRow]:
        rows = await self._run(f"SELECT {COLUMNS} FROM plans WHERE owner = ? ORDER BY updated DESC LIMIT ?", (owner, limit))
        return [PlanRow(*r) for r in rows]

    async def update(self, thread_id: str, **fields: str) -> None:
        fields = {k: v for k, v in fields.items() if k in EDITABLE}
        sets = "".join(f"{k} = ?, " for k in fields)
        await self._run(f"UPDATE plans SET {sets}updated = ? WHERE thread_id = ?", (*fields.values(), time.time(), thread_id))

    async def delete(self, thread_id: str) -> None:
        await self._run("DELETE FROM plans WHERE thread_id = ?", (thread_id,))

    async def transfer(self, from_owner: str, to_owner: str) -> int:
        return (await self._run("UPDATE plans SET owner = ? WHERE owner = ?", (to_owner, from_owner)))[0][0]


class PostgresPlanStore:
    def __init__(self, url: str, max_size: int = 4) -> None:
        self.url, self.max_size = url, max_size
        self._pool = None
        self._lock = anyio.Lock()

    async def _get_pool(self):  # type: ignore[no-untyped-def]
        async with self._lock:
            if self._pool is None:
                from psycopg_pool import AsyncConnectionPool

                # check: Neon's free tier suspends after idle minutes and drops connections; reconnect instead of failing.
                pool = AsyncConnectionPool(self.url, min_size=1, max_size=self.max_size, open=False,
                                           check=AsyncConnectionPool.check_connection, kwargs={"autocommit": True})
                await pool.open()
                async with pool.connection() as conn:
                    await conn.execute(
                        "CREATE TABLE IF NOT EXISTS plans (thread_id TEXT PRIMARY KEY, owner TEXT NOT NULL, "
                        "artist TEXT DEFAULT '', headline TEXT DEFAULT '', title TEXT DEFAULT '', "
                        "created DOUBLE PRECISION, updated DOUBLE PRECISION)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS plans_owner ON plans (owner, updated)")
                self._pool = pool
        return self._pool

    async def _run(self, sql: str, args: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        pool = await self._get_pool()
        async with pool.connection() as conn:
            cur = await conn.execute(sql, args)
            return await cur.fetchall() if cur.description else [(cur.rowcount,)]

    async def add(self, thread_id: str, owner: str) -> None:
        now = time.time()
        await self._run("INSERT INTO plans (thread_id, owner, created, updated) VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (thread_id) DO UPDATE SET owner = EXCLUDED.owner", (thread_id, owner, now, now))

    async def owner_of(self, thread_id: str) -> str | None:
        rows = await self._run("SELECT owner FROM plans WHERE thread_id = %s", (thread_id,))
        return rows[0][0] if rows else None

    async def list_for(self, owner: str, limit: int = 100) -> list[PlanRow]:
        rows = await self._run(f"SELECT {COLUMNS} FROM plans WHERE owner = %s ORDER BY updated DESC LIMIT %s", (owner, limit))
        return [PlanRow(*r) for r in rows]

    async def update(self, thread_id: str, **fields: str) -> None:
        fields = {k: v for k, v in fields.items() if k in EDITABLE}
        sets = "".join(f"{k} = %s, " for k in fields)
        await self._run(f"UPDATE plans SET {sets}updated = %s WHERE thread_id = %s", (*fields.values(), time.time(), thread_id))

    async def delete(self, thread_id: str) -> None:
        await self._run("DELETE FROM plans WHERE thread_id = %s", (thread_id,))

    async def transfer(self, from_owner: str, to_owner: str) -> int:
        return (await self._run("UPDATE plans SET owner = %s WHERE owner = %s", (to_owner, from_owner)))[0][0]

    async def aclose(self) -> None:
        if self._pool is not None:
            await self._pool.close()


def make_plan_store(url: str | None = None) -> PlanStore:
    """Same switch as the checkpointer (core/checkpoint.py), so plans and their index always live together."""
    url = url if url is not None else os.getenv("DATABASE_URL", "")
    if (os.getenv("CHECKPOINTER") or "").lower() == "memory":
        return MemoryPlanStore()
    if url.startswith(("postgres://", "postgresql://")):
        return PostgresPlanStore(url)
    return SQLitePlanStore(DEFAULT_SQLITE)
