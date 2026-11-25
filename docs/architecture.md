# Architecture

## Layout

```
carpathian-keros/
├── app.py                       create_app() factory: routes, presets, error → HTTP, security headers, /health
├── gunicorn.conf.py             Production server settings (PORT, workers, timeouts) used by the image
├── Dockerfile                   Two-stage production image (gunicorn, non-root, PDF fonts) for Docker / Cloud Run
├── .dockerignore                Allow-list: what may enter the image
├── infra/                       OpenTofu: Cloud Run, Artifact Registry, WIF, IAM, budget (+ tests/, .tflint.hcl)
│   └── bootstrap/               The GCS bucket for OpenTofu state (applied once, by hand)
├── data/cities_ro.json          The 319 official cities (generated, committed)
├── scripts/build_cities.py      Generator for data/cities_ro.json (Wikipedia + Open-Meteo Geocoding)
├── scripts/build_brand_assets.py  Generator for favicons, header logo, README logo, social preview (Pillow)
├── assets/brand/                Logo originals (large JPEGs, not served) + social-preview.png for GitHub
├── services/
│   ├── cities.py                City registry: exact lookup, aliases, shared-name handling
│   ├── weather_service.py       Open-Meteo forecast client, TTL cache, response shaping
│   ├── pdf_service.py           fpdf2 report builder
│   └── i18n.py                  Backend labels: PDF strings, WMO codes, weekdays
├── templates/index.html         The single Jinja2 page (markup + CDN script tags)
├── static/
│   ├── js/tailwind-config.js    Tailwind Play CDN theme (a file, because the CSP forbids inline scripts)
│   ├── js/i18n.js               Frontend dictionary + locale helpers (window.CK_I18N)
│   ├── js/util.js               escapeHtml, fold (window.CK_UTIL)
│   ├── js/autocomplete.js       City matching + combobox UI (window.CK_Autocomplete)
│   ├── js/app.js                Page behaviour (fetch, render, GSAP, ApexCharts)
│   ├── css/style.css            Custom CSS layered on Tailwind, @font-face for Inter
│   ├── fonts/                   Self-hosted Inter (woff2) + OFL.txt
│   ├── images/                  Generated favicon set (.ico/.png) and header logo
│   └── site.webmanifest         Web app manifest (name, theme colour, 192/512 icons)
├── tests/                       pytest (unit, api, pdf), js (node:test), e2e (Playwright) and docker (opt-in), fixtures
├── docs/                        This documentation (+ docs/images/logo-stacked.png for the README)
├── AGENTS.md / CLAUDE.md        Constitution and agent instructions (CLAUDE.md only imports AGENTS.md)
├── CHANGELOG.md                 Release history (Keep a Changelog)
├── pyproject.toml               Version (single source of truth), pytest and ruff config
├── requirements.txt             Runtime, pinned: flask, requests, fpdf2, gunicorn
└── requirements-dev.txt         Tooling, pinned: pytest, pypdf, ruff, pip-audit
```

## Request flow

```
Browser ──GET /──────────────────────▶ app.index ──▶ render index.html (presets, city count injected)
   │
   ├─fetch /api/cities (once) ────────▶ app.api_cities ──▶ city_registry.suggestions()   [autocomplete]
   │
   ├─fetch /api/weather?city=X ──────▶ app.api_weather
   │                                     └─▶ weather_service.get_weather(X)
   │                                           ├─ resolve_city(X) ─▶ city_registry.resolve(X)  (in memory; 404 if not listed)
   │                                           └─ _fetch_forecast()  [forecast cache]
   │                                                └─ GET api.open-meteo.com/v1/forecast
   │                                     ◀── JSON (location, current, hourly[24], daily[7], stale)
   │
   └─GET /api/report/export?city=X&lang=ro ─▶ app.api_report_export
                                               ├─ weather_service.get_weather(X)   (usually a cache hit)
                                               └─ pdf_service.build_report(data, lang) ─▶ PDF bytes
```

## Backend components

### `app.py`
- **`create_app(weather_service=None, registry=None)`** is the composition root.
  - Production uses the module-level singletons (`app = create_app()` is also the WSGI entry point); tests inject fakes.
  - It checks that every `PRESET_CITIES` entry resolves, and refuses to start otherwise.
- **`PRESET_CITIES`**: each entry's `query` is what gets sent to the API, and `en` / `ro` are the chip labels.
- **Errors:** `WeatherServiceError` subclasses become `{"error": code, "message": ...}` with the exception's own `status`.
  - 4xx messages describe the input.
  - 5xx messages are a fixed, generic text; the real cause is logged as a warning (AGENTS.md V.1).
- **Security headers:** `SECURITY_HEADERS` is added to every response by an `after_request` hook. It contains the `CONTENT_SECURITY_POLICY`, plus `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and `Permissions-Policy`.
- Sets `app.json.ensure_ascii = False`, so diacritics come out as UTF-8 instead of `\u` escapes.
- `_configure_logging()` runs only under `python app.py`. It turns down fontTools' logging, because fpdf2's font subsetting logs every glyph at INFO.

### Dependency injection (AGENTS.md, Article I-D)

| Component | Injectable collaborators | Production default |
|---|---|---|
| `create_app` | `weather_service`, `registry` | module singletons |
| `WeatherService` | `session` (anything with `.get(url, params=, timeout=)`; see the `HttpSession` protocol), `registry`, `cache` | `requests.Session` with retries, `city_registry`, `TTLCache(600)` |
| `TTLCache` | `clock` | `time.monotonic` |
| `CityRegistry` | `path` | `data/cities_ro.json` |
| `build_report` | `font_paths` (`None` forces the ASCII fallback) | auto-detected Unicode TTF |

`tests/conftest.py` wires these with `FakeSession` (which serves `tests/fixtures/open_meteo_forecast.json`) and `FakeClock`, so the whole suite runs offline in about 2 seconds.

### `services/cities.py`
- **`CityRegistry`** loads `data/cities_ro.json` once at import. The module-level singleton is `city_registry`.
- **`resolve(query)`** does an **exact** lookup on a folded key (case, diacritics and hyphens removed).
  - Accepts `Name`, `Name, County` or `Name (jud. County)`, plus English aliases (`ALIASES`: `bucharest`).
  - A shared name with no county returns the more populous town.
  - Returns `None` for anything not on the list. Partial names never match; that's the autocomplete's job, in the browser.
- **`City.query`** is the canonical query string: the plain name, or `Name, County` when the name is shared (Ștefănești).
- **`City.location()`** builds the `location` object for the API, including the bilingual `region` / `country` labels.

### `scripts/build_cities.py` (offline)
1. Downloads the wikitext of [Lista orașelor din România](https://ro.wikipedia.org/wiki/Lista_ora%C8%99elor_din_Rom%C3%A2nia) and parses the population table: name, county, 2021 population, and county seats (shown in bold).
2. Cross-checks against the page's alphabetical list. The table is missing **Sebiș** and **Turceni**, so those two get their county and population from the geocoder.
3. Geocodes every city with Open-Meteo (`countryCode=RO`).
   - A match needs the same folded name and the same county.
   - If the Romanian-language lookup fails, it retries in English, because some GeoNames entries carry Cyrillic names under `language=ro`.
   - Administrative seats and larger populations win ties.
4. Rejects coordinates outside Romania's bounding box, and fails if any city didn't resolve.
5. Fixes known gaps in the source: Buftea is marked as Ilfov's county seat.
6. Writes `data/cities_ro.json` with source, licence and retrieval date. It warns if the count isn't 319.

### `services/weather_service.py`
- **`WeatherService`**: the production instance is the module-level `weather_service`. Its default session is a `requests.Session` with urllib3 `Retry` (2 retries, backoff 0.3 s, on 429/5xx), and every call passes `REQUEST_TIMEOUT` (3.05 s connect, 8 s read).
- **`resolve_city(city)`** validates the input length (`invalid_city`), then looks the city up in the registry (`city_not_found`). There's no network call.
- **`_fetch_forecast(lat, lon)`**
  - Requests everything in one call (`current`, `hourly`, `daily`, `timezone=Europe/Bucharest`, `forecast_days=7`).
  - `_shape_forecast` turns Open-Meteo's column arrays into lists of row objects, and slices `hourly` to 24 entries starting at the current local hour.
- **`TTLCache`** is a thread-safe `OrderedDict` with a TTL and a size bound. Entries past their TTL aren't deleted: `get()` ignores them, but `get_stale()` still returns them for the fallback path.
- **Error types:**

  | Error | `code` | HTTP status |
  |---|---|---|
  | `InvalidCityError` | `invalid_city` | 400 |
  | `CityNotFoundError` | `city_not_found` | 404 |
  | `UpstreamError` | `upstream_error` | 502 |

  Unexpected payload shapes (`KeyError` and similar) are wrapped as `UpstreamError`.

### `services/pdf_service.py`
- **`_ReportPDF(FPDF)`**: draws the brand header band and the footer (data attribution plus "Page n/N").
- **Font selection** (`_find_font`):
  - Tries `CK_PDF_FONT` first, then DejaVu, Liberation, Noto and Arial paths on Linux, macOS and Windows.
  - If none exists, it uses core Helvetica and sends every string through `t()`, which converts Romanian letters to ASCII. This prevents `FPDFUnicodeEncodingException`.
- **Number formatting**: `_fmt_num` uses comma decimals for `ro` and turns `-0.0` into `0.0`.
- **Layout**: location block, current-conditions key/value table, next 24 h every 3 h (8 rows), 7-day table. It's sized to fit on one A4 page.

### `services/i18n.py`
Holds the backend copies of the WMO labels, weekday names and PDF strings. See [i18n](i18n.md).

## Frontend

See the [frontend guide](frontend.md) for details. In short:
- `index.html` loads Tailwind (with `tailwind-config.js`), GSAP and ApexCharts (pinned, with SRI), then `i18n.js` → `util.js` → `autocomplete.js` → `app.js`.
- Each file is an IIFE exposing one frozen `CK_*` global. There are no frameworks or build tools.
- The CSP forbids inline scripts and `eval`.

## Design decisions

| Decision | Why |
|---|---|
| A fixed allow-list instead of live geocoding | Guarantees Romanian cities only: live geocoding returned villages (`Paris` → Parisești) or, with a misspelled filter, foreign places. It's also faster and deterministic, and the official names keep their diacritics. |
| Exact match on the server, fuzzy match in the browser | The server never guesses. All the "did you mean" behaviour is in the autocomplete, where the user can see and pick. |
| The list is committed, not fetched at startup | No runtime dependency on Wikipedia, and changes can be reviewed. Refresh it with `scripts/build_cities.py`. |
| Forecast cache keyed by coordinates | Every spelling of a city (`Iasi`, `Iași`, `iasi`) shares one forecast entry. |
| App factory + constructor injection | Tests run offline and deterministically (fake HTTP, fake clock), with no monkeypatching of globals. |
| Strict script CSP, inline styles allowed | Blocks injected scripts, the main XSS vector. Styles stay inline because the Tailwind Play CDN and ApexCharts need them, until Tailwind is compiled locally. |
| Self-hosted font | No visitor IPs are sent to Google (GDPR), and one less external origin in the CSP. |
| Serve stale data when the upstream fails | A dashboard with 15-minute-old data is more useful than an error page. The `stale` flag keeps it transparent. |
| Error codes, not messages | The frontend translates them. Messages stay English and are for developers. |
| Hourly view as two stacked charts, not one dual-axis chart | Temperature and precipitation have different units. Charts with two Y scales are easy to misread. |
| Duplicated WMO dictionaries (Python + JS) | No build step and no extra request. The cost is keeping them in sync (see [i18n](i18n.md)). |
| No database | Everything is derived from Open-Meteo on demand. |
