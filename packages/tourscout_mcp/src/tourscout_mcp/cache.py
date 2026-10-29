"""Private response cache (allowed by the Qloo hackathon guide; never committed).

Postgres (Neon) in production, SQLite locally, or no cache. All three share the same tiny async interface.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Protocol

import anyio


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any) -> None: ...


def cache_key(namespace: str, params: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps([namespace, sorted(params.items())]).encode()).hexdigest()


class NoCache:
    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any) -> None:
        return None


class MemoryCache:
    """For tests."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self.data.get(key)

    async def set(self, key: str, value: Any) -> None:
        self.data[key] = value


class SQLiteCache:
    def __init__(self, path: Path, ttl_s: float) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.ttl_s = path, ttl_s
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, body TEXT, created REAL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _get(self, key: str) -> Any | None:
        with self._connect() as db:
            row = db.execute("SELECT body, created FROM cache WHERE key = ?", (key,)).fetchone()
        if row and time.time() - row[1] < self.ttl_s:
            return json.loads(row[0])
        return None

    def _set(self, key: str, value: Any) -> None:
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)", (key, json.dumps(value), time.time()))

    async def get(self, key: str) -> Any | None:
        return await anyio.to_thread.run_sync(self._get, key)

    async def set(self, key: str, value: Any) -> None:
        await anyio.to_thread.run_sync(self._set, key, value)


class PostgresCache:
    """Pooled: a tour fan-out does ~120 cache reads, and a fresh TLS connection to Neon per read would add seconds."""

    def __init__(self, url: str, ttl_s: float, max_size: int = 8) -> None:
        self.url, self.ttl_s, self.max_size = url, ttl_s, max_size
        self._pool = None
        self._lock = anyio.Lock()

    async def _get_pool(self):  # type: ignore[no-untyped-def]
        async with self._lock:
            if self._pool is None:
                from psycopg_pool import AsyncConnectionPool  # optional dependency: tourscout-mcp[postgres]

                # check: Neon's free tier suspends after idle minutes and drops connections; reconnect instead of failing.
                pool = AsyncConnectionPool(self.url, min_size=1, max_size=self.max_size, open=False,
                                           check=AsyncConnectionPool.check_connection, kwargs={"autocommit": True})
                await pool.open()
                async with pool.connection() as conn:
                    await conn.execute(
                        "CREATE TABLE IF NOT EXISTS qloo_cache (key TEXT PRIMARY KEY, body JSONB, created TIMESTAMPTZ DEFAULT now())"
                    )
                self._pool = pool
        return self._pool

    async def get(self, key: str) -> Any | None:
        pool = await self._get_pool()
        async with pool.connection() as conn:
            cur = await conn.execute(
                "SELECT body FROM qloo_cache WHERE key = %s AND created > now() - make_interval(secs => %s)",
                (key, self.ttl_s),
            )
            row = await cur.fetchone()
        return row[0] if row else None

    async def set(self, key: str, value: Any) -> None:
        pool = await self._get_pool()
        async with pool.connection() as conn:
            await conn.execute(
                "INSERT INTO qloo_cache (key, body) VALUES (%s, %s::jsonb) "
                "ON CONFLICT (key) DO UPDATE SET body = EXCLUDED.body, created = now()",
                (key, json.dumps(value)),
            )

    async def aclose(self) -> None:
        if self._pool is not None:
            await self._pool.close()


def make_cache(url: str, ttl_days: int) -> Cache:
    ttl_s = ttl_days * 86400
    if url in ("", "none"):
        return NoCache()
    if url.startswith("sqlite:///"):
        return SQLiteCache(Path(url.removeprefix("sqlite:///")), ttl_s)
    if url.startswith(("postgres://", "postgresql://")):
        return PostgresCache(url, ttl_s)
    raise ValueError(f"unsupported cache URL scheme: {url.split(':', 1)[0]}")
