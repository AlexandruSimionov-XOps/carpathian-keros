# Setup & operations

## Requirements

- Python **3.10+** (developed on 3.14)
- Outbound HTTPS to `api.open-meteo.com` from the server. Geocoding is only used by `scripts/build_cities.py`.
- From the browser: access to `cdn.tailwindcss.com` and `cdn.jsdelivr.net`. The font is self-hosted.
- Optional but recommended: a Unicode TTF font for the PDFs, e.g. `sudo apt install fonts-dejavu-core`

## Install

```bash
cd carpathian-keros
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`source .venv/bin/activate` only changes your shell's `PATH` so that `python` means the project's interpreter. It doesn't start anything, and `deactivate` doesn't stop anything.

## Development setup and tests

```bash
pip install -r requirements-dev.txt      # pytest, pypdf, ruff, pip-audit (+ runtime deps)
pytest                                   # unit, API, PDF and JS tests; offline, ~2 s
ruff check . && ruff format --check .    # lint + formatting (config in pyproject.toml)
pip-audit -r requirements.txt            # known-vulnerability scan (before releases)
```

- The JS tests (`tests/js`) run through pytest if Node.js is installed. Otherwise that test is skipped.
- Browser tests are opt-in and need network access:

  ```bash
  pip install playwright && playwright install chromium
  CK_E2E=1 pytest -m e2e
  ```

See [AGENTS.md](../AGENTS.md), Article III, for the test-first workflow, and [ai-agents.md](ai-agents.md#verification-checklist) for the full checklist.

## Continuous integration

The **Build, Test & Scan** workflow (`.github/workflows/ci.yml`) runs on every pull request into `development` or `main`, and on pushes to them. Seven jobs run in parallel, and all must be green. Each can be reproduced locally with the same tool version:

| CI job | What it checks | Run it locally |
|---|---|---|
| **Lint** | Code style, common bugs, formatting (ruff) | `ruff check . && ruff format --check .` |
| **Unit & API Tests** | Unit, API, PDF and JS tests, offline (pytest + Node) | `pytest` (needs `fonts-dejavu-core` for the PDF tests) |
| **Dependency Audit** | Known vulnerabilities in Python packages (pip-audit) | `pip-audit -r requirements.txt -r requirements-e2e.txt` |
| **Secret Scan** | Secrets anywhere in the git history (gitleaks) | `docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --redact` |
| **Container Build & Scan** | Dockerfile lint (hadolint) → build → container tests → vulnerability scan (Trivy) | `docker run --rm -i -v "$PWD/.hadolint.yaml:/.config/hadolint.yaml:ro" hadolint/hadolint:v2.15.1 < Dockerfile`<br>`docker build -t carpathian-keros:ci . && CK_DOCKER=1 CK_IMAGE=carpathian-keros:ci pytest -m docker`<br>`docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.2 image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed carpathian-keros:ci` |
| **Infrastructure** | OpenTofu in `infra/`: format, validate, tests with a mocked Google provider, tflint, Trivy misconfiguration scan | See [infrastructure.md → Changing the infrastructure](infrastructure.md#changing-the-infrastructure) |
| **Browser Tests** | Desktop and phone layouts, interactions, no console or CSP errors (Playwright) | `pip install -r requirements-e2e.txt && playwright install chromium && CK_E2E=1 pytest -m e2e` |

(The workflow pins each tool image by digest; the tags above are the same versions.)

**Supply-chain rules** (checked by `tests/unit/test_ci_config.py`):
- **Pinning:** actions pinned to full commit SHAs; tool images and the Docker base image pinned by digest.
- **Token:** the workflow token is read-only.
- **Dependabot** (`.github/dependabot.yml`) opens weekly update PRs into `development`, and CI vets each one.

**Make CI block merges:** in GitHub → Settings → Rules → Rulesets, for both `development` and `main`, add *Require status checks to pass* and select the seven job names above. GitHub only lists them after the workflow has run once, i.e. after the first PR with this file.

## Versioning

The app version lives in **`pyproject.toml`** (`[project].version`), and changes are recorded in **`CHANGELOG.md`**. A test fails if the two disagree. Bump rules (SemVer, with the public contracts listed) are in AGENTS.md, Article IV.

## Run

```bash
python app.py                      # foreground; stop with Ctrl+C
```

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` to accept connections from other hosts or VMs |
| `PORT` | `5000` | Port |
| `FLASK_DEBUG` | unset | `1` turns on the debugger and auto-reload. **Never use it in production** |
| `CK_PDF_FONT` | auto | Path to a regular-weight TTF for PDFs |
| `CK_PDF_FONT_BOLD` | same as `CK_PDF_FONT` | Path to a bold TTF |

Example: `HOST=0.0.0.0 PORT=8080 python app.py`.

### WSL2

If the app runs inside WSL2 and you browse from Windows:

```bash
HOST=0.0.0.0 python app.py
```

Then open `http://localhost:5000` in Windows. If that gives *refused to connect*, use the WSL VM's IP from `hostname -I` (for example `http://172.23.x.x:5000`). The IP can change after `wsl --shutdown`.

## Stop

| How it was started | How to stop it |
|---|---|
| In the foreground in your terminal | **Ctrl+C** |
| In the background, or you don't know | `pkill -f "python app.py"` or `fuser -k 5000/tcp` |

Check that it stopped: `ss -ltn | grep :5000` should print nothing.

## Verify a running instance

```bash
B=http://127.0.0.1:5000
for u in "/" "/api/weather?city=Bucharest" \
         "/api/report/export?city=Bucharest&lang=en" \
         "/api/report/export?city=Bucharest&lang=ro"; do
  printf "%-46s" "$u"; curl -s -o /dev/null -w "%{http_code}\n" "$B$u"
done
```

All four should print `200`.

## Run with Docker

The production image (`Dockerfile`) runs the app under **gunicorn** as an unprivileged user, with the PDF fonts installed. This is the same image that goes to Google Cloud Run.

```bash
docker build -t carpathian-keros --build-arg VERSION=1.0.0 .
docker run --rm -p 8080:8080 carpathian-keros        # → http://localhost:8080
curl http://localhost:8080/healthz                    # {"status":"ok","version":"1.0.0"}
```

On WSL2, `http://localhost:8080` also works from the Windows browser. Stop the container with **Ctrl+C**.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | Listening port. Cloud Run sets it automatically |
| `WEB_CONCURRENCY` | `2` | gunicorn worker processes |
| `GUNICORN_THREADS` | `4` | Threads per worker (requests mostly wait on Open-Meteo) |
| `CK_PDF_FONT`, `CK_PDF_FONT_BOLD` | DejaVu, installed in the image | Override the PDF font |

**What's in the image** (about 275 MB; the registry stores it compressed):
- **Build:** two stages. Dependencies are installed into a virtualenv in a build stage, and only that venv plus the app files reach the final image. pip is removed from the venv.
- **Contents:** `.dockerignore` is an **allow-list** (`app.py`, `gunicorn.conf.py`, `pyproject.toml`, `requirements.txt`, `services/`, `templates/`, `static/`, `data/`). Tests, docs, `.git`, `.env` files and the brand originals never enter the build.
- **User:** uid 10001, with no home and no shell. The app files are owned by root, so the process can't change its own code.
- **Process:** gunicorn is PID 1 (exec form), so `docker stop` and Cloud Run's SIGTERM shut it down cleanly in about a second. Settings and their reasons are in `gunicorn.conf.py`.
- **Health:** a `HEALTHCHECK` calls `GET /healthz`, which never contacts Open-Meteo, so an upstream outage can't make a healthy container look broken.

**Container tests** build the image, run it, and check the health endpoint, the API, PDF diacritics, the non-root user, clean logs, image contents and size, and SIGTERM shutdown:
```bash
CK_DOCKER=1 pytest -m docker                                  # builds carpathian-keros:test first
CK_DOCKER=1 CK_IMAGE=carpathian-keros:ci pytest -m docker     # or test an image built elsewhere (CI)
```

If `docker` says *permission denied … docker.sock*, your user isn't in the `docker` group yet (`sudo usermod -aG docker $USER`). On WSL, restart WSL after that (`wsl --shutdown` in PowerShell).

## Production deployment

Use the Docker image above (target: Google Cloud Run). Without Docker, run the app under gunicorn with the same settings as the image:

```bash
pip install -r requirements.txt        # includes gunicorn
gunicorn -c gunicorn.conf.py app:app   # listens on $PORT (default 8080)
```

Things to know:

- **The cache is per process.** Each gunicorn worker has its own 10-minute cache. That's fine for this traffic profile. If you need a shared cache, replace `TTLCache` in `services/weather_service.py` with something like Redis.
- **Upstream rate limits.** Open-Meteo's free tier is for non-commercial use with a fair-use limit (roughly 10,000 calls a day). The cache keeps repeat requests off the upstream. Commercial use needs an Open-Meteo plan.
- **Tailwind CDN.** `cdn.tailwindcss.com` logs a "should not be used in production" warning in the browser console. It works, but for a hardened deployment, compile Tailwind with its CLI and serve the resulting CSS from `static/`.
- **Reverse proxy.** Put nginx or Caddy in front for TLS, and add `Strict-Transport-Security` there. The app already sends CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and `Permissions-Policy`; don't strip them. The app is stateless apart from the cache.
- **Fonts on the server.** Install `fonts-dejavu-core` (Debian/Ubuntu) or `dejavu-sans-fonts` (Fedora) so PDFs keep their Romanian diacritics. Without them, the PDF falls back to plain ASCII letters. See [troubleshooting](troubleshooting.md#pdf-shows-s-instead-of-ș).

## Refreshing the city list

`data/cities_ro.json` is generated and committed. Regenerate it when Wikipedia's list changes, for example when a commune becomes a town:

```bash
.venv/bin/python scripts/build_cities.py            # downloads Wikipedia, geocodes ~320 cities (≈1–2 min)
git diff --stat data/cities_ro.json                 # review before committing
```

The script exits non-zero if any city can't be geocoded, or if its coordinates fall outside Romania. It warns if the total isn't 319. To parse a saved copy of the page instead of downloading it, pass `--wikitext page.wiki`. Restart the app afterwards, because the registry is loaded at startup.

If you remove a city that a quick-select chip uses, the app refuses to start and names the bad preset.

## Updating the logo and favicons

The logo originals live in `assets/brand/` (`logo-mark.jpg`, `logo-horizontal.jpg`, `logo-stacked.jpg`). Every web size is generated from them; never edit the generated files by hand:

```bash
.venv/bin/pip install -r requirements-dev.txt     # includes Pillow
.venv/bin/python scripts/build_brand_assets.py
```

This writes:
- `static/images/`: `favicon.ico` (16/32/48), `favicon-32.png`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `logo-mark-64.png`
- `docs/images/logo-stacked.png` (README header)
- `assets/brand/social-preview.png`: upload it in GitHub → *Settings → General → Social preview*

`tests/api/test_brand_assets.py` checks that every file exists, that each stays within its size budget, and that the page and manifest reference them correctly. After replacing a logo, hard-refresh the browser, because favicons are cached aggressively.

## Updating dependencies

`requirements.txt` (runtime) and `requirements-dev.txt` (tooling) pin exact versions. To upgrade:

```bash
pip install -U flask requests fpdf2
pip freeze | grep -iE '^(flask|requests|fpdf2)=='   # copy these into requirements.txt
```

Then run `pytest` and `pip-audit -r requirements.txt`. The fpdf2 table API (`pdf.table()`) is what most often changes between versions; `tests/pdf` catches that.

**CDN libraries** (GSAP, ApexCharts) are pinned in `templates/index.html` with SRI hashes. When you change a version, recompute the hash, or the browser refuses to load the script:

```bash
curl -s https://cdn.jsdelivr.net/npm/apexcharts@X.Y.Z/dist/apexcharts.min.js | openssl dgst -sha384 -binary | openssl base64 -A
```
