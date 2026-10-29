"""Where agent runs are saved between requests (so a checkpoint answer or a refine continues the same run).

    DATABASE_URL=postgresql://…   → Postgres (Neon in production)
    unset                         → SQLite in ~/.cache/tourscout/ (survives restarts locally, outside the repo)
    CHECKPOINTER=memory           → in-memory (tests)
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

DEFAULT_SQLITE = Path.home() / ".cache" / "tourscout" / "checkpoints.sqlite"


def describe(url: str | None = None) -> str:
    url = url if url is not None else os.getenv("DATABASE_URL", "")
    if (os.getenv("CHECKPOINTER") or "").lower() == "memory":
        return "memory"
    if url and url.startswith(("postgres://", "postgresql://")):
        return "postgres"
    return "sqlite"


@asynccontextmanager
async def open_checkpointer(url: str | None = None) -> AsyncIterator[Any]:
    url = url if url is not None else os.getenv("DATABASE_URL", "")
    kind = describe(url)
    if kind == "memory":
        yield InMemorySaver()
    elif kind == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(url) as saver:
            await saver.setup()  # creates the checkpoint tables on first run
            yield saver
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        DEFAULT_SQLITE.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(DEFAULT_SQLITE)) as saver:
            yield saver
