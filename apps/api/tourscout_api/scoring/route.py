"""Order the chosen cities into a drivable tour and put dates on it.

Nearest-neighbour from the home base, then 2-opt to remove crossings. Distance = haversine × ROAD_FACTOR (roads aren't
straight; 1.25 is a common rule of thumb for US interstates). Then a calendar: one show per day, a travel day before
any leg longer than max_drive_km, a rest day after every REST_EVERY shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from tourscout_mcp.geo import haversine_km

ROAD_FACTOR = 1.25
REST_EVERY = 5
MAX_LEG_MULTIPLE = 2.0  # a leg longer than 2 × max_drive_km means the city doesn't belong on this run


@dataclass
class Stop:
    metro: str
    lat: float
    lon: float
    priority: float = 0.0  # used to decide which city to drop when the route breaks a limit


@dataclass
class ScheduledStop:
    metro: str
    date: str
    drive_km: int
    travel_day_before: bool = False


@dataclass
class Route:
    stops: list[ScheduledStop]
    total_km: int
    days_off: list[str] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stops": [s.__dict__ for s in self.stops],
            "total_km": self.total_km,
            "days_off": self.days_off,
            "dropped": self.dropped,
        }


def road_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return haversine_km(a, b) * ROAD_FACTOR


def _path_km(points: list[tuple[float, float]]) -> float:
    return sum(road_km(points[i], points[i + 1]) for i in range(len(points) - 1))


def order_stops(home: tuple[float, float], stops: list[Stop], return_home: bool = True) -> list[Stop]:
    """Nearest-neighbour tour from home, improved by 2-opt. Home itself is not a stop."""
    remaining, ordered, here = list(stops), [], home
    while remaining:
        nxt = min(remaining, key=lambda s: road_km(here, (s.lat, s.lon)))
        ordered.append(nxt)
        remaining.remove(nxt)
        here = (nxt.lat, nxt.lon)

    def cost(route: list[Stop]) -> float:
        pts = [home, *((s.lat, s.lon) for s in route)] + ([home] if return_home else [])
        return _path_km(pts)

    improved = True
    while improved:
        improved = False
        for i in range(len(ordered) - 1):
            for j in range(i + 1, len(ordered)):
                candidate = ordered[:i] + ordered[i : j + 1][::-1] + ordered[j + 1 :]
                if cost(candidate) < cost(ordered) - 1e-6:
                    ordered, improved = candidate, True
    return ordered


def plan_route(
    home: tuple[float, float],
    stops: list[Stop],
    start: date,
    end: date | None = None,
    max_drive_km: float = 600,
    return_home: bool = True,
) -> Route:
    """Order, enforce limits (dropping the lowest-priority city if needed) and schedule."""
    stops, dropped = list(stops), []
    while stops:
        ordered = order_stops(home, stops, return_home)
        legs = _legs(home, ordered)
        # Leg 0 is the drive from home to the first show: a band can set off a day or two early, so it never
        # disqualifies a city (Phase 4: an Austin-based band's Midwest tour lost every city to this).
        too_long = [i for i, km in enumerate(legs) if i > 0 and km > MAX_LEG_MULTIPLE * max_drive_km]
        schedule = _schedule(ordered, legs, start, max_drive_km)
        over_window = end is not None and schedule.stops and date.fromisoformat(schedule.stops[-1].date) > end
        if not too_long and not over_window:
            schedule.dropped = dropped
            return schedule
        # Drop the lowest-priority city among those causing the problem (or overall if the window is the problem).
        suspects = [ordered[i] for i in too_long] or ordered
        worst = min(suspects, key=lambda s: s.priority)
        stops.remove(worst)
        reason = "window too short" if not too_long else f"leg over {MAX_LEG_MULTIPLE:g}× max drive ({max_drive_km:g} km)"
        dropped.append({"metro": worst.metro, "reason": reason})
    return Route([], 0, [], dropped)


def _legs(home: tuple[float, float], ordered: list[Stop]) -> list[float]:
    points = [home, *((s.lat, s.lon) for s in ordered)]
    return [road_km(points[i], points[i + 1]) for i in range(len(points) - 1)]


def _schedule(ordered: list[Stop], legs: list[float], start: date, max_drive_km: float) -> Route:
    day, out, days_off, streak = start, [], [], 0
    for i, (stop, km) in enumerate(zip(ordered, legs)):
        travel = i > 0 and km > max_drive_km  # the first leg is from home: assume they leave early
        if travel:
            days_off.append(day.isoformat())
            day += timedelta(days=1)
            streak = 0
        elif streak == REST_EVERY:
            days_off.append(day.isoformat())
            day += timedelta(days=1)
            streak = 0
        out.append(ScheduledStop(stop.metro, day.isoformat(), round(km), travel))
        day += timedelta(days=1)
        streak += 1
    return Route(out, round(sum(legs)), days_off)
