"""Heatmap cells → metros.

Qloo heatmap cells are geohash squares with an affinity (taste match, 0–1) and a popularity (Qloo activity, 0–1). Musicians
think in cities, so we group GeoNames cities into metros and roll cells up to the nearest one:

1. Metros: walk cities from largest to smallest; a city within a bigger city's radius joins it (Evanston → Chicago),
   otherwise it starts its own metro. Small college towns far from big cities (Athens OH) stay separate on purpose.
2. Cells: each cell joins the metro with the strongest pull (population / distance²) within MAX_CELL_KM.
3. Per metro: popularity-weighted mean affinity, summed popularity (an audience-size proxy) and the cell count.
"""

from __future__ import annotations

import math
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_CELL_KM = 50.0
GRAVITY_SOFTENING_KM = 5.0
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def metro_radius_km(population: int) -> float:
    if population >= 2_000_000:
        return 55.0
    if population >= 1_000_000:
        return 40.0
    if population >= 250_000:
        return 25.0
    return 12.0


def decode_geohash(geohash: str) -> tuple[float, float]:
    """Centre of a geohash cell."""
    lat, lon = [-90.0, 90.0], [-180.0, 180.0]
    even = True
    for char in geohash.lower():
        bits = BASE32.index(char)
        for shift in range(4, -1, -1):
            interval = lon if even else lat
            mid = (interval[0] + interval[1]) / 2
            interval[0 if bits >> shift & 1 else 1] = mid
            even = not even
    return (lat[0] + lat[1]) / 2, (lon[0] + lon[1]) / 2


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def fold(text: str) -> str:
    """Case- and accent-insensitive key: 'Bengaluru' == 'bengaluru', 'Zürich' == 'zurich'."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold().strip()


@dataclass(frozen=True)
class City:
    name: str
    country: str
    admin1: str
    lat: float
    lon: float
    population: int
    alternate_names: tuple[str, ...] = ()


@dataclass
class Metro:
    name: str
    country: str
    admin1: str
    lat: float
    lon: float
    population: int
    radius_km: float
    members: set[str] = field(default_factory=set)  # folded names of the cities it absorbed (incl. its own)

    @property
    def label(self) -> str:
        # GeoNames admin1 is the state code for the US ("IL"); elsewhere it's numeric, so show the country instead.
        return f"{self.name}, {self.admin1}" if self.country == "US" else f"{self.name}, {self.country}"


def load_cities(path: Path, min_population: int = 15_000) -> list[City]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: uv run data/download_geonames.py")
    cities = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            col = line.rstrip("\n").split("\t")
            population = int(col[14] or 0)
            if population < min_population:
                continue
            alternates = tuple(n for n in col[3].split(",") if n and n.isascii())[:20]
            cities.append(City(col[1], col[8], col[10], float(col[4]), float(col[5]), population, alternates))
    return cities


class _Grid:
    """1° buckets so nearest-neighbour lookups don't scan every city."""

    def __init__(self) -> None:
        self.buckets: dict[tuple[int, int], list[Metro]] = defaultdict(list)

    def add(self, metro: Metro) -> None:
        self.buckets[(math.floor(metro.lat), math.floor(metro.lon))].append(metro)

    def near(self, lat: float, lon: float, km: float) -> Iterable[Metro]:
        dlat = math.ceil(km / 111.0)
        dlon = math.ceil(km / (111.0 * max(math.cos(math.radians(lat)), 0.2)))
        base_lat, base_lon = math.floor(lat), math.floor(lon)
        for i in range(-dlat, dlat + 1):
            for j in range(-dlon, dlon + 1):
                yield from self.buckets.get((base_lat + i, (base_lon + j + 180) % 360 - 180), ())


class MetroIndex:
    def __init__(self, cities: Iterable[City]) -> None:
        self.metros: list[Metro] = []
        self._grid = _Grid()
        self._names: dict[str, list[tuple[int, Metro]]] = defaultdict(list)
        for city in sorted(cities, key=lambda c: c.population, reverse=True):
            host = self._host(city.lat, city.lon)
            if host is None:
                host = Metro(
                    city.name, city.country, city.admin1, city.lat, city.lon,
                    0, metro_radius_km(city.population),
                )
                self.metros.append(host)
                self._grid.add(host)
            host.population += city.population
            host.members |= {fold(city.name), *(fold(n) for n in city.alternate_names)}
            # Lookup priority: a metro's own name, then the cities it absorbed, then alternate names.
            rank = 0 if host.name == city.name else 1
            self._names[fold(city.name)].append((rank, host))
            for alt in city.alternate_names:
                self._names[fold(alt)].append((2, host))

    @classmethod
    def from_file(cls, path: Path) -> "MetroIndex":
        return cls(load_cities(path))

    def _host(self, lat: float, lon: float) -> Metro | None:
        hosts = [m for m in self._grid.near(lat, lon, 55.0) if haversine_km((lat, lon), (m.lat, m.lon)) <= m.radius_km]
        return max(hosts, key=lambda m: m.population, default=None)

    def nearest(self, lat: float, lon: float, max_km: float = MAX_CELL_KM) -> Metro | None:
        """The metro with the strongest pull on a point within max_km: population / (distance + 5 km)².

        Pure nearest-centre handed Bengaluru's outskirts to small towns 5 km away (Channapatna, 70k) instead of the
        9.8M city 45 km away; gravity keeps a big city's edge cells with the big city.
        """
        best, best_pull = None, 0.0
        for metro in self._grid.near(lat, lon, max_km):
            km = haversine_km((lat, lon), (metro.lat, metro.lon))
            if km > max_km:
                continue
            pull = metro.population / (km + GRAVITY_SOFTENING_KM) ** 2
            if pull > best_pull:
                best, best_pull = metro, pull
        return best

    def find(self, name: str, country: str | None = None) -> Metro | None:
        """Metro for a city name ('Chicago', 'Evanston', 'Chicago, IL'); the biggest one wins if the name is ambiguous."""
        city, _, region = (part.strip() for part in name.partition(","))
        region = region.upper()
        matches = [
            (rank, m)
            for rank, m in self._names.get(fold(city), [])
            if (country is None or m.country == country.upper()) and (not region or region in (m.admin1, m.country))
        ]
        best = min(matches, key=lambda rm: (rm[0], -rm[1].population), default=None)
        return best[1] if best else None


@dataclass
class MetroDemand:
    metro: Metro
    affinity: float  # popularity-weighted mean affinity of its cells
    activity: float  # summed cell popularity
    cells: int


def cell_point(cell: dict[str, Any]) -> tuple[float, float] | None:
    loc = cell.get("location") or {}
    if loc.get("latitude") is not None and loc.get("longitude") is not None:
        return float(loc["latitude"]), float(loc["longitude"])
    if loc.get("geohash"):
        return decode_geohash(loc["geohash"])
    return None


def aggregate_cells(cells: Iterable[dict[str, Any]], index: MetroIndex) -> tuple[list[MetroDemand], int]:
    """Roll heatmap cells up into metros. Returns (metros, number of cells that matched no metro)."""
    sums: dict[int, list[float]] = {}  # id(metro) → [Σ aff·pop, Σ pop, n]
    metros: dict[int, Metro] = {}
    unmapped = 0
    for cell in cells:
        point = cell_point(cell)
        query = cell.get("query") or {}
        aff, pop = query.get("affinity"), query.get("popularity")
        if point is None or aff is None or pop is None:
            unmapped += 1
            continue
        metro = index.nearest(*point)
        if metro is None:
            unmapped += 1
            continue
        acc = sums.setdefault(id(metro), [0.0, 0.0, 0])
        acc[0] += aff * pop
        acc[1] += pop
        acc[2] += 1
        metros[id(metro)] = metro
    out = [
        MetroDemand(metros[k], round(a / p, 4) if p else 0.0, round(p, 3), int(n))
        for k, (a, p, n) in sums.items()
    ]
    return out, unmapped
