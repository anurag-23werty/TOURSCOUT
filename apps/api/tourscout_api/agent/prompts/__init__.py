"""Prompt templates live as Markdown files next to this module, so they're easy to read and diff."""

from __future__ import annotations

from functools import cache
from pathlib import Path

HERE = Path(__file__).parent


@cache
def _load(name: str) -> str:
    return (HERE / f"{name}.md").read_text(encoding="utf-8").strip()


def prompt(name: str, **values: object) -> str:
    """Fill {placeholders}. Literal braces in templates must be doubled ({{ }})."""
    return _load(name).format(**values)
