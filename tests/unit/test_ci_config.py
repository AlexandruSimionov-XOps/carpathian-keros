"""CI and supply-chain policy, checked in code so it can't silently erode (AGENTS.md, Articles III and V)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
SHA_PIN = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
REQUIRED_JOBS = {"lint", "test", "audit", "secrets", "docker", "e2e"}


def load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    # PyYAML reads the bare key `on:` as the boolean True.
    if True in data:
        data["on"] = data.pop(True)
    return data


def steps(workflow: dict):
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            yield job_name, step


@pytest.fixture(scope="module")
def ci() -> dict:
    return load(ROOT / ".github/workflows/ci.yml")


def test_workflows_exist():
    assert ROOT / ".github/workflows/ci.yml" in WORKFLOWS


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_full_commit_sha(path):
    """Tags like @v4 can be moved by whoever controls the action's repo; a 40-char SHA can't (supply-chain safety)."""
    unpinned = [
        f"{job}: {step['uses']}"
        for job, step in steps(load(path))
        if "uses" in step and not step["uses"].startswith(("./", "docker://")) and not SHA_PIN.match(step["uses"])
    ]
    assert unpinned == []


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_default_token_permissions_are_read_only(path):
    """Least privilege (AGENTS.md V.2): the workflow token can read the repo and nothing else unless a job says so."""
    assert load(path)["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_a_timeout(path):
    jobs = load(path)["jobs"]
    assert {name for name, job in jobs.items() if "timeout-minutes" not in job} == set()


def test_ci_runs_on_pull_requests_and_pushes_to_both_long_lived_branches(ci):
    on = ci["on"]
    assert set(on["pull_request"]["branches"]) == {"development", "main"}
    assert set(on["push"]["branches"]) == {"development", "main"}
    assert "workflow_dispatch" in on


def test_ci_has_all_required_jobs(ci):
    assert set(ci["jobs"]) >= REQUIRED_JOBS


def test_superseded_runs_are_cancelled(ci):
    assert ci["concurrency"]["cancel-in-progress"] is True


def test_no_pull_request_target_trigger():
    """pull_request_target runs fork code with a write token: a classic CI takeover. Never use it here."""
    assert all("pull_request_target" not in load(p)["on"] for p in WORKFLOWS)


def test_docker_job_builds_tests_and_scans_the_image(ci):
    docker_job = {"jobs": {"docker": ci["jobs"]["docker"]}}
    run = " ".join(step.get("run", "") + " " + step.get("uses", "") for _, step in steps(docker_job))
    assert "docker build" in run
    assert "pytest" in run and "-m docker" in run
    assert "trivy" in run.lower()
    assert "hadolint" in run.lower()


def test_dockerfile_base_images_are_pinned_by_digest():
    """A tag like python:3.14-slim can change under us; a digest can't. Dependabot bumps the digest."""
    froms = re.findall(r"^FROM\s+(\S+)", (ROOT / "Dockerfile").read_text(encoding="utf-8"), re.M)
    assert froms, "no FROM lines"
    assert all(re.search(r"@sha256:[0-9a-f]{64}$", f) for f in froms), froms


def test_dependabot_watches_pip_actions_and_docker_and_targets_development():
    config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text(encoding="utf-8"))
    ecosystems = {u["package-ecosystem"]: u for u in config["updates"]}
    assert set(ecosystems) == {"pip", "github-actions", "docker"}
    assert all(u["target-branch"] == "development" for u in ecosystems.values())
