"""Command-line runner for the TourScout agent.

    uv run tourscout --persona us-02 --auto                  # an eval persona, no checkpoints
    uv run tourscout "I'm Hovvdy, 8 shows in the Midwest in April, leaving from Austin"
    uv run tourscout --persona nq-02 --auto --compare        # also run the LLM-only baseline
    uv run tourscout --persona us-02 --auto --refine "skip Detroit"

Plans are written to ~/.cache/tourscout/plans/ (outside the repo: they contain Qloo-derived data).
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

import anyio

from .agent.outputs import to_csv, to_ics
from .agent.runner import TourAgent
from .baseline import plan_baseline
from . import personas

OUT_DIR = Path.home() / ".cache" / "tourscout" / "plans"


def load_persona(persona_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        return personas.load(persona_id)
    except KeyError:
        raise SystemExit(f"persona {persona_id} not found in {personas.PERSONAS}") from None


def ask(checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Answer a human checkpoint in the terminal."""
    print(f"\n⏸  {checkpoint['question']}")
    if checkpoint["type"] == "confirm_artist":
        candidates = checkpoint["candidates"]
        for i, c in enumerate(candidates, 1):
            print(f"   {i}. {c['name']}  (popularity {c['popularity']}, {', '.join(c['genres'][:3])})")
        numbers = "1" if len(candidates) == 1 else f"1–{len(candidates)}"
        while True:
            choice = input(f"   {numbers} to pick, or n if none of these is you: ").strip().lower()
            if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                return {"choice": candidates[int(choice) - 1]["id"]}
            if choice in ("n", "none", "no"):
                break
            print(f"   please type {numbers}, or n")
        default = ", ".join(checkpoint["sounds_like"]) or "Enter = let TourScout suggest some"
        names = input(f"   artists you sound like, comma-separated [{default}]: ").strip()
        return {"choice": None, "sounds_like": [n.strip() for n in names.split(",") if n.strip()] or checkpoint["sounds_like"]}
    for m in checkpoint["metros"]:
        mark = "✓" if m["metro"] in checkpoint["selected"] else " "
        print(f"   {mark} {m['metro']:<24} demand {m['demand']:5.1f}  reach {m['reach']:5.1f}  gap {m['gap']:+6.1f}  {m['label']}")
    edit = input("   Enter to accept, or type cities to use (comma-separated): ").strip()
    if not edit:
        return {"selected": checkpoint["selected"]}
    wanted = [w.strip().lower() for w in edit.split(",")]
    return {"selected": [m["metro"] for m in checkpoint["metros"] if any(m["metro"].lower().startswith(w) for w in wanted)]}


def show(plan: dict[str, Any], events: list[dict[str, Any]], llm_calls: list[dict[str, Any]], seconds: float) -> None:
    print("\n── agent trace " + "─" * 50)
    for e in events:
        print(f"  {e['node']:<15} {e['message']}")
    print(f"\n── {plan['headline']} " + "─" * 10)
    if not plan["on_qloo"]:
        print(f"  (not on Qloo: audience modelled on {', '.join(plan['signal_names'])})")
    print(f"  {plan['summary']}\n")
    for s in plan["stops"]:
        v = s["venue"] or {}
        openers = ", ".join(f"{o['name']} [{o.get('badge', '?')}]" for o in s["openers"]) or "—"
        sponsors = ", ".join(b["name"] for b in s["sponsors"]) or "—"
        travel = "  (travel day before)" if s["travel_day_before"] else ""
        print(f"  {s['date']}  {s['metro']:<22} {s['label']:<9} D{s['demand']:>5.1f} R{s['reach']:>5.1f}  {s['drive_km']:>4} km{travel}")
        print(f"      venue: {v.get('name', '—')} · capacity: verify   openers: {openers}   sponsor: {sponsors}")
        print(f"      why: {s['why']}")
    print(f"\n  total {plan['total_km']} km · days off {plan['days_off'] or '—'} · dropped {plan['dropped'] or '—'}")
    print(f"  sponsor strategy: {plan['sponsor_strategy']}")
    for kind, msg in plan.get("outreach", {}).items():
        if isinstance(msg, dict):
            print(f"\n  ✉ {kind} → {msg.get('brand') or msg.get('opener')}: {msg['subject']}\n    {msg['body'][:400]}")
    used = {f"{c['provider']}:{c['model_version'] or c['model']}" for c in llm_calls if c["ok"]}
    failed = sum(not c["ok"] for c in llm_calls)
    for c in llm_calls:
        if not c["ok"]:
            print(f"  ⚠ {c['purpose']} on {c['provider']} failed after {c['seconds']}s: {(c['error'] or '')[:160]}")
    print(f"\n  composed by {plan['composed_by']} · {len(llm_calls)} LLM calls ({failed} failed, fell back) via {sorted(used)}")
    print(f"  ⏱ {seconds:.1f} s")


async def run(args: argparse.Namespace) -> None:
    intake, reach_input = load_persona(args.persona) if args.persona else (None, {})
    agent = TourAgent.from_env(outreach=not args.no_outreach)
    thread = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    try:
        out = await agent.start(thread, request=args.request or "", intake=intake, reach_input=reach_input,
                                auto_approve=args.auto)
        while out["interrupt"]:
            out = await agent.resume(thread, ask(out["interrupt"]))
        if args.refine:
            print(f"\n↻ refine: {args.refine}")
            out = await agent.refine(thread, args.refine)
            while out["interrupt"]:
                out = await agent.resume(thread, ask(out["interrupt"]))
        state = out["state"]
        show(state["plan"], state["events"], state.get("llm_calls", []), time.perf_counter() - start)

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        stem = OUT_DIR / f"{args.persona or 'request'}-{thread}"
        stem.with_suffix(".json").write_text(json.dumps(state["plan"], indent=2, ensure_ascii=False))
        stem.with_suffix(".csv").write_text(to_csv(state["plan"]))
        stem.with_suffix(".ics").write_text(to_ics(state["plan"]))
        print(f"  saved {stem}.json / .csv / .ics")

        if args.compare:
            base = await plan_baseline(agent.ctx.llm, request=args.request or "", intake=state["intake"])
            print("\n── LLM-only baseline (no Qloo) " + "─" * 30)
            for s in base["stops"]:
                print(f"  {s['date']}  {s['city']:<20} venue: {s['venue']}  openers: {', '.join(s['openers']) or '—'}")
    finally:
        await agent.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("request", nargs="?", help="free-text request")
    parser.add_argument("--persona", help="eval persona id, e.g. us-02")
    parser.add_argument("--auto", action="store_true", help="skip the human checkpoints")
    parser.add_argument("--refine", help="a follow-up instruction to apply after the first plan")
    parser.add_argument("--compare", action="store_true", help="also run the LLM-only baseline")
    parser.add_argument("--no-outreach", action="store_true", help="skip the sponsor pitch and opener DM")
    args = parser.parse_args()
    if not args.request and not args.persona:
        parser.error("give a request or --persona")
    try:
        anyio.run(run, args)
    except (KeyboardInterrupt, EOFError):
        print("\n  cancelled.")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
