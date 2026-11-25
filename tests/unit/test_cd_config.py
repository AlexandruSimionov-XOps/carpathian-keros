"""Continuous deployment policy (.github/workflows/deploy.yml): how a release reaches Cloud Run.

Generic rules shared with CI (SHA-pinned actions, read-only default token, timeouts, short names) are checked for
every workflow in test_ci_config.py; these are the deploy-specific ones.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / ".github/workflows/deploy.yml"


@pytest.fixture(scope="module")
def wf() -> dict:
    data = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    data["on"] = data.pop(True)  # PyYAML reads the key `on` as True
    return data


@pytest.fixture(scope="module")
def job(wf) -> dict:
    assert list(wf["jobs"]) == ["deploy"]
    return wf["jobs"]["deploy"]


def step_index(job: dict, needle: str) -> int:
    for i, step in enumerate(job["steps"]):
        if needle in (step.get("run", "") + step.get("uses", "") + str(step.get("with", ""))):
            return i
    raise AssertionError(f"no step containing {needle!r}")


def test_deploys_only_release_tags_or_a_manual_run(wf):
    assert wf["on"]["push"] == {"tags": ["v*"]}
    assert "workflow_dispatch" in wf["on"]
    assert "pull_request" not in wf["on"], "pull requests must never deploy"


def test_only_the_deploy_job_can_request_an_oidc_token(wf, job):
    assert wf["permissions"] == {"contents": "read"}
    assert job["permissions"] == {"contents": "read", "id-token": "write"}


def test_authenticates_with_workload_identity_federation_never_a_key(job):
    text = DEPLOY.read_text(encoding="utf-8")
    assert "credentials_json" not in text and "secrets." not in text, "no stored GCP keys or secrets"
    auth = job["steps"][step_index(job, "google-github-actions/auth@")]
    assert auth["with"]["workload_identity_provider"] == "${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}"
    assert auth["with"]["service_account"] == "${{ vars.GCP_DEPLOYER_SERVICE_ACCOUNT }}"


def test_deploys_are_never_cancelled_halfway(wf):
    assert wf["concurrency"]["cancel-in-progress"] is False


def test_uses_the_production_environment_with_the_public_url(job):
    assert job["environment"] == {"name": "production", "url": "https://carpathian-keros.cloud.run"}


def test_release_tag_must_match_the_project_version(job):
    check = job["steps"][step_index(job, "pyproject.toml")]["run"]
    assert "GITHUB_REF_NAME" in check and "exit 1" in check


def test_order_scan_before_push_and_smoke_test_before_traffic(job):
    """Nothing unscanned is pushed; nothing untested gets traffic (blue/green via a no-traffic candidate)."""
    build = step_index(job, "docker build")
    scan = step_index(job, "--severity HIGH,CRITICAL")
    push = step_index(job, "docker push")
    candidate = step_index(job, "no_traffic")
    smoke_candidate = step_index(job, 'smoke_test.py "$CANDIDATE_URL"')
    promote = step_index(job, "--to-latest")
    verify = step_index(job, 'smoke_test.py "$PUBLIC_URL"')
    assert build < scan < push < candidate < smoke_candidate < promote < verify


def test_candidate_gets_no_traffic_and_keeps_the_service_config(job):
    deploy = job["steps"][step_index(job, "google-github-actions/deploy-cloudrun@")]["with"]
    assert deploy["no_traffic"] is True and deploy["tag"] == "candidate"
    assert deploy["skip_default_labels"] is True, "extra labels would show up as drift in `tofu plan`"
    assert not {"env_vars", "secrets", "flags", "labels"} & set(deploy), "service config belongs to OpenTofu"


def test_rolls_back_if_the_public_check_fails_after_promotion(job):
    rollback = job["steps"][step_index(job, "--to-revisions")]
    assert "failure()" in rollback["if"] and "promote" in rollback["if"]


def test_no_untrusted_github_context_in_run_scripts(job):
    """Script-injection safety (AGENTS.md V.5): event data and outputs go through `env:`, never inline."""
    for step in job["steps"]:
        assert "${{" not in step.get("run", ""), step.get("name")
