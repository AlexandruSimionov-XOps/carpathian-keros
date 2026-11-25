"""Carpathian Keros — bilingual (RO/EN) weather dashboard for Romania's official cities.

HTTP layer only (AGENTS.md, Article I-S): it parses params, maps errors to status codes and sets headers.
`create_app()` is the composition root. Collaborators are injected, so tests run without network.
"""

from __future__ import annotations

import io
import logging
import mimetypes
import os
import re
import unicodedata
from datetime import date

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

from services.cities import CityRegistry, city_registry
from services.i18n import normalize_lang
from services.pdf_service import APP_NAME, build_report
from services.weather_service import WeatherService, WeatherServiceError
from services.weather_service import weather_service as default_weather_service

# Quick-select chips, in display order. `query` must resolve in the city registry.
PRESET_CITIES = [
    {"query": "București", "en": "Bucharest", "ro": "București"},
    {"query": "Cluj-Napoca", "en": "Cluj-Napoca", "ro": "Cluj-Napoca"},
    {"query": "Constanța", "en": "Constanța", "ro": "Constanța"},
    {"query": "Iași", "en": "Iași", "ro": "Iași"},
    {"query": "Oradea", "en": "Oradea", "ro": "Oradea"},
    {"query": "Timișoara", "en": "Timișoara", "ro": "Timișoara"},
]

# Article V.2. Scripts: self + the two pinned CDNs, no inline code. Styles need 'unsafe-inline' because the
# Tailwind Play CDN and ApexCharts inject <style>/style attributes (see "Current gaps" in AGENTS.md).
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}

# Public, user-safe text for server-side failures; the details go to the log (Article V.1).
_PUBLIC_5XX_MESSAGE = "The weather service is temporarily unavailable"

log = logging.getLogger("carpathian_keros")

mimetypes.add_type("application/manifest+json", ".webmanifest")  # not in every OS mime database


def _read_version(pyproject: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pyproject.toml")) -> str:
    """The app version from pyproject.toml (the single source of truth, Article IV). Regex, not tomllib: Python 3.10."""
    try:
        with open(pyproject, encoding="utf-8") as fh:
            match = re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.M)
    except OSError:
        return "unknown"
    return match.group(1) if match else "unknown"


APP_VERSION = _read_version()


def _slug(text: str) -> str:
    """ASCII-only filename part: prevents header injection through Content-Disposition."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "city"


def create_app(
    *,
    weather_service: WeatherService | None = None,
    registry: CityRegistry | None = None,
) -> Flask:
    weather = weather_service if weather_service is not None else default_weather_service
    cities = registry if registry is not None else city_registry

    for preset in PRESET_CITIES:  # fail fast on a typo rather than shipping a dead chip
        if cities.resolve(preset["query"]) is None:
            raise RuntimeError(f"Preset city {preset['query']!r} is not in the city registry")

    app = Flask(__name__)
    app.json.ensure_ascii = False

    def error_response(exc: WeatherServiceError):
        if exc.status >= 500:
            log.warning("Upstream failure: %s", exc)
            message = _PUBLIC_5XX_MESSAGE
        else:
            message = str(exc)
        return jsonify({"error": exc.code, "message": message}), exc.status

    @app.after_request
    def add_security_headers(response):
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.get("/")
    def index():
        return render_template("index.html", app_name=APP_NAME, presets=PRESET_CITIES, city_count=len(cities))

    @app.get("/healthz")
    def healthz():
        """Liveness for Cloud Run, CI smoke tests and Docker HEALTHCHECK. Deliberately never calls Open-Meteo:
        an upstream outage must not make the platform restart a healthy container."""
        resp = jsonify({"status": "ok", "version": APP_VERSION})
        resp.cache_control.no_store = True
        return resp

    @app.get("/favicon.ico")
    def favicon():
        """Browsers request /favicon.ico on their own, even with <link rel="icon"> in the page."""
        return send_from_directory(
            os.path.join(app.static_folder, "images"), "favicon.ico", mimetype="image/vnd.microsoft.icon", max_age=86400
        )

    @app.get("/api/cities")
    def api_cities():
        """The full allow-list, for client-side autocomplete (~320 entries, static per deploy)."""
        resp = jsonify({"count": len(cities), "source": cities.source, "cities": cities.suggestions()})
        resp.cache_control.public = True
        resp.cache_control.max_age = 86400
        return resp

    @app.get("/api/weather")
    def api_weather():
        try:
            data = weather.get_weather(request.args.get("city", ""))
        except WeatherServiceError as exc:
            return error_response(exc)
        return jsonify(data)

    @app.get("/api/report/export")
    def api_report_export():
        lang = normalize_lang(request.args.get("lang"))
        try:
            data = weather.get_weather(request.args.get("city", ""))
        except WeatherServiceError as exc:
            return error_response(exc)

        pdf_bytes = build_report(data, lang)
        filename = f"carpathian-keros_{_slug(data['location']['query'])}_{lang}_{date.today():%Y%m%d}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
            max_age=0,
        )

    return app


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("fontTools").setLevel(logging.WARNING)  # fpdf2's font subsetting is very chatty at INFO


app = create_app()  # production wiring, also the WSGI entry point (`gunicorn app:app`)

if __name__ == "__main__":
    _configure_logging()
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
