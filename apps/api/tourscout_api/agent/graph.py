"""The TourScout agent as a LangGraph state machine.

    START → intake → resolve → ⏸confirm_artist → reach → demand → score → ⏸pick_cities → route → fanout
          → compose ⇄ validate (≤ 2 retries) → outputs → END
    fanout → score (≤ 2 times): a chosen city has no venue data → swap it for the next best city and re-route
    START → refine → demand | score | route → …                (a follow-up like "skip Detroit" on the same thread)

⏸ = human checkpoint (LangGraph interrupt). With auto_approve=true (CLI, evals) the agent decides on its own.
The LLM parses the request, suggests "sounds like" artists, writes the brief and outreach. Everything else (which cities,
which order, every number) is tools + code. State is checkpointed, so a refine continues the same run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..core.llm import LLM, LLMUnavailable, dumps
from ..scoring import Stop, plan_route, score, select_cities
from .outputs import build_plan, fallback_brief, opener_dm, parse_refine, sponsor_pitch
from .prompts import prompt
from .reach import ingest, to_metros
from .schemas import Brief, Intake, SimilarArtists, TourState
from .toolbox import Toolbox
from .validate import salvage, validate_brief

MAX_COMPOSE_ATTEMPTS = 3  # first try + 2 retries
COMPOSE_PATIENCE_S = 40.0
MAX_VENUE_SWAPS = 2  # times the agent may swap out cities with no venue data and re-route  # the one big LLM call: wait longer for Gemini and for Groq's rate-limit window
DEFAULT_LEAD_DAYS = 60
NO_DRIVE_LIMIT_KM = 100_000.0


@dataclass
class AgentContext:
    llm: LLM
    tools: Toolbox
    outreach: bool = True  # write one sponsor pitch + one opener DM automatically


def event(node: str, message: str, **data: Any) -> dict[str, Any]:
    return {"events": [{"node": node, "message": message, **({"data": data} if data else {})}]}


def merge(*updates: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for u in updates:
        for k, v in u.items():
            out[k] = out.get(k, []) + v if k in ("events", "llm_calls") else v
    return out


# Only what the composer needs to choose and explain: Groq's free tier is 8k tokens/minute.
COMPOSE_FIELDS = {
    "venues": ("id", "name", "rating", "affinity"),
    "openers": ("id", "name", "badge", "fit"),
    "sponsors": ("id", "name", "uplift", "new_in_city"),
    "promo": ("id", "name", "kind"),
}


COMPOSE_TOP = 3  # candidates per category per city shown to the composer


def aliased(intel: dict[str, Any], cities: list[str]) -> tuple[dict[str, Any], dict[str, str]]:
    """Swap 36-char Qloo UUIDs for short aliases (c1v1 = city 1 venue 1, b2 = brand 2) and return alias → id.

    ~200 UUIDs made the composer prompt too large for Groq (HTTP 413); aliases cut it by more than half and are harder
    for a model to mangle. Code maps them back before validation, so an invented alias is still caught.
    """
    out: dict[str, Any] = {}
    to_id: dict[str, str] = {}
    brands: dict[str, str] = {}
    for i, city in enumerate(cities, 1):
        compact: dict[str, Any] = {}
        for key, fields in COMPOSE_FIELDS.items():
            rows = []
            for j, row in enumerate(intel.get(city, {}).get(key, [])[:COMPOSE_TOP], 1):
                if key == "sponsors":
                    alias = brands.setdefault(row["id"], f"b{len(brands) + 1}")
                else:
                    alias = f"c{i}{key[0]}{j}"
                to_id[alias] = row["id"]
                rows.append({**{f: row.get(f) for f in fields}, "id": alias})
            compact[key] = rows
        out[city] = compact
    return out, to_id


def dealias(brief: Brief, to_id: dict[str, str]) -> Brief:
    for stop in brief.stops:
        stop.venue_id = to_id.get(stop.venue_id, stop.venue_id)
        stop.opener_ids = [to_id.get(x, x) for x in stop.opener_ids]
        stop.sponsor_ids = [to_id.get(x, x) for x in stop.sponsor_ids]
        stop.promo_ids = [to_id.get(x, x) for x in stop.promo_ids]
    return brief


def build_graph(ctx: AgentContext, checkpointer: Any = None):  # type: ignore[no-untyped-def]
    llm, tools = ctx.llm, ctx.tools

    def calls_since(n: int) -> dict[str, Any]:
        return {"llm_calls": llm.usage()[n:]}

    # ------------------------------------------------------------ 1. intake

    async def intake(state: TourState) -> dict[str, Any]:
        n = len(llm.calls)
        if state.get("intake"):
            parsed = Intake.model_validate(state["intake"])
        else:
            parsed = await llm.json(Intake, prompt("intake", today=date.today().isoformat(), request=state["request"]),
                                    system=prompt("system"), tier="lite", purpose="intake")
        if not parsed.start_date:
            parsed.start_date = (date.today() + timedelta(days=DEFAULT_LEAD_DAYS)).isoformat()
        return merge({"intake": parsed.model_dump(), "attempts": 0, "violations": []},
                     event("intake", f"{parsed.artist}: {parsed.n_shows} shows in {', '.join(parsed.regions)}"),
                     calls_since(n))

    # ------------------------------------------------------------ 2. resolve + ⏸ confirm

    async def resolve(state: TourState) -> dict[str, Any]:
        found = await tools.resolve_artist(state["intake"]["artist"])
        exact = not found["needs_confirmation"]
        top = found["candidates"][0] if found["candidates"] else None
        msg = f"found {top['name']} on Qloo" if exact and top else "no exact match on Qloo"
        return merge({"candidates": found["candidates"][:5],
                      "artist": {"name": state["intake"]["artist"], "exact": exact}}, event("resolve", msg))

    async def confirm_artist(state: TourState) -> dict[str, Any]:
        exact = state["artist"]["exact"]
        candidates = state.get("candidates", [])
        if state.get("auto_approve"):
            answer = {"choice": candidates[0]["id"]} if exact else {"choice": None}
        else:
            answer = interrupt({
                "type": "confirm_artist",
                "question": "Is this you?" if exact else "We couldn't find an exact match. Is one of these you?",
                "candidates": candidates[:3],
                "sounds_like": state["intake"].get("sounds_like", []),
            })
        n = len(llm.calls)
        chosen = next((c for c in candidates if c["id"] == answer.get("choice")), None)
        if chosen:
            artist = {"name": chosen["name"], "id": chosen["id"], "on_qloo": True, "signal_ids": [chosen["id"]],
                      "signal_names": [chosen["name"]], "headliner_id": chosen["id"], "popularity": chosen["popularity"]}
            return merge({"artist": artist}, event("confirm_artist", f"using {chosen['name']}'s own taste data"))

        names = answer.get("sounds_like") or state["intake"].get("sounds_like") or []
        if not names:
            similar = await llm.json(SimilarArtists, prompt(
                "similar_artists", artist=state["intake"]["artist"], context=state.get("request") or "independent artist"),
                system=prompt("system"), tier="lite", purpose="similar_artists")
            names = similar.artists
        signals = []
        for name in names[:4]:
            res = await tools.resolve_artist(name)
            if res["candidates"] and not res["needs_confirmation"]:
                signals.append(res["candidates"][0])
        if not signals:
            raise ValueError(f"none of the similar artists {names} are on Qloo; try other names")
        smallest = min(signals, key=lambda c: c["popularity"] or 1)
        artist = {"name": state["intake"]["artist"], "id": None, "on_qloo": False,
                  "signal_ids": [c["id"] for c in signals], "signal_names": [c["name"] for c in signals],
                  "headliner_id": smallest["id"], "popularity": smallest["popularity"]}
        return merge({"artist": artist},
                     event("confirm_artist", f"not on Qloo: using the audience of {', '.join(artist['signal_names'])}"),
                     calls_since(n))

    # ------------------------------------------------------------ 3. reach

    async def reach(state: TourState) -> dict[str, Any]:
        n = len(llm.calls)
        try:
            rows, source = await ingest(llm, state.get("reach_input"))
        except (ValueError, LLMUnavailable) as exc:
            rows, source = [], f"failed: {exc}"
        mapped = to_metros(rows, state["intake"].get("past_cities", []), tools.metro)
        msg = f"reach from {source}: {len(mapped['listeners'])} cities, {len(mapped['played'])} played recently"
        return merge({"reach": {**mapped, "source": source}}, event("reach", msg), calls_since(n))

    # ------------------------------------------------------------ 4. demand + 5. score + ⏸ pick

    async def demand(state: TourState) -> dict[str, Any]:
        region = ", ".join(state["intake"]["regions"])
        result = await tools.demand_map(state["artist"]["signal_ids"], region)
        if not result["metros"]:
            raise ValueError(result.get("note") or f"no demand data for {region}")
        return merge({"metros": result["metros"]},
                     event("demand", f"{result['cells']} heatmap cells → {len(result['metros'])} metros"))

    def _labels(cities: list[str]) -> set[str]:
        return {m.label for m in (tools.metro(c) for c in cities) if m}

    async def score_node(state: TourState) -> dict[str, Any]:
        reach_data = state.get("reach", {})
        scores = score(state["metros"], reach_data.get("listeners"), set(reach_data.get("played", [])))
        intake_ = state["intake"]
        exclude = _labels(intake_.get("exclude_cities", [])) | set(state.get("no_venue_cities", []))
        include = _labels(intake_.get("include_cities", []))
        if state.get("swaps"):  # re-selecting after a venue swap: keep the cities that had venues
            include |= set(state.get("selected", [])) - exclude
        chosen = select_cities(scores, intake_["n_shows"], exclude=exclude, include=include)
        counts = {lab: sum(s.label == lab for s in chosen) for lab in ("unserved", "proven", "potential")}
        return merge({"metros": [s.as_dict() for s in scores], "selected": [s.metro for s in chosen]},
                     event("score", f"picked {len(chosen)} cities: {counts}"))

    async def pick_cities(state: TourState) -> dict[str, Any]:
        # Skip when there's no human, after a venue swap (the agent's own fix), or after a refine (the user just said
        # what they want).
        if state.get("auto_approve") or state.get("swaps") or state.get("refined"):
            return {"refined": False}
        # The suggested cities first (a proven anchor can rank below the top 20 on demand), then the best alternatives.
        suggested = [m for m in state["metros"] if m["metro"] in state["selected"]]
        alternatives = [m for m in state["metros"] if m["metro"] not in state["selected"]]
        rows = suggested + alternatives[: max(10, 20 - len(suggested))]
        answer = interrupt({
            "type": "pick_cities",
            "question": "These cities have the best mix of demand and reach. Change any?",
            "selected": state["selected"],
            "metros": [{k: m[k] for k in ("metro", "demand", "reach", "gap", "label")} for m in rows],
        })
        selected = [m for m in answer.get("selected", state["selected"]) if any(x["metro"] == m for x in state["metros"])]
        return merge({"selected": selected or state["selected"]}, event("pick_cities", f"{len(selected)} cities confirmed"))

    # ------------------------------------------------------------ 6. route

    async def route(state: TourState) -> dict[str, Any]:
        intake_ = state["intake"]
        by_label = {m["metro"]: m for m in state["metros"]}
        stops = [Stop(c, by_label[c]["lat"], by_label[c]["lon"], priority=by_label[c]["demand"] + max(by_label[c]["gap"], 0))
                 for c in state["selected"] if c in by_label]
        home_metro = tools.metro(intake_["home_base"])
        home = (home_metro.lat, home_metro.lon) if home_metro else (stops[0].lat, stops[0].lon)
        flying = intake_.get("max_drive_km", 600) == 0
        planned = plan_route(
            home, stops, date.fromisoformat(intake_["start_date"]),
            date.fromisoformat(intake_["end_date"]) if intake_.get("end_date") else None,
            max_drive_km=NO_DRIVE_LIMIT_KM if flying else intake_["max_drive_km"], return_home=not flying,
        )
        if not planned.stops:
            raise ValueError("no city fits the drive limit and dates; loosen max_drive_km or the window")
        msg = f"{len(planned.stops)} dates, {planned.total_km} km" + (f", dropped {len(planned.dropped)}" if planned.dropped else "")
        return merge({"route": planned.as_dict()}, event("route", msg))

    # ------------------------------------------------------------ 7. fan-out

    async def fanout(state: TourState) -> dict[str, Any]:
        from tourscout_mcp.tools import gather  # parallel helper shared with the MCP tools

        ids = state["artist"]["signal_ids"]
        cities = [s["metro"] for s in state["route"]["stops"]]
        notes: list[str] = []

        async def safe(label: str, coro: Any) -> Any:
            try:
                return await coro
            except Exception as exc:  # one city failing shouldn't sink the plan
                notes.append(f"{label}: {exc}")
                return None

        tasks = [lambda c=c: safe(f"venues {c}", tools.find_venues(ids, c)) for c in cities]
        tasks += [lambda c=c: safe(f"promo {c}", tools.find_promo_spots(ids, c)) for c in cities]
        tasks += [lambda: safe("openers", tools.find_openers(state["artist"]["headliner_id"], cities)),
                  lambda: safe("sponsors", tools.find_sponsors(ids, cities))]
        results = await gather(tasks)
        venues, promos = results[: len(cities)], results[len(cities) : 2 * len(cities)]
        openers, sponsors = results[-2] or {"cities": []}, results[-1] or {"national": [], "cities": []}

        opener_by = {c["city"]: c["openers"] for c in openers["cities"]}
        sponsor_by = {c["city"]: c["brands"] for c in sponsors["cities"]}
        intel = {}
        for city, v, p in zip(cities, venues, promos):
            promo = [{**s, "kind": kind} for kind, spots in ((p or {}).get("spots") or {}).items() for s in spots]
            intel[city] = {
                "venues": [{k: x.get(k) for k in ("id", "name", "address", "rating", "affinity")} for x in (v or {}).get("venues", [])],
                "openers": [{k: o.get(k) for k in ("id", "name", "badge", "home", "fit", "score", "popularity")}
                            for o in opener_by.get(city, [])],
                "sponsors": sponsor_by.get(city, []),
                "promo": [{k: x.get(k) for k in ("id", "name", "kind", "address")} for x in promo],
            }
        empty = [c for c in cities if not intel[c]["venues"]]
        msg = f"venues, openers, sponsors and promo spots for {len(cities)} cities"
        msg += (f"; no venues for {empty}" if empty else "") + (f"; {len(notes)} tool errors" if notes else "")
        update = {"intel": intel, "national_sponsors": sponsors["national"][:6]}
        if empty and state.get("swaps", 0) < MAX_VENUE_SWAPS:
            update["no_venue_cities"] = sorted(set(state.get("no_venue_cities", [])) | set(empty))
            update["swaps"] = state.get("swaps", 0) + 1
            msg += " → swapping them for the next best cities"
        else:
            update["swaps"] = 0  # done swapping (or out of swaps): continue with what we have
        return merge(update, event("fanout", msg, notes=notes))

    def after_fanout(state: TourState) -> str:
        return "score" if state.get("swaps") else "compose"

    # ------------------------------------------------------------ 8. compose ⇄ 9. validate

    def facts(state: TourState, aliases: dict[str, Any] | None = None) -> dict[str, Any]:
        by_label = {m["metro"]: m for m in state["metros"]}
        stops = state["route"]["stops"]
        return {
            "route": stops,
            "total_km": state["route"]["total_km"],
            "days_off": state["route"]["days_off"],
            "dropped": state["route"]["dropped"],
            "metros": [{k: by_label[s["metro"]].get(k) for k in ("metro", "label", "demand", "reach", "gap", "listeners", "population")}
                       for s in stops],
            "cities": aliases if aliases is not None else state["intel"],
        }

    async def compose(state: TourState) -> dict[str, Any]:
        n = len(llm.calls)
        attempts = state.get("attempts", 0) + 1
        artist = state["artist"]
        note = "" if artist["on_qloo"] else f" (not on Qloo; audience modelled on {', '.join(artist['signal_names'])})"
        feedback = ""
        if state.get("violations"):
            feedback = "Your previous answer broke these rules, fix them:\n- " + "\n- ".join(state["violations"][:8])
        cities, to_id = aliased(state["intel"], [s["metro"] for s in state["route"]["stops"]])
        try:
            brief = await llm.json(Brief, prompt("compose", artist=artist["name"], signal_note=note,
                                                 facts=dumps(facts(state, cities)), feedback=feedback),
                                   system=prompt("system"), purpose="compose", patience_s=COMPOSE_PATIENCE_S)
            update = {"brief": dealias(brief, to_id).model_dump(), "attempts": attempts}
        except LLMUnavailable as exc:
            update = {"brief": None, "attempts": MAX_COMPOSE_ATTEMPTS, "violations": [f"LLM unavailable: {exc}"]}
        return merge(update, event("compose", f"attempt {attempts}"), calls_since(n))

    async def validate(state: TourState) -> dict[str, Any]:
        if state.get("brief") is None:
            return event("validate", "no brief from the model; using the automatic plan")
        violations = validate_brief(Brief.model_validate(state["brief"]), state["route"], state["intel"], facts(state))
        msg = "grounded ✓" if not violations else f"{len(violations)} problems: {violations[0][:120]}"
        return merge({"violations": violations}, event("validate", msg))

    def after_validate(state: TourState) -> str:
        if state.get("brief") is not None and not state.get("violations"):
            return "outputs"
        return "compose" if state.get("attempts", 0) < MAX_COMPOSE_ATTEMPTS else "outputs"

    # ------------------------------------------------------------ 10. outputs

    async def outputs(state: TourState) -> dict[str, Any]:
        n = len(llm.calls)
        by_label = {m["metro"]: m for m in state["metros"]}
        auto = fallback_brief(state["artist"]["name"], state["route"], state["intel"], by_label)
        if state.get("brief") is None:
            brief, composed_by = auto, "fallback"
        elif not state.get("violations"):
            brief, composed_by = Brief.model_validate(state["brief"]), "llm"
        else:  # still breaking rules after the retries: keep what's grounded, replace the rest
            brief, replaced = salvage(Brief.model_validate(state["brief"]), auto, state["intel"], facts(state))
            composed_by = f"llm ({replaced} stops auto-filled)"
        plan = build_plan(state["artist"], brief, state["route"], state["intel"], by_label, grounded=True)
        plan["composed_by"] = composed_by
        plan["outreach"] = {}
        if ctx.outreach:
            from tourscout_mcp.tools import gather

            brand = next((b for s in plan["stops"] for b in s["sponsors"]), None)
            first = next((s for s in plan["stops"] if s["openers"]), None)

            async def pitch() -> None:
                if brand:
                    msg = await sponsor_pitch(llm, plan, brand["id"], state.get("national_sponsors", []))
                    plan["outreach"]["sponsor_pitch"] = {"brand": brand["name"], **msg.model_dump()}

            async def dm() -> None:
                if first:
                    msg = await opener_dm(llm, plan, first["metro"])
                    plan["outreach"]["opener_dm"] = {"opener": first["openers"][0]["name"], "city": first["metro"], **msg.model_dump()}

            async def safe(job) -> None:  # type: ignore[no-untyped-def]
                try:
                    await job()
                except (LLMUnavailable, ValueError) as exc:
                    plan["outreach"].setdefault("errors", []).append(str(exc))

            await gather([lambda: safe(pitch), lambda: safe(dm)])  # the two messages are independent: write them in parallel
        return merge({"plan": plan}, event("outputs", f"plan ready ({plan['composed_by']})"), calls_since(n))

    # ------------------------------------------------------------ refine

    async def refine(state: TourState) -> dict[str, Any]:
        n = len(llm.calls)
        ops = await parse_refine(llm, state.get("plan"), state["refine_request"])
        intake_ = dict(state["intake"])
        nxt = "route"
        if ops.regions:
            intake_["regions"], nxt = ops.regions, "demand"
        if ops.exclude_cities or ops.include_cities or ops.n_shows:
            intake_["exclude_cities"] = sorted(set(intake_.get("exclude_cities", [])) | set(ops.exclude_cities))
            intake_["include_cities"] = sorted(set(intake_.get("include_cities", [])) | set(ops.include_cities))
            intake_["n_shows"] = ops.n_shows or intake_["n_shows"]
            nxt = "demand" if nxt == "demand" else "score"
        for field in ("max_drive_km", "start_date", "end_date"):
            if getattr(ops, field) is not None:
                intake_[field] = getattr(ops, field)
        changed = ops.model_dump(exclude_defaults=True)
        return merge({"intake": intake_, "refine_request": "", "refine_next": nxt, "attempts": 0, "violations": [], "swaps": 0, "refined": True},
                     event("refine", f"{changed or 'no structured change'} → rerun from {nxt}"), calls_since(n))

    # ------------------------------------------------------------ wiring

    g = StateGraph(TourState)
    for name, fn in [("intake", intake), ("resolve", resolve), ("confirm_artist", confirm_artist), ("reach", reach),
                     ("demand", demand), ("score", score_node), ("pick_cities", pick_cities), ("route", route),
                     ("fanout", fanout), ("compose", compose), ("validate", validate), ("outputs", outputs),
                     ("refine", refine)]:
        g.add_node(name, fn)
    g.add_conditional_edges(START, lambda s: "refine" if s.get("refine_request") else "intake", ["refine", "intake"])
    for a, b in [("intake", "resolve"), ("resolve", "confirm_artist"), ("confirm_artist", "reach"), ("reach", "demand"),
                 ("demand", "score"), ("score", "pick_cities"), ("pick_cities", "route"), ("route", "fanout"),
                 ("compose", "validate"), ("outputs", END)]:
        g.add_edge(a, b)
    g.add_conditional_edges("fanout", after_fanout, ["score", "compose"])
    g.add_conditional_edges("validate", after_validate, ["compose", "outputs"])
    g.add_conditional_edges("refine", lambda s: s["refine_next"], ["demand", "score", "route"])
    return g.compile(checkpointer=checkpointer)
