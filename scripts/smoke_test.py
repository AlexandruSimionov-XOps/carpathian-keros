"""Post-deploy smoke test: is the expected version live, and does it work end to end?

    python scripts/smoke_test.py https://carpathian-keros.cloud.run 1.1.0

Used by .github/workflows/deploy.yml twice: on the candidate revision (before it gets traffic) and on the public URL
(after). Standard library only, so it runs anywhere. Retries cover cold starts and rollout delays.
Exit code 0 = all checks passed, 1 = a check failed.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message

USER_AGENT = "carpathian-keros-smoke-test"  # generic on purpose: no personal details in outbound requests (V.3)


class SmokeTestError(Exception):
    """A check failed after all retries."""


class CheckFailed(Exception):
    """One attempt of one check failed (retried until the attempts run out)."""


def _require(ok: bool, message: str) -> None:
    # Not `assert`: Python drops asserts under -O, and a safety check must never pass silently.
    if not ok:
        raise CheckFailed(message)


def _get(url: str, timeout: float) -> tuple[int, Message, bytes]:
    # Headers stay a Message, whose lookups ignore case: Cloud Run (HTTP/2) sends lowercase names, and a plain
    # dict(...) copy made "Content-Security-Policy" look missing on the first deploy.
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 - http(s) URL from the caller
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def _retry(name: str, check: Callable[[], str], attempts: int, delay: float) -> str:
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            return check()
        except (CheckFailed, OSError, ValueError, KeyError) as exc:
            last_error = str(exc) or type(exc).__name__
            if attempt < attempts:
                time.sleep(delay)
    raise SmokeTestError(f"{name}: {last_error} (after {attempts} attempt(s))")


def run_checks(
    base_url: str, expected_version: str, *, attempts: int = 10, delay: float = 3.0, timeout: float = 15.0
) -> list[tuple[str, str]]:
    """Run every check; return [(name, detail)] or raise SmokeTestError on the first failure."""
    base = base_url.rstrip("/")

    def health() -> str:
        status, _, body = _get(f"{base}/health", timeout)
        _require(status == 200, f"HTTP {status}")
        data = json.loads(body)
        _require(data.get("status") == "ok", f"status {data.get('status')!r}")
        _require(
            data.get("version") == expected_version,
            f"version {data.get('version')!r} is live, expected {expected_version!r}",
        )
        return f"ok, version {expected_version}"

    def dashboard() -> str:
        status, headers, body = _get(f"{base}/", timeout)
        _require(status == 200, f"HTTP {status}")
        _require(b"Carpathian Keros" in body, "brand name missing from the page")
        _require("default-src 'self'" in headers.get("Content-Security-Policy", ""), "Content-Security-Policy missing")
        return "page served with security headers"

    def weather() -> str:
        status, _, body = _get(f"{base}/api/weather?city=Iasi", timeout)
        _require(status == 200, f"HTTP {status}: {body[:120]!r}")
        data = json.loads(body)
        _require(data["location"]["name"] == "Iași", f"unexpected city {data['location']['name']!r}")
        _require(len(data["daily"]) == 7, "expected a 7-day forecast")
        return f"Iași, {data['current']['temperature']} °C"

    def pdf() -> str:
        status, _, body = _get(f"{base}/api/report/export?city=Iasi&lang=ro", timeout)
        _require(status == 200, f"HTTP {status}")
        _require(body[:5] == b"%PDF-", "not a PDF")
        return f"{len(body) // 1024} KB PDF"

    results = []
    for name, check in (("health", health), ("dashboard", dashboard), ("weather", weather), ("pdf", pdf)):
        results.append((name, _retry(name, check, attempts, delay)))
    return results


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    url, version = argv[1], argv[2]
    try:
        for name, detail in run_checks(url, version):
            print(f"✓ {name:<10} {detail}")
    except SmokeTestError as exc:
        print(f"::error title=Smoke test failed::{url}: {exc}")  # shows as an annotation in GitHub Actions
        return 1
    print(f"Smoke test passed: {url} runs {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
