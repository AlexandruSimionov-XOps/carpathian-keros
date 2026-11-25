"""Brand assets: favicons, header logo, web manifest, README images (built by scripts/build_brand_assets.py)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "static/images"

# (file, max bytes): keep what browsers download small.
SERVED_ASSETS = [
    ("favicon.ico", 20_000),
    ("favicon-32.png", 5_000),
    ("apple-touch-icon.png", 40_000),
    ("icon-192.png", 40_000),
    ("icon-512.png", 200_000),
    ("logo-mark-64.png", 12_000),
]


@pytest.mark.parametrize(("name", "max_bytes"), SERVED_ASSETS)
def test_served_images_exist_and_are_small(name, max_bytes):
    path = IMAGES / name
    assert path.is_file(), f"missing {path}"
    assert path.stat().st_size <= max_bytes, f"{name} is {path.stat().st_size} bytes"


def test_head_links_the_favicon_set_and_manifest(client):
    html = client.get("/").get_data(as_text=True)
    assert 'rel="icon" href="/static/images/favicon.ico" sizes="any"' in html
    assert 'rel="icon" type="image/png" sizes="32x32" href="/static/images/favicon-32.png"' in html
    assert 'rel="apple-touch-icon" href="/static/images/apple-touch-icon.png"' in html
    assert 'rel="manifest" href="/static/site.webmanifest"' in html
    assert "data:image/svg+xml" not in html  # the old inline SVG favicon is gone


def test_header_shows_the_logo_mark_and_keeps_the_brand_name_as_text(client):
    html = client.get("/").get_data(as_text=True)
    assert re.search(r'<img[^>]+src="/static/images/logo-mark-64.png"[^>]+alt=""', html)
    assert re.search(r"<h1[^>]*>Carpathian Keros</h1>", html)


def test_root_favicon_ico_is_served(client):
    """Browsers request /favicon.ico on their own; it must not 404."""
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.mimetype in {"image/vnd.microsoft.icon", "image/x-icon"}


def test_web_manifest_is_valid_and_its_icons_exist(client):
    manifest = json.loads((ROOT / "static/site.webmanifest").read_text(encoding="utf-8"))
    assert manifest["name"] == "Carpathian Keros"
    assert {"192x192", "512x512"} <= {i["sizes"] for i in manifest["icons"]}
    for icon in manifest["icons"]:
        assert client.get(icon["src"]).status_code == 200, icon["src"]


def test_readme_images_exist():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    local = [
        src
        for src in re.findall(r'(?:src="|\]\()([^")]+\.(?:png|jpe?g|webp|svg|gif))', readme)
        if not src.startswith("http")
    ]
    assert local, "README should show the banner"
    for src in local:
        assert (ROOT / src).is_file(), src


def test_downloaded_file_metadata_is_never_committed():
    """Windows adds `<file>:Zone.Identifier` when files are copied into WSL; they mustn't reach the repo."""
    assert "Zone.Identifier" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_readme_header_is_the_stacked_logo():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    first_image = re.search(r'<img src="([^"]+)"', readme)
    assert first_image and first_image.group(1) == "docs/images/logo-stacked.png"
    path = ROOT / "docs/images/logo-stacked.png"
    assert path.stat().st_size <= 250_000, f"{path.name} is {path.stat().st_size} bytes"
    assert not (ROOT / "docs/images/banner.jpg").exists(), "the old banner is replaced; don't keep a dead file"
