# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27", "python-dotenv>=1.0"]
# ///
"""Phase 1: explore the Qloo API and answer the open questions in docs/qloo-notes.md.

Usage (from the repo root):
  uv run scripts/qloo_explore.py search "Arctic Monkeys" --types urn:entity:artist
  uv run scripts/qloo_explore.py tags coffee
  uv run scripts/qloo_explore.py insights filter.type=urn:entity:destination signal.interests.entities=<id>
  uv run scripts/qloo_explore.py shape filter.type=urn:entity:place filter.location.query=Tokyo
  uv run scripts/qloo_explore.py hypothesis      # do different tastes give different destinations?
  uv run scripts/qloo_explore.py probe place     # which params actually change results (or are silently ignored)?
  uv run scripts/qloo_explore.py probe destination
  uv run scripts/qloo_explore.py coverage        # how much place data per city?

Add --no-cache to force fresh calls. Raw responses are cached in qloo_responses/ (git-ignored).
"""

from __future__ import annotations

import argparse
import itertools
from collections import Counter
from typing import Any

from _qloo import Qloo, QlooResponse, affinity, ids, item_id, jaccard, key_paths, lat_lon

# Hand-resolved test tastes (no LLM in Phase 1). Search types use /search naming: note "videogame" there vs "video_game" in insights.
PERSONAS: dict[str, list[tuple[str, str]]] = {
    "film-indie": [("Interstellar", "urn:entity:movie"), ("Arctic Monkeys", "urn:entity:artist"), ("Muji", "urn:entity:brand")],
    "foodie": [("Parts Unknown", "urn:entity:tv_show"), ("The Bear", "urn:entity:tv_show"), ("Anthony Bourdain", "urn:entity:person")],
    "techno": [("Kraftwerk", "urn:entity:artist"), ("Daft Punk", "urn:entity:artist"), ("Berghain", "urn:entity:place")],
    "heritage": [("Pride and Prejudice", "urn:entity:book"), ("Bridgerton", "urn:entity:tv_show"), ("Ludovico Einaudi", "urn:entity:artist")],
}

COVERAGE_CITIES = ["Tokyo", "Lisbon", "New York City", "Mexico City", "Bengaluru", "Goa", "Jaipur", "Ulaanbaatar"]


# ---------- printing ----------

def print_items(resp: QlooResponse, limit: int = 10) -> None:
    status = f"{resp.status} · {resp.seconds}s" + (" · cached" if resp.cached else "")
    if not resp.ok:
        print(f"  ✗ {status} · {resp.message}")
        return
    items = resp.items()
    print(f"  ✓ {status} · {len(items)} results")
    for i, item in enumerate(items[:limit], 1):
        aff = affinity(item)
        loc = lat_lon(item)
        types = item.get("types") or item.get("type") or ""
        extras = [f"aff={aff:.3f}" if isinstance(aff, (int, float)) else "", f"@{loc[0]:.3f},{loc[1]:.3f}" if loc else ""]
        print(f"  {i:>2}. {item.get('name', '?'):<40} {str(item_id(item))[:12]:<12} {str(types)[:40]:<40} {' '.join(e for e in extras if e)}")


def print_table(headers: list[str], rows: list[list[Any]]) -> None:
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
    for row in [headers, ["-" * w for w in widths], *rows]:
        print("  " + "  ".join(str(x).ljust(w) for x, w in zip(row, widths)))


def parse_kv(pairs: list[str]) -> dict[str, str]:
    params = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"Expected key=value, got {pair!r}")
        params[key] = value
    return params


# ---------- building blocks ----------

def resolve(q: Qloo, name: str, type_urn: str) -> str | None:
    resp = q.get("/search", {"query": name, "types": type_urn, "take": 1})
    found = ids(resp)
    marker = f"→ {resp.items()[0].get('name')} ({found[0][:12]})" if found else f"→ NOT FOUND ({resp.status} {resp.message})"
    print(f"    resolve {name!r} [{type_urn.split(':')[-1]}] {marker}")
    return found[0] if found else None


def resolve_persona(q: Qloo, persona: str) -> list[str]:
    print(f"  persona {persona}:")
    return [i for i in (resolve(q, n, t) for n, t in PERSONAS[persona]) if i]


def first_tag_id(q: Qloo, query: str) -> str | None:
    resp = q.get("/v2/tags", {"filter.query": query, "take": 5})
    found = ids(resp)
    print(f"    tag {query!r} → {found[0] if found else f'NOT FOUND ({resp.status} {resp.message})'}")
    return found[0] if found else None


# ---------- commands ----------

def cmd_search(q: Qloo, args: argparse.Namespace) -> None:
    print_items(q.get("/search", {"query": args.query, "types": args.types, "take": args.take}), args.take)


def cmd_tags(q: Qloo, args: argparse.Namespace) -> None:
    print_items(q.get("/v2/tags", {"filter.query": args.query, "take": args.take, **parse_kv(args.param)}), args.take)


def cmd_insights(q: Qloo, args: argparse.Namespace) -> None:
    print_items(q.get("/v2/insights", parse_kv(args.params)), args.take)


def cmd_shape(q: Qloo, args: argparse.Namespace) -> None:
    """Which fields appear on result items, and how often (answers: do places have lat/lng, price, images, tags?)."""
    resp = q.get(args.path, parse_kv(args.params))
    print_items(resp, 3)
    items = resp.items()
    if not items:
        return
    counts = Counter(path for item in items for path in key_paths(item))
    print(f"\n  field presence across {len(items)} items:")
    for path, n in sorted(counts.items()):
        print(f"  {100 * n // len(items):>4}%  {path}")


def cmd_hypothesis(q: Qloo, args: argparse.Namespace) -> None:
    """Core bet of the project: contrasting tastes must give clearly different destinations."""
    tops: dict[str, list[str]] = {}
    for persona in PERSONAS:
        entity_ids = resolve_persona(q, persona)
        resp = q.get("/v2/insights", {"filter.type": "urn:entity:destination", "signal.interests.entities": entity_ids, "take": 10})
        print_items(resp, 10)
        tops[persona] = ids(resp)

    print("\n  pairwise overlap of top-10 destinations (Jaccard, lower = more personalised):")
    rows = [[a, b, jaccard(tops[a], tops[b])] for a, b in itertools.combinations(tops, 2)]
    print_table(["persona A", "persona B", "overlap"], rows)
    mean = sum(r[2] for r in rows) / len(rows)
    verdict = "PASS: taste drives destinations" if mean < 0.5 else "FAIL: results look popularity-driven; rethink signals"
    print(f"\n  mean overlap {mean:.2f} → {verdict}")


def run_probe(q: Qloo, base: dict[str, Any], variants: list[tuple[str, dict[str, Any]]]) -> None:
    """Send base and base+variant; identical results mean the param was probably ignored (Qloo ignores invalid params silently)."""
    base_resp = q.get("/v2/insights", base)
    print("  base:")
    print_items(base_resp, 5)
    if not base_resp.ok:
        return
    base_ids = ids(base_resp)
    base_fields = set().union(*(key_paths(i) for i in base_resp.items())) if base_resp.items() else set()

    rows = []
    for label, change in variants:
        params = dict(base)
        for key, value in change.items():
            if value is None:
                params.pop(key, None)
            else:
                params[key] = value
        resp = q.get("/v2/insights", params)
        if not resp.ok:
            rows.append([label, f"ERROR {resp.status}", "-", "-", resp.message[:50], resp.seconds])
            continue
        new_ids = ids(resp)
        new_fields = set().union(*(key_paths(i) for i in resp.items())) - base_fields if resp.items() else set()
        if not new_ids:
            verdict = "EMPTY"
        elif new_ids == base_ids and not new_fields:
            verdict = "IGNORED?"
        else:
            verdict = "CHANGED"
        rows.append([label, verdict, jaccard(base_ids, new_ids), len(new_ids), ", ".join(sorted(new_fields))[:50], resp.seconds])

    print()
    print_table(["variant", "verdict", "overlap", "n", "new fields", "secs"], rows)
    print("\n  IGNORED? = same results in same order: param likely invalid for this type (or no effect). Record findings in docs/qloo-notes.md.")


def cmd_probe(q: Qloo, args: argparse.Namespace) -> None:
    entity_ids = resolve_persona(q, "film-indie")
    common: list[tuple[str, dict[str, Any]]] = [
        ("no taste signal", {"signal.interests.entities": None}),
        ("explainability on", {"feature.explainability": "true"}),
        ("bias.trends=medium", {"bias.trends": "medium"}),
        ("popularity.min=0.5", {"filter.popularity.min": "0.5"}),
        ("demographics age", {"signal.demographics.age": "35_and_younger"}),
    ]

    if args.target == "destination":
        base = {"filter.type": "urn:entity:destination", "signal.interests.entities": entity_ids, "take": 10}
        variants = common + [
            ("country_code=JP", {"filter.geocode.country_code": "JP"}),
            ("near Bengaluru", {"signal.location.query": "Bengaluru"}),
        ]
    else:
        coffee = first_tag_id(q, "coffee")
        base = {"filter.type": "urn:entity:place", "filter.location.query": "Tokyo", "signal.interests.entities": entity_ids, "take": 20}
        variants = common + [
            ("radius=2000", {"filter.location.radius": "2000"}),
            *([("tag: coffee", {"filter.tags": coffee})] if coffee else []),
            ("price_level.min=3", {"filter.price_level.min": "3"}),
            ("tripadvisor.rating.min=4", {"filter.external.tripadvisor.rating.min": "4"}),
            ("lat,lon instead of query", {"filter.location.query": None, "filter.location": "35.6595,139.7005"}),
        ]
    run_probe(q, base, variants)


def cmd_coverage(q: Qloo, args: argparse.Namespace) -> None:
    entity_ids = resolve_persona(q, "film-indie")
    rows = []
    for city in args.cities or COVERAGE_CITIES:
        resp = q.get("/v2/insights", {"filter.type": "urn:entity:place", "filter.location.query": city,
                                      "signal.interests.entities": entity_ids, "take": 50})
        items = resp.items()
        with_loc = sum(1 for i in items if lat_lon(i))
        top_tags = Counter(t.get("name") for i in items for t in (i.get("tags") or [])[:3] if isinstance(t, dict))
        rows.append([city, resp.status, len(items), f"{100 * with_loc // max(len(items), 1)}%", resp.seconds,
                     ", ".join(n for n, _ in top_tags.most_common(3) if n)[:45]])
    print_table(["city", "status", "places", "with lat/lon", "secs", "common tags"], rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-cache", action="store_true", help="ignore cached responses")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="name → entity IDs")
    p.add_argument("query")
    p.add_argument("--types", help="e.g. urn:entity:movie,urn:entity:tv_show")
    p.add_argument("--take", type=int, default=5)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("tags", help="word → tag IDs")
    p.add_argument("query")
    p.add_argument("--take", type=int, default=10)
    p.add_argument("--param", nargs="*", default=[], help="extra key=value params to try")
    p.set_defaults(func=cmd_tags)

    p = sub.add_parser("insights", help="raw /v2/insights call with key=value params")
    p.add_argument("params", nargs="+")
    p.add_argument("--take", type=int, default=10, help="rows to print")
    p.set_defaults(func=cmd_insights)

    p = sub.add_parser("shape", help="field presence across results")
    p.add_argument("params", nargs="+")
    p.add_argument("--path", default="/v2/insights")
    p.set_defaults(func=cmd_shape)

    sub.add_parser("hypothesis", help="do tastes change destinations?").set_defaults(func=cmd_hypothesis)

    p = sub.add_parser("probe", help="which params change results")
    p.add_argument("target", choices=["destination", "place"])
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("coverage", help="place data per city")
    p.add_argument("cities", nargs="*")
    p.set_defaults(func=cmd_coverage)

    args = parser.parse_args()
    args.func(Qloo(use_cache=not args.no_cache), args)


if __name__ == "__main__":
    main()
