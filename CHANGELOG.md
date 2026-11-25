# Changelog

All notable changes to Carpathian Keros are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/) as defined in `AGENTS.md`, Article IV. The version's single source of truth is `version` in `pyproject.toml`.

## [Unreleased]

## [1.1.1] - 2026-11-25

**The first live release** at **https://carpathian-keros.cloud.run**.

### Fixed
- **The deploy's smoke test rejected a healthy candidate** with "Content-Security-Policy missing", so the `v1.1.0` deploy stopped before any traffic moved (production was untouched). Cloud Run answers over HTTP/2, which sends header names in lowercase, and `scripts/smoke_test.py` copied the headers into a case-sensitive `dict`. It now keeps urllib's case-insensitive headers. The regression test runs the checks against a server that lowercases every header name. The app itself is unchanged.

## [1.1.0] - 2026-11-25

Adds deployment to Google Cloud Run: every `v*` tag deploys itself. The `v1.1.0` deploy stopped at the candidate's smoke test (fixed in 1.1.1), so 1.1.1 is the first live release.

### Added
- **Live deployment on Google Cloud Run** (europe-west1, free tier), with free HTTPS at `https://carpathian-keros.cloud.run`. The custom URL is a Cloud Run Preview feature, claimed once by hand; the default `*.run.app` URL stays as a fallback.
- **Continuous deployment** (`.github/workflows/deploy.yml`, *Deploy to Cloud Run*). A `v*` tag (or a manual run on `main`) deploys **blue/green**:
  - checks the tag against the `pyproject.toml` version, then builds and Trivy-scans the image
  - pushes it with Workload Identity Federation (no keys or secrets)
  - deploys a **no-traffic candidate**, smoke-tests its own URL, then moves 100% of the traffic to it
  - verifies `https://carpathian-keros.cloud.run`, and **rolls back automatically** if that fails
  - runs in a `production` environment and is never cancelled halfway
  - adds a deploy status badge to the README
- **`scripts/smoke_test.py`**: checks `/health` for the expected version, the page and its security headers, the weather API and the PDF export, with retries. It's used on the candidate and on the public URL, and can be run by hand.
- **`GET /health`** → `{"status": "ok", "version": "…"}`, for Cloud Run probes, the deploy smoke test and the Docker `HEALTHCHECK`. It never calls Open-Meteo. This is an additive API change, hence a MINOR release. It's deliberately **not** `/healthz`: Cloud Run's front end reserves paths ending in `z`, and public requests to `/healthz` returned Google's 404 (found on the live service before release). No route may end in `z` now.
- **Infrastructure as code** (`infra/`, OpenTofu) for Google Cloud Run:
  - a GCS state bucket and the foundation APIs (Storage, Resource Manager, Service Usage) in `infra/bootstrap/`, so `infra/` can plan in a fresh project
  - Artifact Registry with image cleanup (keeps the 5 newest images)
  - runtime and deployer service accounts with resource-scoped roles only
  - **Workload Identity Federation**: no service-account keys. It trusts only this repository's `deploy.yml`, on `main`/`v*` tags, by numeric repository and owner ID.
  - the Cloud Run service (scale to zero, max 2 instances, `/health` probes); OpenTofu ignores the image and the traffic split, which CD owns
  - a monthly budget alert
  - **Tests:** `tofu test` with a mocked Google provider, plus static policy checks
  - **Guide:** `docs/infrastructure.md` (first apply, the custom URL, GitHub variables, deploying, rollback, teardown)
- **Production Docker image** (`Dockerfile`, `.dockerignore`, `gunicorn.conf.py`):
  - two-stage build, with gunicorn as PID 1 for a clean SIGTERM shutdown
  - non-root user (uid 10001), and `fonts-dejavu-core` so PDFs keep their diacritics
  - an allow-list build context, so tests, docs, `.git` and `.env` never reach the image
  - honours `PORT` (default 8080), `WEB_CONCURRENCY` and `GUNICORN_THREADS`
- **CI** (`.github/workflows/ci.yml`, *Build, Test & Scan*) on every PR into `development` or `main`, with 7 jobs:
  - Lint (ruff), Unit & API Tests (pytest + Node), Dependency Audit (pip-audit), Secret Scan (gitleaks, full history)
  - Container Build & Scan (hadolint → build → container tests → Trivy, failing on fixable HIGH/CRITICAL)
  - Infrastructure (tofu fmt/validate/test, tflint, Trivy config)
  - Browser Tests (Playwright, desktop and phones)

  Actions are pinned to commit SHAs, tool images by digest, and the token is read-only. `tests/unit/test_ci_config.py` and `tests/unit/test_cd_config.py` enforce these rules.
- **Dependabot** (`.github/dependabot.yml`): weekly PRs into `development` for pip packages, GitHub Actions, the Docker base image and the OpenTofu Google provider.
- **Container tests** (`CK_DOCKER=1 pytest -m docker`): build and run the image, then check health, the API, PDF fonts, the non-root user, clean startup logs, image contents and size, no pip, and graceful shutdown.
- `requirements-e2e.txt` (Playwright, pinned). PyYAML is added to the dev requirements and gunicorn to the runtime requirements.

### Changed
- **Branching strategy** (AGENTS.md, Article VI): work branches merge into a `development` integration branch (squash); releases go `development` → `main` (merge commit), then a `vX.Y.Z` tag, which now also deploys. Hotfixes branch from `main` and are merged back into `development`.
- **Browser tests no longer depend on Open-Meteo.** They run the real app with the recorded forecast (`tests/e2e/fake_server.py`, the unit tests' `FakeSession`), so an Open-Meteo outage or a rate limit on shared CI runners can't fail them. Previously a slow answer made all 23 time out (6 minutes). Verified by running them with Open-Meteo blocked.
- **CI caches Chromium** for the browser tests. The test server's log is kept and shown if it fails to start (it used to be discarded).

### Fixed
- **Mobile layout** (phones up to 639 px wide). Tablets and desktop are unchanged.
  - Hourly chart axis labels overlapped (`15:0018:0021:00…`). They now show every 6 hours on phones.
  - 7-day chart day names touched each other (`Sâm.Dum.`). They now use a smaller font on phones.
  - The 7 day cards took four rows. They're now one swipeable row.
  - The current-conditions card was very tall. The illustration now sits beside the city name, and feels like / humidity / wind sit side by side.
  - The search placeholder was cut off. Phones get a short one ("Caută un oraș…").
  - The footer link was too small to tap comfortably (15 px). It's now at least 24 px tall.

### Security
- **HSTS** (`Strict-Transport-Security: max-age=31536000`) on responses to HTTPS requests, as Cloud Run serves them. Plain local HTTP is unaffected.
- **Docker image hardened after the first Trivy scan**, which found 5 fixable HIGH vulnerabilities, all outside the app's own dependencies:
  - The base image's own `pip` (with vendored urllib3 and msgpack) and ensurepip's bundled setuptools wheels are removed. The app never installs anything at runtime.
  - Debian security updates are applied at build time (`libzstd1`).
  - Result: 0 HIGH/CRITICAL findings.
- **Base image pinned by digest** (`python:3.14-slim@sha256:…`); Dependabot bumps it.
- **The container user is numeric** (`USER 10001:10001`), so platforms can verify it isn't root.

## [1.0.0] - 2026-11-25

This is the first public release. The public contracts below are **v1**.

### Added
- **Dashboard:**
  - current conditions, a 7-day forecast with a min/max range chart, and an hourly temperature and precipitation chart (two synced panels), in that order
  - GSAP animations, with reduced motion respected
- **Hourly view for any day:** click a day card, or its bar in the range chart, to see that day hour by hour (00:00–23:00). "Back to next 24 hours", "Today" or clicking the day again returns to the next 24 hours. The cards are buttons, so they work with the keyboard and screen readers.
- **Bilingual UI:** Romanian by default, English on the `RO | EN` toggle.
  - The server-rendered HTML is already Romanian, so no English flashes up while the scripts load.
  - The language is saved in `localStorage` as `ck-lang`, and the last city as `ck-city`.
- **City allow-list** of Romania's 319 official cities and towns:
  - `data/cities_ro.json`, generated by `scripts/build_cities.py` from Wikipedia, with coordinates from Open-Meteo Geocoding
  - the server only accepts exact (folded) matches; places not on the list return `city_not_found`
- **City search autocomplete:**
  - ranked suggestions (prefix, word, substring), with county and population
  - inline Tab completion, keyboard navigation, and the `Bucharest` alias
- **Quick-select presets:** București, Cluj-Napoca, Constanța, Iași, Oradea, Timișoara.
- **API:**
  - endpoints: `GET /api/cities`, `GET /api/weather?city=`, and `GET /api/report/export?city=&lang=`
  - `daily[].hourly` carries each day's 24 hourly rows
  - error contract `{error, message}` with the codes `invalid_city` (400), `city_not_found` (404) and `upstream_error` (502)
  - `lang` defaults to `en` in the API
- **One-page A4 PDF report** in English or Romanian, with a Unicode font and an ASCII fallback. Filename: `carpathian-keros_<query-slug>_<lang>_<YYYYMMDD>.pdf`.
- **Temperatures** are displayed as whole degrees, rounded half away from zero, in both the UI and the PDF. The API keeps full precision.
- **Forecast cache:** in memory, 10 minutes, serving stale data (`"stale": true`) when the upstream fails.
- **Security:**
  - Content-Security-Policy (no inline scripts, no eval), `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and `Permissions-Policy` headers
  - Subresource Integrity on GSAP and ApexCharts
  - server-side failure details are logged, never returned to clients
- **Brand identity:**
  - logo in the site header
  - favicon set (`favicon.ico`, PNG sizes, Apple touch icon) and a web app manifest
  - the stacked logo as the README header, and a GitHub social-preview image
  - all generated from the originals in `assets/brand/` by `scripts/build_brand_assets.py`
- **Self-hosted Inter font** (SIL OFL 1.1). No requests go to Google Fonts.
- **Tests:**
  - pytest suite (unit, API, PDF, brand assets), fully offline through injected fakes
  - Node unit tests for i18n and autocomplete
  - opt-in Playwright browser tests (`CK_E2E=1`)
- **Tooling and docs:**
  - `pyproject.toml` (version, pytest, ruff) and `requirements-dev.txt`
  - `AGENTS.md` (project constitution) and `docs/`
  - `LICENSE` (MIT) and `NOTICE.md` (third-party licences)

### Fixed
These were found and fixed during development, before the first release. Each has a regression test.
- The geocoder country filter was ignored because it was spelled `country_code` instead of `countryCode`, which let non-Romanian places through.
- Grouped ApexCharts threw `Cannot read properties of undefined (reading 'call')` after a city or language change.
- Negative halves rounded toward zero in JS (`Math.round(-3.5)`), and Python's `round()` rounded to even (`2.5 → 2`).
- Both towns named Ștefănești produced the same PDF filename.
- Escape didn't close the autocomplete list.
- The 7-day cards showed a text cursor (I-beam) and accepted a text caret.
