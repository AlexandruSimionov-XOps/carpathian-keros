# Third-party notices

Carpathian Keros's own source code is licensed under the [MIT License](LICENSE). The repository also contains, or uses at runtime, third-party material under its **own** licence. The MIT licence does **not** apply to these.

## Project brand assets

The Carpathian Keros logos (`assets/brand/`) and the images generated from them (`static/images/`, `docs/images/logo-stacked.png`) are the project's own artwork, by Alexandru Simionov, and part of this repository.

## Bundled in this repository

| Material | Path | Source | Licence | Obligations |
|---|---|---|---|---|
| List of Romanian cities, counties and 2021 populations | `data/cities_ro.json` | [Wikipedia: Lista orașelor din România](https://ro.wikipedia.org/wiki/Lista_ora%C8%99elor_din_Rom%C3%A2nia) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Attribution (shown in the UI footer and the file's `source`/`license` fields). **ShareAlike:** if you redistribute this data file, modified or not, it stays CC BY-SA 4.0. |
| City coordinates and elevations | `data/cities_ro.json` | [Open-Meteo Geocoding API](https://open-meteo.com/) (GeoNames data) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Attribution |
| Recorded forecast used by the tests | `tests/fixtures/open_meteo_forecast.json` | [Open-Meteo Forecast API](https://open-meteo.com/) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Attribution |
| Inter typeface (woff2 subsets) | `static/fonts/` | [The Inter Project](https://github.com/rsms/inter), via Google Fonts | [SIL Open Font License 1.1](static/fonts/OFL.txt) | Keep `OFL.txt` with the font files. The font may not be sold on its own. |

## Loaded at runtime (not redistributed)

| Library / service | Licence / terms |
|---|---|
| [Open-Meteo](https://open-meteo.com/) weather API | Data under CC BY 4.0. The **free API is for non-commercial use only**; commercial deployments need an [Open-Meteo API subscription](https://open-meteo.com/en/pricing). |
| [Tailwind CSS](https://tailwindcss.com/) (Play CDN) | MIT |
| [GSAP](https://gsap.com/) 3.12.5 (jsDelivr) | [GSAP Standard License](https://gsap.com/standard-license) |
| [ApexCharts](https://apexcharts.com/) 3.54.1 (jsDelivr) | MIT |

## Python dependencies (installed from PyPI, not redistributed)

| Package | Licence |
|---|---|
| Flask | BSD-3-Clause |
| requests | Apache-2.0 |
| fpdf2 | LGPL-3.0 (used unmodified, as a library) |
| Pillow *(runtime via fpdf2; also `scripts/build_brand_assets.py`)* | MIT-CMU (HPND) |
| fontTools *(runtime via fpdf2)* | MIT |
| gunicorn *(production server)* | MIT |
| pytest, ruff *(dev)* | MIT |
| pypdf *(dev)* | BSD-3-Clause |
| pip-audit *(dev)* | Apache-2.0 |
| PyYAML *(dev)* | MIT |
| Playwright *(e2e tests)* | Apache-2.0 |

CI also runs hadolint (GPL-3.0), gitleaks (MIT) and Trivy (Apache-2.0) as containers. They check the code but aren't part of it or of the image.

The infrastructure code in `infra/` uses OpenTofu, the `hashicorp/google` provider, tflint and the tflint Google ruleset (all MPL-2.0). These are tools; none of them is redistributed.

## In the Docker image

A **published** image redistributes the runtime packages above, plus:

| Component | Licence |
|---|---|
| Python (`python:3.14-slim` base image) | PSF License |
| Debian base system packages | Various free licences (see `/usr/share/doc/*/copyright` in the image) |
| DejaVu fonts (`fonts-dejavu-core`, for the PDF reports) | Bitstream Vera / Arev licence (free, redistributable) |

Their licence texts ship inside the image: Debian copies under `/usr/share/doc/`, and Python packages under `site-packages/*.dist-info/`.
