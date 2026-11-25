"""HTTP layer: routes, the error-code contract, PDF export and security headers (Articles IV and V)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import requests

from app import PRESET_CITIES

ROOT = Path(__file__).resolve().parents[2]


class TestIndex:
    def test_brand_name_is_in_title_and_header(self, client):
        html = client.get("/").get_data(as_text=True)
        assert re.search(r"<title>[^<]*Carpathian Keros", html)
        assert re.search(r"<h1[^>]*>Carpathian Keros</h1>", html)

    def test_presets_are_rendered_in_the_configured_order(self, client):
        html = client.get("/").get_data(as_text=True)
        assert re.findall(r'class="preset-chip" data-city="([^"]+)"', html) == [
            "București",
            "Cluj-Napoca",
            "Constanța",
            "Iași",
            "Oradea",
            "Timișoara",
        ]

    def test_server_rendered_page_is_romanian_before_js_runs(self, client):
        """Default language is RO: the HTML fallback text must already be Romanian (no flash of English)."""
        html = client.get("/").get_data(as_text=True)
        assert '<html lang="ro"' in html
        assert 'placeholder="Caută printre cele 319 orașe din România…"' in html
        assert ">Condiții actuale<" in html and ">Prognoză pe 7 zile<" in html
        visible = re.sub(r"<!--.*?-->", "", html, flags=re.S)  # developer comments may stay in English
        assert "Current conditions" not in visible

    def test_no_static_local_time_line(self, client):
        """Removed: the "Local time HH:MM" line showed the observation time and never ticked, so it looked stuck."""
        html = client.get("/").get_data(as_text=True)
        assert 'id="updated"' not in html

    def test_every_preset_resolves(self, registry):
        assert all(registry.resolve(p["query"]) for p in PRESET_CITIES)

    def test_fonts_are_self_hosted(self, client):
        """GDPR (Article V.5): no visitor IPs sent to Google Fonts."""
        html = client.get("/").get_data(as_text=True)
        css = (ROOT / "static/css/style.css").read_text(encoding="utf-8")
        assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
        for font in re.findall(r"url\(['\"]?/static/fonts/([^'\")]+)", css):
            assert (ROOT / "static/fonts" / font).is_file()
        assert "@font-face" in css

    def test_pinned_cdn_scripts_have_subresource_integrity(self, client):
        """Article V.2. The Tailwind Play CDN is the documented exception (it can't be pinned by hash)."""
        html = client.get("/").get_data(as_text=True)
        for tag in re.findall(r"<script[^>]+src=\"https://[^\"]+\"[^>]*>", html):
            if "cdn.tailwindcss.com" in tag:
                continue
            assert 'integrity="sha384-' in tag, tag
            assert 'crossorigin="anonymous"' in tag, tag


class TestCitiesEndpoint:
    def test_lists_all_cities_and_is_cacheable(self, client):
        resp = client.get("/api/cities")
        assert resp.status_code == 200
        assert resp.json["count"] == 319 == len(resp.json["cities"])
        assert "max-age=86400" in resp.headers["Cache-Control"]

    def test_shared_names_carry_their_county_in_the_query(self, client):
        queries = {c["query"] for c in client.get("/api/cities").json["cities"] if c["name"] == "Ștefănești"}
        assert queries == {"Ștefănești, Argeș", "Ștefănești, Botoșani"}


class TestWeatherEndpoint:
    def test_success(self, client):
        resp = client.get("/api/weather", query_string={"city": "iasi"})
        assert resp.status_code == 200
        assert resp.json["location"]["query"] == "Iași"
        assert "ș" in resp.get_data(as_text=True)  # UTF-8, not \\u escapes

    @pytest.mark.parametrize(
        ("params", "status", "code"),
        [
            ({}, 400, "invalid_city"),
            ({"city": "   "}, 400, "invalid_city"),
            ({"city": "x" * 101}, 400, "invalid_city"),
            ({"city": "Atlantis"}, 404, "city_not_found"),
            ({"city": "Paris"}, 404, "city_not_found"),
            ({"city": "Florești"}, 404, "city_not_found"),
        ],
    )
    def test_error_contract(self, client, params, status, code):
        resp = client.get("/api/weather", query_string=params)
        assert resp.status_code == status
        assert set(resp.json) == {"error", "message"}
        assert resp.json["error"] == code

    def test_upstream_failure_is_502_without_internals(self, client, fake_session):
        fake_session.error = requests.ConnectionError("secret-internal-host:443 refused")
        resp = client.get("/api/weather", query_string={"city": "Iași"})
        assert resp.status_code == 502
        assert resp.json["error"] == "upstream_error"
        assert "secret-internal-host" not in resp.get_data(as_text=True)  # Article V.1: no internals leak


class TestReportExport:
    @pytest.mark.parametrize("lang", ["en", "ro"])
    def test_pdf_download(self, client, lang):
        resp = client.get("/api/report/export", query_string={"city": "Brașov", "lang": lang})
        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"
        assert resp.data[:5] == b"%PDF-"
        assert re.fullmatch(
            rf"attachment; filename=carpathian-keros_brasov_{lang}_\d{{8}}\.pdf", resp.headers["Content-Disposition"]
        )

    def test_unknown_lang_falls_back_to_english(self, client):
        resp = client.get("/api/report/export", query_string={"city": "Iași", "lang": "de"})
        assert "_en_" in resp.headers["Content-Disposition"]

    def test_shared_names_get_distinct_filenames(self, client):
        """Regression: both Ștefănești PDFs used to be named carpathian-keros_stefanesti_*."""
        names = {
            client.get("/api/report/export", query_string={"city": q}).headers["Content-Disposition"]
            for q in ("Ștefănești, Argeș", "Ștefănești, Botoșani")
        }
        assert len(names) == 2
        assert any("stefanesti-botosani" in n for n in names)

    def test_errors_use_the_same_contract(self, client):
        resp = client.get("/api/report/export", query_string={"city": "Atlantis"})
        assert resp.status_code == 404
        assert resp.json["error"] == "city_not_found"


class TestSecurityHeaders:
    @pytest.mark.parametrize(
        "path",
        ["/", "/api/cities", "/api/weather?city=Iasi", "/api/weather", "/api/report/export?city=Iasi", "/healthz"],
    )
    def test_headers_on_every_response(self, client, path):
        headers = client.get(path).headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert headers["X-Frame-Options"] == "DENY"
        csp = headers["Content-Security-Policy"]
        for directive in (
            "default-src 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "base-uri 'self'",
            "connect-src 'self'",
        ):
            assert directive in csp

    def test_csp_allows_only_the_known_script_hosts(self, client):
        csp = client.get("/").headers["Content-Security-Policy"]
        script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src")).split()[1:]
        hosts = {s for s in script_src if s.startswith("https://")}
        assert hosts == {"https://cdn.tailwindcss.com", "https://cdn.jsdelivr.net"}
        assert "'unsafe-inline'" not in script_src and "'unsafe-eval'" not in script_src

    def test_page_has_no_inline_scripts(self, client):
        """Required by the strict script-src: every <script> must load from a src."""
        html = client.get("/").get_data(as_text=True)
        assert re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html) == []

    def test_upstream_details_are_logged_not_returned(self, client, fake_session, caplog):
        fake_session.error = requests.ConnectionError("boom-detail")
        resp = client.get("/api/weather", query_string={"city": "Iași"})
        assert "boom-detail" not in resp.get_data(as_text=True)
        assert "boom-detail" in caplog.text


class TestHealthz:
    """Liveness endpoint for Cloud Run, CI smoke tests and Docker HEALTHCHECK."""

    def test_reports_ok_and_the_app_version(self, client):
        tomllib = pytest.importorskip("tomllib")
        version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json == {"status": "ok", "version": version}

    def test_never_calls_the_weather_provider(self, client, fake_session):
        """A health check must not depend on Open-Meteo, or its outages would restart healthy containers."""
        fake_session.error = requests.ConnectionError("down")
        assert client.get("/healthz").status_code == 200
        assert fake_session.calls == []

    def test_is_not_cached(self, client):
        assert "no-store" in client.get("/healthz").headers["Cache-Control"]


def test_version_is_declared_once_and_matches_the_changelog():
    """Article IV: pyproject.toml is the single source of truth; CHANGELOG.md documents it."""
    tomllib = pytest.importorskip("tomllib")  # Python 3.11+
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M)
