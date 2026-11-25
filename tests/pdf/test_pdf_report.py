"""PDF report: one page, both languages, diacritics, whole-degree temperatures and the no-font fallback."""

from __future__ import annotations

import io
import re

import pytest
from pypdf import PdfReader

from services.pdf_service import build_report


@pytest.fixture
def weather(service):
    return service.get_weather("Brașov")


def _text(pdf: bytes) -> tuple[int, str]:
    reader = PdfReader(io.BytesIO(pdf))
    return len(reader.pages), "\n".join(page.extract_text() for page in reader.pages)


@pytest.mark.parametrize(
    ("lang", "phrases"),
    [
        ("en", ["Weather Report", "Current conditions", "Next 24 hours", "7-day forecast", "Brașov County"]),
        ("ro", ["Raport meteo", "Condiții actuale", "Următoarele 24 de ore", "Prognoză pe 7 zile", "Județul Brașov"]),
    ],
)
def test_report_is_one_localized_page_with_diacritics(weather, lang, phrases):
    pages, text = _text(build_report(weather, lang))
    assert pages == 1
    assert "Carpathian Keros" in text
    assert "Brașov" in text
    for phrase in phrases:
        assert phrase in text


def test_temperatures_are_printed_as_whole_degrees(weather):
    weather["current"]["temperature"] = 3.5
    weather["current"]["feels_like"] = -3.5
    _, text = _text(build_report(weather, "en"))
    temps = re.findall(r"(-?\d+(?:[.,]\d+)?) °C", text)
    assert temps, "no temperatures found"
    assert all(re.fullmatch(r"-?\d+", t) for t in temps), temps
    assert "4 °C" in text and "-4 °C" in text


def test_attribution_is_in_the_footer(weather):
    _, text = _text(build_report(weather, "ro"))
    assert "Open-Meteo.com (CC BY 4.0)" in text


def test_missing_unicode_font_falls_back_without_crashing(weather):
    """No TTF available → core Helvetica with transliteration, never FPDFUnicodeEncodingException."""
    pdf = build_report(weather, "ro", font_paths=None)
    pages, text = _text(pdf)
    assert pages == 1
    assert "Brasov" in text and "Conditii actuale" in text
