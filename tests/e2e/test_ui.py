"""Browser tests against a live server. Opt-in: they need Playwright + Chromium and network access to
Open-Meteo and the CDNs.

    pip install playwright && playwright install chromium
    CK_E2E=1 pytest -m e2e
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(os.environ.get("CK_E2E") != "1", reason="set CK_E2E=1 to run browser tests"),
]
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def base_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "HOST": "127.0.0.1", "PORT": str(port)}
    proc = subprocess.Popen(
        [sys.executable, "app.py"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(url, timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def page(base_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and "404" not in m.text and pg.errors.append(m.text))
        pg.goto(base_url, wait_until="load")
        # `expect` polls without eval(); wait_for_function("...") would be blocked by our strict CSP (no 'unsafe-eval').
        sync_api.expect(pg.locator("#loc-name")).not_to_have_text("—", timeout=15000)
        pg.expect = sync_api.expect
        yield pg
        browser.close()


def test_presets_in_order_and_footer_credit(page):
    labels = page.eval_on_selector_all(".preset-chip", "els => els.map(e => e.dataset.city)")
    assert labels == ["București", "Cluj-Napoca", "Constanța", "Iași", "Oradea", "Timișoara"]
    assert page.get_attribute("footer a", "href") == "https://github.com/AlexandruSimionov-XOps"


def test_no_errors_after_city_and_language_changes(page):
    """Regression: grouped ApexCharts threw on updateOptions() without updateSyncedCharts=false.
    Also catches CSP violations: the browser reports them as console errors."""
    page.click('.preset-chip[data-city="Oradea"]')
    page.expect(page.locator("#loc-name")).to_have_text("Oradea", timeout=15000)
    page.wait_for_timeout(1500)
    page.click("#lang-toggle")  # RO (default) → EN
    page.wait_for_timeout(1500)
    assert page.get_attribute("html", "lang") == "en"
    assert page.get_attribute("#pdf-link", "href").endswith("city=Oradea&lang=en")
    assert page.errors == []


def test_temperature_is_a_whole_number(page):
    assert page.inner_text("#m-temp").lstrip("−").isdigit()


def test_autocomplete_keyboard_flow(page):
    box = page.locator("#city-input")
    box.click()
    box.type("timi")
    assert page.inner_text("#city-ghost .ghost-rest") == "șoara"
    page.keyboard.press("Tab")
    assert box.input_value() == "Timișoara"

    box.fill("")
    box.type("stef")
    assert page.locator("#city-suggestions .suggestion").count() == 2
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    page.expect(page.locator("#loc-region")).to_contain_text("Botoșani", timeout=15000)

    box.click()
    box.fill("")
    box.type("paris")
    assert "paris" in page.inner_text("#city-suggestions")
    page.keyboard.press("Escape")
    assert page.get_attribute("#city-input", "aria-expanded") == "false"
    assert page.errors == []


def test_day_cards_are_buttons_without_a_text_caret(page):
    """Regression: hovering a 7-day card showed the I-beam text cursor and clicking placed a caret.
    The cards are now clickable buttons: pointer cursor, no text selection."""
    card = page.locator(".day-card").nth(2)
    assert card.evaluate("el => el.tagName") == "BUTTON"
    style = card.evaluate("el => { const s = getComputedStyle(el); return [s.cursor, s.userSelect]; }")
    assert style == ["pointer", "none"]


def test_clicking_a_day_shows_its_hourly_forecast(page):
    title = page.locator("#hourly-title")
    # Wait for the GSAP reveal: while the card is still visibility:hidden, inner_text() returns "" (was flaky).
    page.expect(title).to_be_visible()
    page.expect(title).not_to_have_text("")
    default_title = title.inner_text()
    # The visible <tspan>: each ApexCharts label <text> also holds an SVG <title> with the same text.
    first_label = "document.querySelector('#chart-precip .apexcharts-xaxis-texts-g text tspan')"

    page.locator(".day-card").nth(2).click()
    page.expect(page.locator(".day-card").nth(2)).to_have_attribute("aria-pressed", "true")
    page.expect(title).not_to_have_text(default_title)
    page.expect(page.locator("#hourly-reset")).to_be_visible()
    page.wait_for_timeout(1200)
    assert page.evaluate(f"{first_label}.textContent") == "00:00"  # a whole day: 00:00 … 23:00

    page.click("#lang-toggle")  # the selection survives a language switch, and the title is translated
    page.expect(page.locator(".day-card").nth(2)).to_have_attribute("aria-pressed", "true")
    page.click("#lang-toggle")

    page.locator(".day-card").nth(2).click()  # clicking the selected day again goes back
    page.expect(title).to_have_text(default_title)
    page.expect(page.locator("#hourly-reset")).to_be_hidden()

    page.locator(".day-card").nth(3).focus()  # keyboard: Enter selects
    page.keyboard.press("Enter")
    page.expect(page.locator(".day-card").nth(3)).to_have_attribute("aria-pressed", "true")
    page.click("#hourly-reset")
    page.expect(title).to_have_text(default_title)
    assert page.errors == []


def test_seven_day_forecast_comes_before_the_hourly_charts(page):
    order = page.eval_on_selector_all("#dashboard > section", "els => els.map(e => e.id)")
    assert order.index("forecast-section") < order.index("hourly-section")


def test_selecting_a_day_brings_the_hourly_charts_into_view_without_jumping_up(page):
    card = page.locator(".day-card").nth(4)
    card.scroll_into_view_if_needed()
    y_before = page.evaluate("scrollY")
    card.click()
    page.wait_for_timeout(1200)  # smooth scroll
    assert page.evaluate("scrollY") >= y_before  # only ever scrolls down, towards the charts below
    box = page.locator("#chart-precip").bounding_box()
    assert box["y"] + box["height"] <= page.viewport_size["height"]  # the hourly charts are fully visible


def test_first_visit_is_in_romanian(page):
    """New visitors (nothing in localStorage) get Romanian; the PDF link follows."""
    assert page.get_attribute("html", "lang") == "ro"
    assert page.get_attribute("#city-input", "placeholder").startswith("Caută")
    page.expect(page.locator(".preset-chip").first).to_have_text("București")
    assert page.get_attribute("#pdf-link", "href").endswith("lang=ro")


def test_a_saved_english_choice_is_kept(page):
    page.evaluate("localStorage.setItem('ck-lang', 'en')")
    page.reload(wait_until="load")
    page.expect(page.locator("#loc-name")).not_to_have_text("—", timeout=15000)
    assert page.get_attribute("html", "lang") == "en"
