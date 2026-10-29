"""Backtest: would TourScout's demand ranking have found the cities indie artists really toured?

For each artist in artists.json:
  1. setlist.fm → their most recent tour year in the country (≥ 6 distinct cities) → the metros they played.
  2. TourScout → Qloo heatmap for the artist over the whole country → metros ranked by demand (same scoring as the app,
     no reach data).
  3. Baselines on the same candidate metros: ranked by population, and random.
Metric: recall@N = share of played metros that are in the top N. Higher = the ranking finds where they actually played.

    cd apps/api && uv run python ../../evals/backtest/backtest.py
Writes evals/reports/backtest.md (aggregate numbers only).

Caveat (stated in the report): a real tour isn't the optimal tour, and today's taste data can reflect past touring.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any

import anyio
import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from setlistfm import SetlistFm, latest_tour  # noqa: E402

from tourscout_api.agent.toolbox import Toolbox  # noqa: E402
from tourscout_api.scoring import score  # noqa: E402
from tourscout_mcp.cache import make_cache  # noqa: E402
from tourscout_mcp.config import Settings  # noqa: E402

COUNTRY_NAMES = {"US": "United States", "GB": "United Kingdom", "IN": "India", "DE": "Germany", "CA": "Canada"}
NS = (10, 25)
REPORT = HERE.parent / "reports" / "backtest.md"


def recall_at(ranked: list[str], played: set[str], n: int) -> float:
    return len(played & set(ranked[:n])) / len(played) if played else 0.0


def evaluate(played: set[str], metros: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure: recall@N for TourScout's demand ranking vs population and random, over the same candidates."""
    candidates = {m["metro"] for m in metros}
    covered = played & candidates
    demand_rank = [s.metro for s in score(metros)]  # sorted by demand
    pop_rank = [m["metro"] for m in sorted(metros, key=lambda m: m["population"], reverse=True)]
    out: dict[str, Any] = {"played": len(played), "played_in_candidates": len(covered), "candidates": len(candidates)}
    for n in NS:
        out[f"tourscout@{n}"] = round(recall_at(demand_rank, covered, n), 3)
        out[f"population@{n}"] = round(recall_at(pop_rank, covered, n), 3)
        out[f"random@{n}"] = round(min(n, len(candidates)) / len(candidates), 3) if candidates else 0.0
    return out


async def main() -> None:
    artists = json.loads((HERE / "artists.json").read_text())
    settings = Settings()
    tools = Toolbox.from_env()
    sfm = SetlistFm(os.getenv("SETLISTFM_API_KEY", ""), make_cache(settings.cache_url, 90))
    rows = []
    try:
        for a in artists:
            found = await tools.resolve_artist(a["artist"])
            if found["needs_confirmation"]:
                print(f"skip {a['artist']}: not an exact Qloo match"); continue
            home = await tools.deps.musicbrainz.home(a["artist"]) if tools.deps.musicbrainz else None
            mbid = a.get("mbid") or (home or {}).get("mbid")
            if not mbid:
                print(f"skip {a['artist']}: no MusicBrainz id"); continue
            try:
                tour = latest_tour(await sfm.shows(mbid), a["country"], a.get("before_year"))
            except httpx.HTTPStatusError as exc:  # one artist failing shouldn't sink the backtest
                print(f"skip {a['artist']}: setlist.fm HTTP {exc.response.status_code}"); continue
            if not tour:
                print(f"skip {a['artist']}: no tour with ≥ 6 cities in {a['country']}"); continue
            year, shows = tour
            played = set()
            for s in shows:
                metro = (tools.deps.metros.nearest(s["lat"], s["lon"]) if s.get("lat") is not None and tools.deps.metros
                         else tools.metro(f"{s['city']}, {s['state']}" if s.get("state") else s["city"]))
                if metro:
                    played.add(metro.label)
            demand = await tools.demand_map([found["candidates"][0]["id"]], COUNTRY_NAMES[a["country"]], top_n=1000)
            result = {"artist": a["artist"], "year": year, **evaluate(played, demand["metros"])}
            rows.append(result)
            print(f"{a['artist']:<24} {year} played {result['played']} metros · "
                  + " · ".join(f"@{n}: TS {result[f'tourscout@{n}']:.0%} pop {result[f'population@{n}']:.0%}" for n in NS))
    finally:
        await tools.aclose()
        await sfm.aclose()
    write_report(rows)


def write_report(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("no artists scored"); return
    mean = lambda k: statistics.mean(r[k] for r in rows)  # noqa: E731
    lines = [
        "# Backtest: real tours vs TourScout's demand ranking",
        "",
        f"{len(rows)} artists. For each, the metros from their most recent real tour (setlist.fm, ≥ 6 cities in one "
        "country and year) are compared with three rankings of the same candidate metros: TourScout's demand score "
        "(Qloo heatmap, no reach data), population, and random. Recall@N = share of the played metros in the top N.",
        "",
        "| Ranking | Recall@10 | Recall@25 |",
        "|---|---|---|",
        f"| **TourScout demand** | **{mean('tourscout@10'):.0%}** | **{mean('tourscout@25'):.0%}** |",
        f"| Population only | {mean('population@10'):.0%} | {mean('population@25'):.0%} |",
        f"| Random | {mean('random@10'):.0%} | {mean('random@25'):.0%} |",
        "",
        "| Artist | Tour year | Metros played | TS@10 | Pop@10 | TS@25 | Pop@25 |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [f"| {r['artist']} | {r['year']} | {r['played_in_candidates']} | {r['tourscout@10']:.0%} | {r['population@10']:.0%} | "
              f"{r['tourscout@25']:.0%} | {r['population@25']:.0%} |" for r in rows]
    lines += ["", "**Caveats.** A real tour is not the optimal tour (routing, offers and luck shape it), so this measures "
              "signal, not ground truth. Qloo's taste data is current, and touring a city can itself create fans there, so "
              "some agreement may run in the other direction. Population is a strong baseline because big cities get "
              "most shows; TourScout's job is the mid-sized cities population misses."]
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    anyio.run(main)
