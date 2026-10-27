"""Tool implementations. Each takes a Deps first so tests can pass fakes; server.py exposes them over MCP."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import anyio

from ..cache import make_cache
from ..config import Settings
from ..geo import Metro, MetroIndex, fold
from ..musicbrainz import MusicBrainz
from ..qloo import QlooClient

T = TypeVar("T")


@dataclass
class Deps:
    qloo: QlooClient
    musicbrainz: MusicBrainz | None = None
    metros: MetroIndex | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_settings(cls, settings: Settings) -> "Deps":
        cache = make_cache(settings.cache_url, settings.cache_ttl_days)
        deps = cls(
            qloo=QlooClient(settings.qloo_api_key, settings.qloo_base_url, cache, settings.timeout_s),
            musicbrainz=MusicBrainz(settings.musicbrainz_user_agent, cache),
        )
        try:
            deps.metros = MetroIndex.from_file(settings.geonames_file)
        except FileNotFoundError as exc:
            deps.notes.append(str(exc))
        return deps

    def metro(self, city: str) -> Metro | None:
        return self.metros.find(city) if self.metros else None

    def metro_names(self, city: str) -> set[str]:
        metro = self.metro(city)
        return metro.members if metro else {fold(city.split(",")[0])}


async def gather(funcs: list[Callable[[], Awaitable[T]]]) -> list[T]:
    """Run coroutine factories concurrently and return their results in order."""
    results: list[Any] = [None] * len(funcs)

    async def run(i: int, func: Callable[[], Awaitable[T]]) -> None:
        results[i] = await func()

    async with anyio.create_task_group() as tg:
        for i, func in enumerate(funcs):
            tg.start_soon(run, i, func)
    return results
