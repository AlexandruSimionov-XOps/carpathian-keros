"""Build data/cities_ro.json: the official list of Romania's 319 cities and towns (orașe + municipii).

Source: https://ro.wikipedia.org/wiki/Lista_orașelor_din_România (CC BY-SA 4.0)
Coordinates: Open-Meteo Geocoding API, matched on city name + county.

Usage:  .venv/bin/python scripts/build_cities.py [--wikitext saved_page.wiki]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

WIKI_PAGE = "Lista orașelor din România"
WIKI_API = "https://ro.wikipedia.org/w/api.php"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OUT = Path(__file__).resolve().parent.parent / "data" / "cities_ro.json"
EXPECTED_COUNT = 319
# County seats the Wikipedia table doesn't bold (Buftea is the seat of Ilfov).
EXTRA_COUNTY_SEATS = {"Buftea"}
# Rough bounding box of Romania, used to sanity-check coordinates.
LAT_RANGE, LON_RANGE = (43.5, 48.4), (20.1, 29.8)

HEADERS = {"User-Agent": "CarpathianKeros-build/1.0"}

# ~640 requests in one run: retry transient timeouts / 429 / 5xx with backoff instead of aborting.
SESSION = requests.Session()
SESSION.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
    ),
)
_CEDILLA = str.maketrans({"ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț"})
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.replace("-", " ").split())


def county_key(admin1: str) -> str:
    """'Județul Brașov' (ro) and 'Brașov County' (en) both become 'brasov'."""
    key = fold(admin1)
    return key.removeprefix("judetul ").removesuffix(" county")


def fetch_wikitext() -> str:
    resp = SESSION.get(
        WIKI_API,
        params={
            "action": "parse",
            "page": WIKI_PAGE,
            "prop": "wikitext",
            "format": "json",
            "formatversion": 2,
        },
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["parse"]["wikitext"]


def parse_table(wiki: str) -> list[dict]:
    """The sortable table: Oraș | Județ | Populație (2021) | ... Bold names are county seats."""
    table = wiki[wiki.index('{|class="wikitable sortable"') :]
    table = table[: table.index("\n|}")]
    cities = []
    for row in re.split(r"\n\|-[^\n]*", table)[1:]:
        cells = [c.strip() for c in re.split(r"\n\|", "\n" + row.strip())][1:]
        if len(cells) < 3 or not (m := _LINK.search(cells[0])):
            continue
        name = (m.group(2) or m.group(1)).strip().translate(_CEDILLA)
        county_m = _LINK.search(cells[1])
        county = (county_m.group(2) or county_m.group(1)).strip().translate(_CEDILLA) if county_m else None
        population = re.sub(r"\D", "", re.sub(r"<ref.*", "", cells[2]).split("|")[-1])
        cities.append(
            {
                "name": name,
                "county": county,
                "population": int(population) if population else None,
                "county_seat": cells[0].startswith("'''") and county is not None,
            }
        )
    return cities


def parse_alphabetical(wiki: str) -> list[str]:
    """The alphabetical list further down the page; used to catch rows missing from the table."""
    section = wiki[wiki.index("== Lista alfabetică") :]
    names = []
    for target, label in re.findall(r"^# \[\[([^\]|]+)(?:\|([^\]]+))?\]\]", section, re.M):
        # Unlabelled links are article titles such as "Ștefănești, Argeș" or "Vulcan (oraș)".
        name = label or re.sub(r"\s*\(.*\)$|,.*$", "", target)
        names.append(name.strip().translate(_CEDILLA))
    return list(dict.fromkeys(names))


def geocode(name: str, county: str | None) -> dict | None:
    # Some GeoNames entries carry Cyrillic names under language=ro (e.g. Codlea → "Кодля"); retry in English.
    for language in ("ro", "en"):
        if hit := _geocode(name, county, language):
            return hit
    return None


def _geocode(name: str, county: str | None, language: str) -> dict | None:
    resp = SESSION.get(
        GEOCODING_URL,
        params={
            "name": name,
            "count": 20,
            "language": language,
            "countryCode": "RO",
            "format": "json",
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    results = [
        r
        for r in resp.json().get("results") or []
        if r.get("country_code") == "RO"
        and r.get("feature_code", "").startswith("PPL")
        and fold(r["name"]) == fold(name)
    ]
    if county:
        results = [r for r in results if county_key(r.get("admin1", "")) == fold(county)]
    if not results:
        return None
    # Prefer administrative seats, then the most populous match.
    results.sort(key=lambda r: (not r["feature_code"].startswith("PPLA"), -(r.get("population") or 0)))
    return results[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wikitext", type=Path, help="use a saved wikitext file instead of downloading")
    args = ap.parse_args()

    wiki = args.wikitext.read_text(encoding="utf-8") if args.wikitext else fetch_wikitext()
    cities = parse_table(wiki)
    for city in cities:
        city["county_seat"] = city["county_seat"] or city["name"] in EXTRA_COUNTY_SEATS
    known = {fold(c["name"]) for c in cities}
    for name in parse_alphabetical(wiki):
        if fold(name) not in known:  # e.g. Sebiș, Turceni are absent from the table
            print(f"  + {name}: only in the alphabetical list, county taken from geocoder")
            cities.append(
                {"name": name, "county": None, "population": None, "county_seat": False, "_needs_county": True}
            )
            known.add(fold(name))

    failures = []
    for i, city in enumerate(cities, 1):
        hit = geocode(city["name"], city["county"])
        if not hit:
            failures.append(city["name"])
            continue
        if city.pop("_needs_county", False):
            city["county"] = hit.get("admin1", "").translate(_CEDILLA).removeprefix("Județul ").removesuffix(" County")
            city["population"] = hit.get("population")
        city["latitude"] = round(hit["latitude"], 5)
        city["longitude"] = round(hit["longitude"], 5)
        city["elevation"] = hit.get("elevation")
        if not (LAT_RANGE[0] <= city["latitude"] <= LAT_RANGE[1] and LON_RANGE[0] <= city["longitude"] <= LON_RANGE[1]):
            failures.append(f"{city['name']} (coordinates outside Romania)")
        if i % 50 == 0:
            print(f"  geocoded {i}/{len(cities)}")
        time.sleep(0.12)  # stay well under Open-Meteo's rate limits

    if failures:
        print("FAILED:", failures, file=sys.stderr)
        return 1
    if len(cities) != EXPECTED_COUNT:
        print(f"WARNING: expected {EXPECTED_COUNT} cities, got {len(cities)}", file=sys.stderr)

    cities.sort(key=lambda c: fold(c["name"]))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "source": "https://ro.wikipedia.org/wiki/Lista_ora%C8%99elor_din_Rom%C3%A2nia",
                "license": "CC BY-SA 4.0 (Wikipedia); coordinates from Open-Meteo Geocoding (GeoNames, CC BY 4.0)",
                "retrieved": date.today().isoformat(),
                "count": len(cities),
                "cities": cities,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cities)} cities to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
