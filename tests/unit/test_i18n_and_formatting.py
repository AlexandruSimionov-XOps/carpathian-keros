"""Backend i18n tables and number formatting (the PDF's rounding rules)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.i18n import LABELS, SUPPORTED_LANGS, WEEKDAYS, WMO_CODES, normalize_lang, wmo_label
from services.pdf_service import _fmt_num, _fmt_temp

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (3.4, "3"),
        (3.5, "4"),
        (3.6, "4"),
        (-3.4, "-3"),
        (-3.5, "-4"),  # half away from zero, symmetric around 0
        (2.5, "3"),  # regression: Python's round() is banker's rounding (round(2.5) == 2)
        (-0.4, "0"),  # never "-0"
        (0.5, "1"),
        (12.49, "12"),
    ],
)
def test_temperatures_are_whole_degrees_rounded_half_away_from_zero(value, expected):
    assert _fmt_temp(value, "en") == expected


def test_other_numbers_keep_their_decimals_and_romanian_uses_a_comma():
    assert _fmt_num(6.45, "en") == "6.5"
    assert _fmt_num(6.45, "ro") == "6,5"
    assert _fmt_num(None, "en") == "–"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en", "en"),
        ("ro", "ro"),
        ("RO", "ro"),
        (" ro ", "ro"),
        ("de", "en"),
        ("", "en"),
        (None, "en"),
        ("<script>", "en"),
    ],
)
def test_normalize_lang_allow_lists_and_falls_back_to_english(raw, expected):
    assert normalize_lang(raw) == expected


def test_wmo_labels_cover_both_languages_and_unknown_codes():
    assert wmo_label(81, "ro") == "Averse de ploaie"
    assert wmo_label(2, "en") == "Partly cloudy"
    assert wmo_label(1234, "ro") == "Necunoscut"
    assert all(set(v) == set(SUPPORTED_LANGS) for v in WMO_CODES.values())


def test_label_tables_have_identical_keys_per_language():
    assert set(LABELS["en"]) == set(LABELS["ro"])
    assert all(len(WEEKDAYS[lang]) == 7 for lang in SUPPORTED_LANGS)


def test_wmo_tables_are_identical_in_python_and_javascript():
    """Invariant: the WMO dictionary is duplicated on purpose and must never drift (AGENTS.md rule 3)."""
    js = (ROOT / "static/js/i18n.js").read_text(encoding="utf-8")
    js_wmo = {
        int(code): {"en": en, "ro": ro}
        for code, en, ro in re.findall(r'^\s*(\d+): \{ en: "([^"]+)", ro: "([^"]+)" \},$', js, re.M)
    }
    assert js_wmo == WMO_CODES


@pytest.mark.parametrize("path", ["services/i18n.py", "static/js/i18n.js", "templates/index.html", "app.py"])
def test_romanian_text_uses_comma_below_not_cedilla(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert not set(text) & set("şŞţŢ"), f"cedilla ş/ţ found in {path}"
