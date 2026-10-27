"""Which query params each Qloo call may use.

Qloo silently ignores params it doesn't support for a filter.type, so a typo or an unsupported filter returns plausible but
wrong results. Every request goes through validate() first. The lists come from the Phase 1 probes (docs/qloo-notes.md):
only params we verified change results are allowed, and params we saw being ignored or harmful are rejected with a reason.
"""

from __future__ import annotations

from typing import Any

MAX_TAKE = 50  # take=100 returned 400 in Phase 1

COMMON = {"take", "page", "feature.explainability"}

INSIGHTS: dict[str, set[str]] = {
    "urn:heatmap": {"signal.interests.entities", "filter.location.query"},
    "urn:entity:artist": {
        "signal.interests.entities",
        "signal.interests.tags",
        "signal.location.query",
        "signal.location.weight",
        "filter.popularity.max",
        "filter.popularity.min",
        "filter.exclude.entities",
    },
    "urn:entity:place": {"signal.interests.entities", "filter.location.query", "filter.tags"},
    "urn:entity:brand": {
        "signal.interests.entities",
        "signal.location.query",
        "signal.demographics.age",
        "bias.trends",
    },
}

# Params we tested and must not send, with the reason shown to the caller.
REJECTED: dict[tuple[str, str], str] = {
    ("urn:entity:artist", "filter.location.query"): "ignored for artists; use signal.location.query",
    ("urn:entity:artist", "signal.location.radius"): "ignored by Qloo",
    ("urn:entity:place", "filter.popularity.max"): "pulls restaurants into venue results",
    ("urn:entity:place", "filter.rating.min"): "ignored by Qloo",
    ("urn:entity:place", "signal.location.radius"): "ignored by Qloo",
    ("urn:heatmap", "signal.demographics.age"): "returns ~7,400 cells and ignores the region",
}

UNSUPPORTED_TYPES = {"urn:entity:locality": "returns 400 on insights; use urn:heatmap"}

OTHER_PATHS: dict[str, set[str]] = {
    "/search": {"query", "types", "take", "page"},
    "/v2/tags": {"filter.query", "take", "page"},
    "/entities": {"entity_ids"},
}


class ParamNotAllowed(ValueError):
    pass


def validate(path: str, params: dict[str, Any]) -> None:
    """Raise ParamNotAllowed if a request uses a param we haven't verified for its endpoint and filter.type."""
    if "take" in params and int(params["take"]) > MAX_TAKE:
        raise ParamNotAllowed(f"take={params['take']} is above Qloo's limit of {MAX_TAKE}")

    if path in OTHER_PATHS:
        allowed = OTHER_PATHS[path]
        filter_type = path
    elif path == "/v2/insights":
        filter_type = params.get("filter.type", "")
        if filter_type in UNSUPPORTED_TYPES:
            raise ParamNotAllowed(f"{filter_type}: {UNSUPPORTED_TYPES[filter_type]}")
        if filter_type not in INSIGHTS:
            raise ParamNotAllowed(f"filter.type {filter_type!r} has no verified allow-list")
        allowed = INSIGHTS[filter_type] | COMMON | {"filter.type"}
    else:
        raise ParamNotAllowed(f"unknown Qloo path {path!r}")

    for key in params:
        if (filter_type, key) in REJECTED:
            raise ParamNotAllowed(f"{key} on {filter_type}: {REJECTED[(filter_type, key)]}")
        if key not in allowed:
            raise ParamNotAllowed(f"{key} is not verified for {filter_type}")
