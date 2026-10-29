"""TourScout vs LLM-only on the eval personas.

    cd apps/api
    uv run python ../../evals/run.py run   [--ids us-01,nq-02]     # both planners → evals/reports/raw/<run>/ (git-ignored)
    uv run python ../../evals/run.py score [--run <run id>]        # metrics → evals/reports/summary.md (numbers only)

Raw outputs contain Qloo-derived data and stay out of git. The summary has aggregate numbers and persona ids only.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))  # so `metrics` imports when run from apps/api

from metrics import normalise_baseline, normalise_tourscout, rate  # noqa: E402
from metrics.checks import constraint_metrics, headliner, opener_metrics, venue_metrics  # noqa: E402
from metrics.edges import edge_checks  # noqa: E402
from metrics.judge import judge_sponsors  # noqa: E402

from tourscout_api import personas  # noqa: E402
from tourscout_api.agent.runner import TourAgent  # noqa: E402
from tourscout_api.agent.toolbox import Toolbox  # noqa: E402
from tourscout_api.baseline import plan_baseline  # noqa: E402
from tourscout_api.core.config import LLMSettings  # noqa: E402
from tourscout_api.core.llm import LLM, LLMUnavailable  # noqa: E402

RAW = ROOT / "reports" / "raw"
SUMMARY = ROOT / "reports" / "summary.md"


def free_text(p: dict[str, Any]) -> str:
    """Personas with notes (edge-01: a prompt injection) go through the free-text intake, like a real user."""
    window = p.get("window") or ["", ""]
    return (f"I'm {p['artist']}, based in {p['home_base']}. {p['n_shows']} shows in {', '.join(p['regions'])} "
            f"between {window[0]} and {window[1]}, max {p['max_drive_km']} km of driving a day. {p.get('notes', '')}")


# ---------------------------------------------------------------- run


async def run(ids: list[str] | None, into: str | None = None) -> Path:
    # --into reruns some personas inside an existing run (e.g. after fixing a bug); the summary says which.
    out_dir = RAW / (into or datetime.now().strftime("%Y%m%d-%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)
    agent = TourAgent.from_env(outreach=False)
    baseline_llm = LLM()
    rows = [p for p in personas.all_personas().values() if not ids or p["id"] in ids]
    try:
        for i, p in enumerate(rows, 1):
            intake, reach = personas.to_inputs(p)
            use_text = bool(p.get("notes"))
            print(f"[{i}/{len(rows)}] {p['id']} {p['artist'] or '(unnamed)'} …", flush=True)

            start, error, plan = time.perf_counter(), None, None
            try:
                out = await agent.start(f"eval-{out_dir.name}-{p['id']}", request=free_text(p) if use_text else "",
                                        intake=None if use_text else intake, reach_input=reach, auto_approve=True)
                plan = out["state"].get("plan")
                state = out["state"]
            except Exception as exc:  # an honest error is a valid outcome (edge-02)
                error, state = str(exc), (await agent.state(f"eval-{out_dir.name}-{p['id']}"))["state"]
            ts_seconds = round(time.perf_counter() - start, 1)

            start, base, base_error = time.perf_counter(), None, None
            try:
                base = await plan_baseline(baseline_llm, intake=state.get("intake") or intake)
            except LLMUnavailable as exc:
                base_error = str(exc)
            base_seconds = round(time.perf_counter() - start, 1)

            record = {
                "persona": p,
                "tourscout": {"plan": plan, "error": error, "seconds": ts_seconds,
                              "llm_calls": state.get("llm_calls", []),
                              "state": {"artist": state.get("artist"), "intake": state.get("intake")}},
                "baseline": {"plan": base, "error": base_error, "seconds": base_seconds},
            }
            (out_dir / f"{p['id']}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False, default=str))
            stops = len(plan["stops"]) if plan else 0
            print(f"    TourScout {ts_seconds}s, {stops} stops{' ERROR ' + error[:80] if error else ''} | "
                  f"LLM-only {base_seconds}s{' ERROR' if base_error else ''}", flush=True)
    finally:
        await agent.aclose()
        await baseline_llm.aclose()
    return out_dir


# ---------------------------------------------------------------- score


def pct(x: float | None) -> str:
    return "—" if x is None else f"{round(100 * x)}%"


def pooled(rows: list[dict[str, Any]], side: str, metric: str, count: str) -> float | None:
    """Pool a rate over personas, weighted by how many items each had (not a mean of means)."""
    hits = sum((r[side][metric] or 0) * r[side][count] for r in rows if r.get(side) and r[side][metric] is not None)
    total = sum(r[side][count] for r in rows if r.get(side) and r[side][metric] is not None)
    return round(hits / total, 3) if total else None


async def score(run_dir: Path) -> None:
    tools = Toolbox.from_env()
    deps = tools.deps
    judge = LLM(LLMSettings(primary="groq"))
    results = []
    try:
        for path in sorted(run_dir.glob("*.json")):
            if path.name == "scores.json":
                continue
            rec = json.loads(path.read_text())
            p, ts, base = rec["persona"], rec["tourscout"], rec["baseline"]
            print(f"scoring {p['id']} …", flush=True)
            intake = ts["state"].get("intake") or personas.to_inputs(p)[0]
            head = await headliner(deps, ts["state"])
            row: dict[str, Any] = {"id": p["id"], "group": p["id"].split("-")[0], "ts_seconds": ts["seconds"],
                                   "ts_llm_calls": len(ts.get("llm_calls") or []), "ts_error": ts["error"],
                                   "composed_by": (ts["plan"] or {}).get("composed_by"),
                                   "edges": edge_checks(p, ts)}
            for side, plan, norm in (("tourscout", ts["plan"], normalise_tourscout), ("baseline", base["plan"], normalise_baseline)):
                if not plan:
                    row[side] = None
                    continue
                stops = norm(plan)
                row[side] = {**await opener_metrics(deps, stops, head), **await venue_metrics(deps, stops),
                             **constraint_metrics(deps, stops, intake)}
            if ts["plan"] and base["plan"]:
                t_stops, b_stops = normalise_tourscout(ts["plan"]), normalise_baseline(base["plan"])
                try:
                    row["judge"] = await judge_sponsors(
                        judge, p["id"], ts["plan"]["artist"], (head or {}).get("genres", []),
                        [s["city"] for s in t_stops],
                        sorted({b for s in t_stops for b in s["sponsors"]})[:8],
                        sorted({b for s in b_stops for b in s["sponsors"]})[:8])
                except LLMUnavailable as exc:
                    row["judge"] = {"winner": "error", "reason": str(exc)}
            results.append(row)
    finally:
        await tools.aclose()
        await judge.aclose()
    (run_dir / "scores.json").write_text(json.dumps(results, indent=1, default=str))
    rerun_file = run_dir / "reruns.txt"
    lines = rerun_file.read_text().splitlines() if rerun_file.exists() else []
    reruns = sorted({pid for line in lines if line.strip() for pid in line.split()[-1].split(",")})  # "<date> <time> <ids>"
    write_summary(run_dir.name, results, reruns)


def write_summary(run_id: str, rows: list[dict[str, Any]], reruns: list[str] | None = None) -> None:
    both = [r for r in rows if r.get("tourscout") and r.get("baseline")]
    seconds = sorted(r["ts_seconds"] for r in rows if r.get("tourscout"))
    judged = [r["judge"]["winner"] for r in rows if r.get("judge") and r["judge"]["winner"] != "error"]
    edges = [(r["id"], name, ok) for r in rows for name, ok in r["edges"].items()]

    def line(label: str, metric: str, count: str, note: str = "") -> str:
        return (f"| {label} | **{pct(pooled(both, 'tourscout', metric, count))}** | {pct(pooled(both, 'baseline', metric, count))} | "
                f"{note} |")

    def sums(side: str, key: str) -> int:
        return sum(r[side][key] for r in both)

    out = [
        "# Eval results: TourScout vs LLM-only",
        "",
        f"Run `{run_id}` · {len(rows)} personas · {len(both)} with a plan from both planners. "
        "Same intake for both; the LLM-only planner gets no tools. Generated by `evals/run.py score`.",
        "",
        *([f"Rerun after bug fixes (region names like \"US East Coast\", an LLM retry gap): {', '.join(reruns)}. "
           "Their first attempts failed before planning; every other persona ran once.", ""] if reruns else []),
        "| Metric | TourScout | LLM-only | How it's measured |",
        "|---|---|---|---|",
        line("Openers based in the show's city", "local_rate", "openers", "MusicBrainz area / begin-area in the metro"),
        line("Openers based somewhere else", "elsewhere_rate", "openers", "lower is better"),
        line("Openers that exist on Qloo", "on_qloo_rate", "openers", "exact-name Qloo artist search"),
        line("Openers that fit (smaller + shared genre)", "fit_rate", "openers", "vs the headliner's Qloo popularity and genre tags"),
        line("Venues that exist in that city", "grounded_rate", "venues", "Qloo place id, or Qloo place search within 60 km"),
        line("Dates inside the requested window", "dates_in_window_rate", "shows_planned", ""),
        f"| Long drives without a day off | **{sums('tourscout', 'drive_violations')}** | {sums('baseline', 'drive_violations')} | "
        "legs over max_drive_km on consecutive days |",
        f"| Sponsor lists preferred by a blind judge | **{judged.count('tourscout')}** | {judged.count('baseline')} | "
        f"Groq gpt-oss-120b, A/B order randomised; ties {judged.count('tie')} |",
        "",
        f"**Openers counted:** TourScout {sums('tourscout', 'openers')}, LLM-only {sums('baseline', 'openers')}. "
        f"**Venues counted:** TourScout {sums('tourscout', 'venues')}, LLM-only {sums('baseline', 'venues')}.",
        "",
        "## Speed",
        f"TourScout time to a full plan: p50 **{statistics.median(seconds):.0f} s**, "
        f"p95 {seconds[max(0, int(len(seconds) * 0.95) - 1)]:.0f} s (cached Qloo responses after the first run). "
        f"LLM calls per plan: mean {statistics.mean(r['ts_llm_calls'] for r in rows):.1f}. "
        f"Brief written by the LLM in {sum(1 for r in rows if r['composed_by'] == 'llm')} of "
        f"{sum(1 for r in rows if r['composed_by'])} plans (the rest used the grounded automatic brief, fully or per stop).",
        "",
        "## By persona group",
        "| Group | Personas | Local openers (TS / LLM) | Venues exist (TS / LLM) |",
        "|---|---|---|---|",
    ]
    for group in ("us", "eu", "in", "nq", "edge"):
        g = [r for r in both if r["group"] == group]
        if g:
            out.append(f"| {group} | {len(g)} | {pct(pooled(g, 'tourscout', 'local_rate', 'openers'))} / "
                       f"{pct(pooled(g, 'baseline', 'local_rate', 'openers'))} | "
                       f"{pct(pooled(g, 'tourscout', 'grounded_rate', 'venues'))} / {pct(pooled(g, 'baseline', 'grounded_rate', 'venues'))} |")
    out += ["", "## Behaviour checks", "| Persona | Check | Result |", "|---|---|---|"]
    out += [f"| {pid} | {name.replace('_', ' ')} | {'✅' if ok else '❌'} |" for pid, name, ok in edges]
    passed = sum(ok for _, _, ok in edges)
    out += ["", f"{passed} of {len(edges)} checks pass.", "", "## Per persona", "",
            "| Persona | TS s | TS local | LLM local | TS venues exist | LLM venues exist | Judge |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        t, b = r.get("tourscout") or {}, r.get("baseline") or {}
        out.append(f"| {r['id']} | {r['ts_seconds']} | {pct(t.get('local_rate'))} | {pct(b.get('local_rate'))} | "
                   f"{pct(t.get('grounded_rate'))} | {pct(b.get('grounded_rate'))} | {(r.get('judge') or {}).get('winner', '—')} |")
    out += ["", "## Caveats",
            "- MusicBrainz hometowns are incomplete: an opener with no hometown counts as *not* local for both planners.",
            "- Qloo's place index is incomplete too: a real venue the LLM-only planner names may not be found, so its "
            "venue rate is a lower bound.",
            "- The judge is one model; a 5–10 person human panel on a subset is planned.",
            "- Raw plans contain Qloo data and are not committed (`evals/reports/raw/`)."]
    SUMMARY.write_text("\n".join(out) + "\n")
    print(f"wrote {SUMMARY}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--ids", help="comma-separated persona ids (default: all)")
    r.add_argument("--into", help="write into an existing run id (reruns are listed in the summary)")
    s = sub.add_parser("score")
    s.add_argument("--run", help="run id under evals/reports/raw (default: latest)")
    args = parser.parse_args()
    if args.cmd == "run":
        out = anyio.run(run, args.ids.split(",") if args.ids else None, args.into)
        if args.into and args.ids:
            with (out / "reruns.txt").open("a") as fh:
                fh.write(f"{datetime.now():%Y-%m-%d %H:%M} {args.ids}\n")
        print(f"raw outputs in {out}\nnext: uv run python ../../evals/run.py score --run {out.name}")
    else:
        runs = sorted(d for d in RAW.iterdir() if d.is_dir()) if RAW.exists() else []
        target = RAW / args.run if args.run else (runs[-1] if runs else None)
        if not target or not target.exists():
            raise SystemExit("no run found: run `evals/run.py run` first")
        anyio.run(score, target)


if __name__ == "__main__":
    main()
