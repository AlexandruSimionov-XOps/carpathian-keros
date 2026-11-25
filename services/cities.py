"""Registry of Romania's 319 official cities and towns (data/cities_ro.json).

Only places on this list can be queried. The list is built by scripts/build_cities.py from
https://ro.wikipedia.org/wiki/Lista_orașelor_din_România, with coordinates from Open-Meteo Geocoding.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "cities_ro.json"
MAX_QUERY_LENGTH = 100

# English exonyms people commonly type. Keys are folded.
ALIASES = {"bucharest": "bucuresti"}


def fold(text: str) -> str:
    """Case-, diacritic- and hyphen-insensitive key: 'Slănic-Moldova' == 'slanic moldova'."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.replace("-", " ").split())


@dataclass(frozen=True)
class City:
    name: str
    county: str | None  # None only for București
    population: int | None
    county_seat: bool
    latitude: float
    longitude: float
    elevation: float | None
    query: str  # canonical query string: "Name", or "Name, County" when the name is shared

    def location(self) -> dict[str, Any]:
        if self.county:
            region = {"ro": f"Județul {self.county}", "en": f"{self.county} County"}
        else:
            region = {"ro": "Municipiul București", "en": "Bucharest Municipality"}
        return {
            "name": self.name,
            "query": self.query,
            "county": self.county,
            "region": region,
            "country": {"ro": "România", "en": "Romania"},
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
        }

    def suggestion(self) -> dict[str, Any]:
        return {"name": self.name, "county": self.county, "population": self.population, "query": self.query}


class CityRegistry:
    def __init__(self, path: Path = DATA_FILE):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.source = raw.get("source")
        rows = raw["cities"]
        name_counts: dict[str, int] = {}
        for row in rows:
            name_counts[fold(row["name"])] = name_counts.get(fold(row["name"]), 0) + 1

        self.cities: list[City] = []
        self._by_name: dict[str, list[City]] = {}
        for row in rows:
            shared = name_counts[fold(row["name"])] > 1
            city = City(
                name=row["name"],
                county=row["county"],
                population=row.get("population"),
                county_seat=bool(row.get("county_seat")),
                latitude=row["latitude"],
                longitude=row["longitude"],
                elevation=row.get("elevation"),
                query=f"{row['name']}, {row['county']}" if shared else row["name"],
            )
            self.cities.append(city)
            self._by_name.setdefault(fold(city.name), []).append(city)
        # Most populous first, so an unqualified shared name ("Ștefănești") picks the larger town.
        for matches in self._by_name.values():
            matches.sort(key=lambda c: -(c.population or 0))

    def __len__(self) -> int:
        return len(self.cities)

    def resolve(self, query: str) -> City | None:
        """Exact (folded) lookup. Accepts 'Name', 'Name, County' or 'Name (County)'."""
        query = (query or "").strip()
        if not query or len(query) > MAX_QUERY_LENGTH:
            return None
        county = None
        if m := re.fullmatch(r"(.+?)\s*(?:,\s*|\()\s*(?:jud(?:etul|ețul|\.)?\s+)?([^,()]+?)\s*\)?", query, re.I):
            query, county = m.group(1), m.group(2)
        key = fold(query)
        matches = self._by_name.get(ALIASES.get(key, key), [])
        if county:
            county_key = fold(county).removesuffix(" county")
            matches = [c for c in matches if c.county and fold(c.county) == county_key]
        return matches[0] if matches else None

    def suggestions(self) -> list[dict[str, Any]]:
        return [c.suggestion() for c in self.cities]


city_registry = CityRegistry()
