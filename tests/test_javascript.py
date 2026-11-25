"""Runs the JavaScript unit tests (tests/js, Node's built-in runner) as part of `pytest`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

JS_DIR = Path(__file__).resolve().parent / "js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_javascript_unit_tests():
    result = subprocess.run(  # noqa: S603 - fixed argv, no user input
        ["node", "--test", *sorted(str(p) for p in JS_DIR.glob("*.test.mjs"))],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
