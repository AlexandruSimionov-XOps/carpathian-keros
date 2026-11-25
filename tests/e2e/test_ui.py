"""Browser tests against the real app served with recorded weather (tests/e2e/fake_server.py).

Opt-in: they need Playwright + Chromium, and network access for the CDN scripts (not for Open-Meteo):

    pip install -r requirements-e2e.txt && playwright install chromium
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
def base_url(tmp_path_factory):
    """The app with recorded weather (no Open-Meteo calls), on a free port. Its log goes to a file that's shown
    if it doesn't start, instead of being discarded."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log_path = tmp_path_factory.mktemp("server") / "server.log"
    env = {**os.environ, "PORT": str(port)}
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            [sys.executable, "tests/e2e/fake_server.py"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
        )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"{url}/health", timeout=1)  # noqa: S310 - our own local test server
                break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("test server didn't start:\n" + log_path.read_text())
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


# ---------------------------------------------------------------- mobile layout (phones: 360 and 390 px wide)

OVERLAPS_JS = """sel => {
  const boxes = [...document.querySelectorAll(sel)].filter(t => t.textContent.trim())
                  .map(t => t.getBoundingClientRect()).sort((a, b) => a.left - b.left);
  return boxes.slice(1).filter((b, i) => b.left < boxes[i].right - 0.5).length;
}"""


@pytest.fixture(params=[(360, 740), (390, 844)], ids=["360px", "390px"])
def phone(request, base_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    width, height = request.param
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": width, "height": height}, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.goto(base_url, wait_until="load")
        sync_api.expect(pg.locator("#loc-name")).not_to_have_text("—", timeout=15000)
        pg.wait_for_timeout(2500)  # reveal + chart animations
        pg.expect = sync_api.expect
        yield pg
        browser.close()


def test_phone_page_never_scrolls_sideways(phone):
    assert phone.evaluate("document.documentElement.scrollWidth") == phone.viewport_size["width"]
    assert phone.errors == []


def test_phone_chart_axis_labels_do_not_overlap(phone):
    """Was: '15:0018:0021:00…' under the hourly chart and 'Sâm.Dum.' under the 7-day chart."""
    assert phone.evaluate(OVERLAPS_JS, "#chart-precip .apexcharts-xaxis-texts-g text tspan") == 0
    assert phone.evaluate(OVERLAPS_JS, "#chart-range .apexcharts-xaxis-texts-g text tspan") == 0


def test_phone_day_cards_are_one_swipeable_row(phone):
    cards = phone.locator(".day-card")
    tops = {round(cards.nth(i).bounding_box()["y"]) for i in range(cards.count())}
    assert len(tops) == 1, "all 7 days in one row"
    row = phone.locator("#daily-cards")
    assert row.evaluate("el => el.scrollWidth > el.clientWidth && getComputedStyle(el).overflowX === 'auto'")
    cards.nth(6).scroll_into_view_if_needed()  # the last day is reachable by swiping
    last = cards.nth(6).bounding_box()
    assert last["x"] + last["width"] <= phone.viewport_size["width"]


def test_phone_current_conditions_are_compact(phone):
    scene = phone.locator("#weather-scene").bounding_box()
    text = phone.locator("#loc-name").locator("xpath=..").bounding_box()  # the column with name, region, temperature
    assert scene["x"] + scene["width"] <= text["x"], "illustration is to the left of the text, not above it"
    assert scene["y"] < text["y"] + text["height"] and text["y"] < scene["y"] + scene["height"], "same row"
    metric_tops = {round(m.bounding_box()["y"]) for m in phone.locator(".metric").all()}
    assert len(metric_tops) == 1, "feels like / humidity / wind side by side"


def test_phone_search_placeholder_is_short(phone):
    assert phone.get_attribute("#city-input", "placeholder") == "Caută un oraș…"


def test_phone_footer_link_is_a_comfortable_tap_target(phone):
    assert phone.locator("footer a").bounding_box()["height"] >= 24


def test_desktop_keeps_the_long_placeholder(page):
    assert page.get_attribute("#city-input", "placeholder") == "Caută printre cele 319 orașe din România…"
