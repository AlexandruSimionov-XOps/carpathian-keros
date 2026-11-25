"""City registry: the allow-list is the security and product boundary for which places can be queried."""

from __future__ import annotations

import json

import pytest

from services.cities import DATA_FILE, CityRegistry, fold

LAT_RANGE, LON_RANGE = (43.5, 48.4), (20.1, 29.8)


def test_registry_has_all_319_official_cities(registry):
    assert len(registry) == 319


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Iași", "Iași"),
        ("iasi", "Iași"),
        ("IASI", "Iași"),
        ("  Iași  ", "Iași"),
        ("cluj napoca", "Cluj-Napoca"),  # hyphen-insensitive
        ("targu-mures", "Târgu Mureș"),
        ("Slanic-Moldova", "Slănic Moldova"),  # Wikipedia spells it both ways
        ("Bucharest", "București"),  # English alias
        ("bucuresti", "București"),
        ("Ștefănești", "Ștefănești, Argeș"),  # shared name → more populous town
        ("Stefanesti, Botosani", "Ștefănești, Botoșani"),
        ("Ștefănești (jud. Botoșani)", "Ștefănești, Botoșani"),
        ("Stefanesti, Botosani County", "Ștefănești, Botoșani"),
    ],
)
def test_resolve_accepts_every_documented_form(registry, query, expected):
    city = registry.resolve(query)
    assert city is not None
    assert city.query == expected


@pytest.mark.parametrize(
    "query",
    [
        "Atlantis",  # regression: the misspelled `country_code` filter returned a town in South Africa
        "Paris",  # regression: live geocoding fuzzily matched the village Parisești
        "Parisești",  # village, not a city
        "Florești",  # commune, not a city
        "Cluj",  # partial names never match on the server
        "Stefanesti, Cluj",  # real name, wrong county
        "",
        "   ",
        "x" * 101,
    ],
)
def test_resolve_rejects_anything_not_on_the_list(registry, query):
    assert registry.resolve(query) is None


def test_shared_names_get_county_qualified_queries(registry):
    queries = {c.query for c in registry.cities if c.name == "Ștefănești"}
    assert queries == {"Ștefănești, Argeș", "Ștefănești, Botoșani"}
    assert all(c.query == c.name for c in registry.cities if c.name != "Ștefănești")


def test_location_labels_are_bilingual(registry):
    cluj = registry.resolve("Cluj-Napoca").location()
    assert cluj["region"] == {"ro": "Județul Cluj", "en": "Cluj County"}
    assert cluj["country"] == {"ro": "România", "en": "Romania"}
    assert cluj["county"] == "Cluj"
    bucuresti = registry.resolve("București").location()
    assert bucuresti["county"] is None
    assert bucuresti["region"] == {"ro": "Municipiul București", "en": "Bucharest Municipality"}


def test_suggestions_expose_only_the_public_fields(registry):
    suggestions = registry.suggestions()
    assert len(suggestions) == 319
    assert set(suggestions[0]) == {"name", "county", "population", "query"}


def test_fold_is_case_diacritic_and_hyphen_insensitive():
    assert fold("Slănic-Moldova") == fold("slanic  moldova") == "slanic moldova"
    assert fold("ȘȚĂÎÂ") == "staia"


def test_registry_can_load_an_injected_file(tmp_path):
    data = {
        "source": "test",
        "cities": [
            {
                "name": "Testești",
                "county": "Alba",
                "population": 1,
                "county_seat": False,
                "latitude": 46.0,
                "longitude": 23.0,
                "elevation": None,
            }
        ],
    }
    path = tmp_path / "cities.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    reg = CityRegistry(path)
    assert len(reg) == 1
    assert reg.resolve("testesti").name == "Testești"


@pytest.fixture(scope="module")
def rows():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))["cities"]


class TestDataIntegrity:
    """Guards for data/cities_ro.json, which is generated and never hand-edited (Article II)."""

    def test_coordinates_are_inside_romania(self, rows):
        outside = [
            r["name"]
            for r in rows
            if not (LAT_RANGE[0] <= r["latitude"] <= LAT_RANGE[1] and LON_RANGE[0] <= r["longitude"] <= LON_RANGE[1])
        ]
        assert outside == []

    def test_names_use_comma_below_not_cedilla(self, rows):
        assert [r["name"] for r in rows if set(r["name"] + (r["county"] or "")) & set("şŞţŢ")] == []

    def test_name_and_county_pairs_are_unique(self, rows):
        pairs = [(fold(r["name"]), r["county"]) for r in rows]
        assert len(pairs) == len(set(pairs))

    def test_every_county_is_represented_with_one_seat(self, rows):
        counties = {r["county"] for r in rows if r["county"]}
        assert len(counties) == 41
        seats = [r for r in rows if r["county_seat"]]
        assert len(seats) == 41
        assert {r["county"] for r in seats} == counties

    def test_attribution_metadata_is_present(self):
        meta = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        assert "wikipedia.org" in meta["source"]
        assert "CC BY-SA" in meta["license"]
