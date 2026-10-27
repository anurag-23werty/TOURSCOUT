# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27", "python-dotenv>=1.0"]
# ///
"""Phase 1: explore the Qloo API for tour planning and answer the open questions in docs/qloo-notes.md.

Usage (from the repo root):
  uv run scripts/qloo_explore.py search "Hovvdy" --types urn:entity:artist
  uv run scripts/qloo_explore.py tags "record store"
  uv run scripts/qloo_explore.py insights filter.type=urn:entity:brand signal.interests.entities=<id>
  uv run scripts/qloo_explore.py shape filter.type=urn:heatmap signal.interests.entities=<id> filter.location.query=Texas
  uv run scripts/qloo_explore.py heatmap "Men I Trust" "United States"   # top demand cells
  uv run scripts/qloo_explore.py openers "Men I Trust" Chicago            # local acts smaller than the headliner
  uv run scripts/qloo_explore.py venues "Men I Trust" Chicago
  uv run scripts/qloo_explore.py sponsors "Men I Trust" --city Chicago
  uv run scripts/qloo_explore.py hypothesis      # do different artists get different demand maps?
  uv run scripts/qloo_explore.py probe openers   # which params change results (or are silently ignored)?
  uv run scripts/qloo_explore.py probe venues | probe sponsors | probe heatmap
  uv run scripts/qloo_explore.py coverage        # venue + opener data per city

Add --no-cache to force fresh calls. Raw responses are cached in qloo_responses/ (git-ignored).
"""

from __future__ import annotations

import argparse
import itertools
from collections import Counter
from typing import Any

from _qloo import Qloo, QlooResponse, affinity, ids, item_id, jaccard, key_paths, lat_lon, popularity

VENUE_TAGS = ["urn:tag:category:place:live_music_venue", "urn:tag:setting:qloo:music_venue"]
OPENER_LOCATION_WEIGHT = 25
OPENER_POPULARITY_MARGIN = 0.05

# Contrasting artists for the hypothesis test (all verified on Qloo).
HYPOTHESIS_ARTISTS = ["Men I Trust", "Thee Sacred Souls", "Ed Maverick", "Pinegrove"]
HYPOTHESIS_REGION = "United States"
COVERAGE_CITIES = ["Chicago", "Columbus", "Madison", "Austin", "London", "Berlin", "Mumbai", "Bengaluru"]


# ---------- printing ----------

def print_items(resp: QlooResponse, limit: int = 10) -> None:
    status = f"{resp.status} · {resp.seconds}s" + (" · cached" if resp.cached else "")
    if not resp.ok:
        print(f"  ✗ {status} · {resp.message}")
        return
    items = resp.items()
    print(f"  ✓ {status} · {len(items)} results")
    for i, item in enumerate(items[:limit], 1):
        aff, pop, loc = affinity(item), popularity(item), lat_lon(item)
        label = item.get("name") or (item.get("location") or {}).get("geohash") or "?"
        extras = [f"aff={aff:.3f}" if isinstance(aff, (int, float)) else "",
                  f"pop={pop:.3f}" if isinstance(pop, (int, float)) else "",
                  f"@{loc[0]:.3f},{loc[1]:.3f}" if loc else ""]
        print(f"  {i:>2}. {str(label)[:40]:<40} {str(item_id(item) or '')[:12]:<12} {' '.join(e for e in extras if e)}")


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

def resolve_artist(q: Qloo, name: str) -> dict[str, Any] | None:
    resp = q.get("/search", {"query": name, "types": "urn:entity:artist", "take": 1})
    items = resp.items()
    if not items:
        print(f"    resolve {name!r} → NOT FOUND ({resp.status} {resp.message})")
        return None
    artist = items[0]
    warn = "" if artist.get("name", "").lower() == name.lower() else "  ⚠️ different name: confirm with the user"
    print(f"    resolve {name!r} → {artist.get('name')} ({artist.get('entity_id', '')[:12]}) pop={artist.get('popularity') or 0:.3f}{warn}")
    return artist


def require_artist(q: Qloo, name: str) -> dict[str, Any]:
    artist = resolve_artist(q, name)
    if not artist:
        raise SystemExit(f"{name!r} is not on Qloo; use the sounds-like path with similar artists.")
    return artist


def heatmap_params(artist_id: str, region: str) -> dict[str, Any]:
    return {"filter.type": "urn:heatmap", "signal.interests.entities": artist_id, "filter.location.query": region}


def opener_params(artist: dict[str, Any], city: str, take: int = 10) -> dict[str, Any]:
    cap = max((artist.get("popularity") or 1.0) - OPENER_POPULARITY_MARGIN, 0.0)
    return {"filter.type": "urn:entity:artist", "signal.interests.entities": artist["entity_id"],
            "signal.location.query": city, "signal.location.weight": OPENER_LOCATION_WEIGHT,
            "filter.popularity.max": round(cap, 3), "filter.exclude.entities": artist["entity_id"], "take": take}


def venue_params(artist_id: str, city: str, tag: str, take: int = 10) -> dict[str, Any]:
    return {"filter.type": "urn:entity:place", "filter.location.query": city, "filter.tags": tag,
            "signal.interests.entities": artist_id, "take": take}


def sponsor_params(artist_id: str, city: str | None, take: int = 10) -> dict[str, Any]:
    return {"filter.type": "urn:entity:brand", "signal.interests.entities": artist_id,
            "signal.location.query": city, "take": take}


def demand_ranked_cells(resp: QlooResponse) -> list[dict[str, Any]]:
    """Rank cells by affinity weighted by popularity: affinity alone favours tiny, empty cells."""
    return sorted(resp.items(), key=lambda c: (affinity(c) or 0) * (popularity(c) or 0), reverse=True)


# ---------- commands ----------

def cmd_search(q: Qloo, args: argparse.Namespace) -> None:
    print_items(q.get("/search", {"query": args.query, "types": args.types, "take": args.take}), args.take)


def cmd_tags(q: Qloo, args: argparse.Namespace) -> None:
    print_items(q.get("/v2/tags", {"filter.query": args.query, "take": args.take, **parse_kv(args.param)}), args.take)


def cmd_insights(q: Qloo, args: argparse.Namespace) -> None:
    print_items(q.get("/v2/insights", parse_kv(args.params)), args.take)


def cmd_shape(q: Qloo, args: argparse.Namespace) -> None:
    """Which fields appear on result items, and how often."""
    resp = q.get(args.path, parse_kv(args.params))
    print_items(resp, 3)
    items = resp.items()
    if not items:
        return
    counts = Counter(path for item in items for path in key_paths(item))
    print(f"\n  field presence across {len(items)} items:")
    for path, n in sorted(counts.items()):
        print(f"  {100 * n // len(items):>4}%  {path}")


def cmd_heatmap(q: Qloo, args: argparse.Namespace) -> None:
    artist = require_artist(q, args.artist)
    resp = q.get("/v2/insights", heatmap_params(artist["entity_id"], args.region))
    if not resp.ok:
        print_items(resp)
        return
    ranked = demand_ranked_cells(resp)
    print(f"  {len(ranked)} cells in {resp.seconds}s; top {args.take} by affinity × popularity:")
    rows = [[i, (c.get("location") or {}).get("geohash"), f"{lat_lon(c)[0]:.2f},{lat_lon(c)[1]:.2f}" if lat_lon(c) else "-",
             f"{affinity(c) or 0:.3f}", f"{popularity(c) or 0:.3f}"] for i, c in enumerate(ranked[:args.take], 1)]
    print_table(["#", "geohash", "lat,lon", "affinity", "popularity"], rows)
    print("  (paste lat,lon into a map to sanity-check; city mapping comes in Phase 2 via GeoNames)")


def cmd_openers(q: Qloo, args: argparse.Namespace) -> None:
    artist = require_artist(q, args.artist)
    params = opener_params(artist, args.city, args.take)
    print(f"  popularity cap {params['filter.popularity.max']} (headliner − {OPENER_POPULARITY_MARGIN}), location weight {OPENER_LOCATION_WEIGHT}")
    print_items(q.get("/v2/insights", params), args.take)


def cmd_venues(q: Qloo, args: argparse.Namespace) -> None:
    artist = require_artist(q, args.artist)
    for tag in VENUE_TAGS:
        print(f"  tag {tag}:")
        print_items(q.get("/v2/insights", venue_params(artist["entity_id"], args.city, tag, args.take)), args.take)


def cmd_sponsors(q: Qloo, args: argparse.Namespace) -> None:
    artist = require_artist(q, args.artist)
    national = q.get("/v2/insights", sponsor_params(artist["entity_id"], None, args.take))
    print("  national:")
    print_items(national, args.take)
    if args.city:
        local = q.get("/v2/insights", sponsor_params(artist["entity_id"], args.city, args.take))
        print(f"  {args.city}:")
        print_items(local, args.take)
        new = [i.get("name") for i in local.items() if item_id(i) not in set(ids(national))]
        print(f"  new in {args.city} vs national: {', '.join(n for n in new if n) or 'none'}")


def cmd_hypothesis(q: Qloo, args: argparse.Namespace) -> None:
    """Core bet: different artists must get clearly different demand maps (not just 'big cities')."""
    tops: dict[str, list[str]] = {}
    for name in HYPOTHESIS_ARTISTS:
        artist = require_artist(q, name)
        resp = q.get("/v2/insights", heatmap_params(artist["entity_id"], HYPOTHESIS_REGION))
        cells = demand_ranked_cells(resp)[:25]
        tops[name] = [(c.get("location") or {}).get("geohash") for c in cells]
        print(f"    {name}: {len(resp.items())} cells, top-25 kept")

    print(f"\n  pairwise overlap of top-25 demand cells in {HYPOTHESIS_REGION} (Jaccard, lower = more artist-specific):")
    rows = [[a, b, jaccard(tops[a], tops[b])] for a, b in itertools.combinations(tops, 2)]
    print_table(["artist A", "artist B", "overlap"], rows)
    mean = sum(r[2] for r in rows) / len(rows)
    verdict = "PASS: demand is artist-specific" if mean < 0.5 else "FAIL: maps look population-driven; reweight affinity vs popularity"
    print(f"\n  mean overlap {mean:.2f} → {verdict}")


def run_probe(q: Qloo, base: dict[str, Any], variants: list[tuple[str, dict[str, Any]]]) -> None:
    """Send base and base+variant; identical results mean the param was probably ignored (Qloo ignores invalid params silently)."""
    base_resp = q.get("/v2/insights", base)
    print("  base:")
    print_items(base_resp, 5)
    if not base_resp.ok:
        return
    base_ids = ids(base_resp) or [str(lat_lon(c)) for c in base_resp.items()]
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
        new_ids = ids(resp) or [str(lat_lon(c)) for c in resp.items()]
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
    print("\n  IGNORED? = same results in same order: param likely invalid for this type. Record in docs/qloo-notes.md.")


def cmd_probe(q: Qloo, args: argparse.Namespace) -> None:
    artist = require_artist(q, "Men I Trust")
    aid = artist["entity_id"]
    explain = ("explainability on", {"feature.explainability": "true"})

    if args.target == "openers":
        base = opener_params(artist, "Chicago")
        variants = [
            ("no location signal", {"signal.location.query": None, "signal.location.weight": None}),
            ("location weight default", {"signal.location.weight": None}),
            ("no popularity cap", {"filter.popularity.max": None}),
            ("no exclude headliner", {"filter.exclude.entities": None}),
            ("filter.location instead", {"signal.location.query": None, "signal.location.weight": None, "filter.location.query": "Chicago"}),
            ("signal.location.radius=30000", {"signal.location.radius": "30000"}),
            ("genre tag indie", {"signal.interests.tags": "urn:tag:genre:music:indie"}),
            explain,
        ]
    elif args.target == "venues":
        base = venue_params(aid, "Chicago", VENUE_TAGS[0], 15)
        variants = [
            ("no artist signal", {"signal.interests.entities": None}),
            ("setting:music_venue tag", {"filter.tags": VENUE_TAGS[1]}),
            ("rating.min=4.3", {"filter.properties.business_rating.min": "4.3"}),
            ("popularity.max=0.95", {"filter.popularity.max": "0.95"}),
            ("radius=5000", {"filter.location.radius": "5000"}),
            explain,
        ]
    elif args.target == "sponsors":
        base = sponsor_params(aid, None, 15)
        variants = [
            ("Chicago signal", {"signal.location.query": "Chicago"}),
            ("Austin signal", {"signal.location.query": "Austin"}),
            ("age 35_and_younger", {"signal.demographics.age": "35_and_younger"}),
            ("bias.trends=medium", {"bias.trends": "medium"}),
            explain,
        ]
    else:
        base = heatmap_params(aid, "Texas")
        variants = [
            ("no artist signal", {"signal.interests.entities": None}),
            ("region Illinois", {"filter.location.query": "Illinois"}),
            ("age 35_and_younger", {"signal.demographics.age": "35_and_younger"}),
        ]
    run_probe(q, base, variants)


def cmd_coverage(q: Qloo, args: argparse.Namespace) -> None:
    artist = require_artist(q, args.artist)
    rows = []
    for city in args.cities or COVERAGE_CITIES:
        venues = q.get("/v2/insights", venue_params(artist["entity_id"], city, VENUE_TAGS[0], 30))
        openers = q.get("/v2/insights", opener_params(artist, city, 10))
        top_venue = (venues.items() or [{}])[0].get("name", "-")
        top_opener = (openers.items() or [{}])[0].get("name", "-")
        rows.append([city, len(venues.items()), str(top_venue)[:28], len(openers.items()), str(top_opener)[:24],
                     round(venues.seconds + openers.seconds, 2)])
    print_table(["city", "venues", "top venue", "openers", "top opener", "secs"], rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-cache", action="store_true", help="ignore cached responses")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="name → entity IDs")
    p.add_argument("query")
    p.add_argument("--types", help="e.g. urn:entity:artist")
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

    p = sub.add_parser("heatmap", help="top demand cells for an artist in a region")
    p.add_argument("artist")
    p.add_argument("region")
    p.add_argument("--take", type=int, default=20)
    p.set_defaults(func=cmd_heatmap)

    for name, func, helptext in [("openers", cmd_openers, "local acts smaller than the headliner"),
                                 ("venues", cmd_venues, "live-music venues by audience fit")]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument("artist")
        p.add_argument("city")
        p.add_argument("--take", type=int, default=10)
        p.set_defaults(func=func)

    p = sub.add_parser("sponsors", help="brands the artist's fans love (national and per city)")
    p.add_argument("artist")
    p.add_argument("--city")
    p.add_argument("--take", type=int, default=10)
    p.set_defaults(func=cmd_sponsors)

    sub.add_parser("hypothesis", help="do different artists get different demand maps?").set_defaults(func=cmd_hypothesis)

    p = sub.add_parser("probe", help="which params change results")
    p.add_argument("target", choices=["openers", "venues", "sponsors", "heatmap"])
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("coverage", help="venue + opener data per city")
    p.add_argument("cities", nargs="*")
    p.add_argument("--artist", default="Men I Trust")
    p.set_defaults(func=cmd_coverage)

    args = parser.parse_args()
    args.func(Qloo(use_cache=not args.no_cache), args)


if __name__ == "__main__":
    main()
