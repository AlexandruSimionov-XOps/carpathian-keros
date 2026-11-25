# AI agent guide

The project's governing principles (SOLID, modular architecture, test-first development, versioning, security and compliance, Git branching) are in [`AGENTS.md`](../AGENTS.md). This is a compact orientation for AI coding agents (and humans in a hurry) working on Carpathian Keros. Read it before changing code. Deeper details are in the linked docs.

## Map

| Concern | File | Key symbols |
|---|---|---|
| App factory, routes, presets, error → HTTP, security headers | `app.py` | `create_app`, `PRESET_CITIES`, `SECURITY_HEADERS`, `CONTENT_SECURITY_POLICY`, `_slug` |
| City allow-list + lookup | `services/cities.py`, `data/cities_ro.json` | `city_registry.resolve`, `City.query`, `City.location`, `ALIASES`, `fold` |
| City list generator (offline) | `scripts/build_cities.py` | `parse_table`, `parse_alphabetical`, `geocode`, `EXTRA_COUNTY_SEATS` |
| Forecast API, cache, payload shape | `services/weather_service.py` | `WeatherService(session=, registry=, cache=)`, `resolve_city`, `_fetch_forecast`, `_shape_forecast`, `TTLCache(clock=)`, `*Error` classes |
| PDF | `services/pdf_service.py` | `build_report(font_paths=)`, `_ReportPDF`, `_find_font`, `_fmt_num`, `_fmt_temp` |
| Backend strings | `services/i18n.py` | `LABELS`, `WMO_CODES`, `WEEKDAYS`, `normalize_lang`, `wmo_label` |
| Page markup | `templates/index.html` | `data-i18n*` attributes, element IDs used by `app.js` |
| Frontend strings | `static/js/i18n.js` | `window.CK_I18N` (`t`, `wmoLabel`, `weekday`, `formatNumber`) |
| Shared JS helpers | `static/js/util.js` | `window.CK_UTIL` (`escapeHtml`, `fold`) |
| City autocomplete | `static/js/autocomplete.js` | `window.CK_Autocomplete`: pure `findMatches`, `completion`, `resolveInput`, `prepareCities`; UI `mount()` |
| Page behaviour | `static/js/app.js` | `state`, `loadCity`, `loadCityList`, `render`, `renderCharts`, `sceneSVG`, `animateScene` |
| Tailwind theme | `static/js/tailwind-config.js` | `tailwind.config` (a file, not inline, because of the CSP) |
| Tests | `tests/` | `conftest.py` (`FakeSession`, `FakeClock`), `fixtures/open_meteo_forecast.json` |
| Version / history | `pyproject.toml`, `CHANGELOG.md` | `[project].version` |
| Styles | `static/css/style.css` | component classes |

## Invariants: don't break these

1. **The brand name "Carpathian Keros"** must appear in the HTML `<title>`, the nav `<h1>` and the PDF header (`APP_NAME` in `pdf_service.py`).
2. **Only the 319 cities in `data/cities_ro.json` can be queried.** Don't add live geocoding back to request handling.
   - The server does an **exact** (folded) match only; the browser's autocomplete does the fuzzy matching.
   - Use `location.query` (canonical, county-qualified when a name is shared) for follow-up calls.
   - Every `PRESET_CITIES` entry must resolve, and `app.py` refuses to start otherwise.
   - If you touch `scripts/build_cities.py`, keep it using `countryCode` (not `country_code`, which Open-Meteo silently ignores) and keep the county match and bounding-box checks.
3. **API error contract:** `{"error": <code>, "message": <str>}` with codes `invalid_city` (400), `city_not_found` (404), `upstream_error` (502). The frontend translates `errors.<code>`. If you add a code, add a translation in both languages in `i18n.js`.
4. **The WMO labels live in two places** (`services/i18n.py` → `WMO_CODES`, `static/js/i18n.js` → `wmo`). Change both together.
5. **Every UI string needs `en` and `ro`.** Use comma-below `ș ț`, never the cedilla forms `ş ţ`.
6. **The PDF must not raise `FPDFUnicodeEncodingException`.** All text written to the PDF goes through `pdf.t(...)`, which handles the no-Unicode-font fallback. Don't call `pdf.cell(...)` with raw strings.
7. **Grouped ApexCharts update with `updateOptions(opts, false, true, false)`.** Without the 4th argument, the options leak into the other chart in the group and it throws at runtime.
8. **No dual-axis charts.** Temperature and precipitation stay as two aligned charts with the same `Y_LABEL_WIDTH`.
9. **Local times aren't instants.** API times are Europe/Bucharest local without an offset. Slice the strings, or build dates at local noon (see `frontend.md`).
10. **Language switching never refetches** and never resets `state.city`. The PDF link must always reflect both `state.city` and `state.lang`.
11. **Keep `/api/weather` and the PDF reading the same cache.** Export right after viewing must not call the upstream again.
12. **Temperatures are displayed as whole degrees, rounded half away from zero** (3.5 → 4, 3.4 → 3, −3.5 → −4), in both the UI (`TEMP_DECIMALS` in `app.js`, `data-decimals="0"`) and the PDF (`_fmt_temp` / `TEMP_DECIMALS` in `pdf_service.py`). Don't use JS `Math.round` alone (−3.5 → −3) or Python's `round()` (banker's: 2.5 → 2). `formatNumber` and `_fmt_num` already implement the rule, so the two can't drift. The API itself stays unrounded.
13. **Respect `prefers-reduced-motion`.** New looping animations go through the existing `reducedMotion` check.

## Conventions

- Python: `ruff`-clean and `ruff format`-ted (line length 120), with type hints, `from __future__ import annotations` and small pure helpers. Avoid new dependencies; pin any additions in `requirements.txt` (runtime) or `requirements-dev.txt` (tooling).
- JS: plain ES2020, no frameworks and no build step. Each file is an IIFE exposing one frozen `CK_*` global. Escape anything interpolated into HTML strings with `CK_UTIL.escapeHtml`. Query the DOM with `$` / `$$`. **No inline scripts, `on*=` attributes or `eval`**: the CSP blocks them.
- CSS: Tailwind utilities in the markup. Reusable components go in `style.css`.
- Comments explain *why*, not what.
- CDN versions are pinned in `index.html`, with SRI hashes. If you bump ApexCharts or GSAP, recompute the hash (`curl -s URL | openssl dgst -sha384 -binary | openssl base64 -A`) and re-run the e2e tests.

## Verification checklist

Run these after any change. Everything apart from the e2e tests is offline.

**1. Tests + lint** (required for every change)
```bash
.venv/bin/pip install -r requirements-dev.txt        # once
.venv/bin/pytest                                     # unit, API, PDF and JS (Node) tests, ~2 s
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```
- `pytest` runs the JS tests through `tests/test_javascript.py` when `node` is installed. On their own: `node --test tests/js/*.test.mjs`.
- Write new tests first (Article III). Put them next to their layer: `tests/unit`, `tests/api`, `tests/pdf`, `tests/js`, `tests/e2e`.
- Use the fixtures in `tests/conftest.py`: `service`, `client`, `fake_session` (set `.error`, `.status_code` or `.payload`), `clock.advance()` and `registry`.

**2. Browser tests** (for any frontend change; opt-in, needs network + Playwright)
```bash
pip install playwright && playwright install chromium
CK_E2E=1 .venv/bin/pytest -m e2e
```
These cover the presets, the RO/EN toggle, the autocomplete keys, whole-degree temperatures and the footer. They also fail on any console error, which includes **CSP violations** and the chart error from invariant 7. That error only appears **after** a city or language change, so the tests click through the flow.

If no browser is installed, headless Chromium through Playwright works in a scratch venv; point `PYTHONPATH` at its site-packages. On minimal WSL images Chromium may need `libnspr4`, `libnss3` and `libasound2`. Without root, fetch them with `apt-get download`, extract them with `dpkg -x` into a scratch directory, and add that to `LD_LIBRARY_PATH`.

**3. Live server + curl.** See [setup.md → Verify](setup.md#verify-a-running-instance). Stop the server afterwards. On WSL, bind `HOST=0.0.0.0` if the user will open it from Windows.

**4. PDF visual check** (for layout changes). `tests/pdf` already checks the page count, text, diacritics and rounding. For layout, also render page 1 to PNG (e.g. PyMuPDF in a scratch venv) for **both** languages and look at it for overflow.

**5. Before a release:** `pip-audit -r requirements.txt`, bump `version` in `pyproject.toml`, and move the `[Unreleased]` notes in `CHANGELOG.md` under the new version. `test_version_is_declared_once_and_matches_the_changelog` enforces that the two match.

## Common tasks

| Task | Where |
|---|---|
| Add or reorder a preset city | `PRESET_CITIES` in `app.py` (`query`, `en`, `ro`). `query` must be on the city list |
| Refresh the city list | `python scripts/build_cities.py`, review the diff, restart. See [setup.md](setup.md#refreshing-the-city-list) |
| Add an English alias (e.g. another exonym) | `ALIASES` in **both** `services/cities.py` (folded key → folded official name) and `static/js/autocomplete.js` (folded key → official name), plus a test in each of `tests/unit/test_cities.py` and `tests/js/autocomplete.test.mjs` |
| Add a metric | [frontend.md → Adding a new metric](frontend.md#adding-a-new-metric-example-pressure) |
| Add a UI string | [i18n.md → Adding a new string](i18n.md#adding-a-new-string) |
| Add a language | [i18n.md → Adding a third language](i18n.md#adding-a-third-language-eg-hungarian) |
| Change the logo / favicons | Replace the originals in `assets/brand/`, run `python scripts/build_brand_assets.py`, commit the generated files. See [setup.md](setup.md#updating-the-logo-and-favicons) |
| Change the cache TTL | `CACHE_TTL_SECONDS` in `weather_service.py` |
| Change the PDF layout | `build_report` in `pdf_service.py`; keep it to one A4 page and check both languages |

## Things that look wrong but are intentional

- `services/i18n.py` and `static/js/i18n.js` overlap: there's no build step to share them.
- The app never geocodes at runtime: coordinates come from the committed `data/cities_ro.json`.
- `foldChars` in `autocomplete.js` deliberately doesn't collapse whitespace, so match positions line up with the original name for highlighting.
- `TTLCache` keeps expired entries: that's how the stale fallback works.
- `.reveal` cards are hidden only under `html.js-anim`: if GSAP fails to load, the content stays visible.
- `fontTools` logging is set to WARNING in `app.py` (`_configure_logging`): fpdf2's subsetter is very noisy at INFO.
- 5xx responses say only "The weather service is temporarily unavailable": the real cause is in the server log, never in the response (V.1).
- `tests/conftest.py` puts the repo root on `sys.path`: there's no package to install, by design.
