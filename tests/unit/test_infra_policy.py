"""Static policy checks on the OpenTofu code in infra/ (AGENTS.md V.2/V.3).

Complements `tofu test`, which checks values: this checks for things that must never appear at all."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra"
TF_FILES = sorted(p for p in INFRA.rglob("*.tf") if ".terraform" not in p.parts)


def all_tf() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in TF_FILES)


def test_infra_code_exists():
    assert (INFRA / "main.tf").is_file() and (INFRA / "bootstrap/main.tf").is_file()


def test_no_service_account_keys_anywhere():
    """GitHub authenticates through Workload Identity Federation; a downloadable key would be a long-lived secret."""
    assert "google_service_account_key" not in all_tf()


def test_no_project_wide_iam_grants():
    """Every grant is scoped to one resource (repository, service, service account), never the whole project."""
    assert not re.search(r'resource\s+"google_project_iam_(member|binding|policy)"', all_tf())


def test_all_users_is_only_the_public_cloud_run_invoker():
    code = all_tf()
    public_grants = re.findall(r'resource\s+"(\w+)"\s+"\w+"\s*\{[^}]*"allUsers"', code, re.S)
    assert public_grants == ["google_cloud_run_v2_service_iam_member"]
    assert "allAuthenticatedUsers" not in code


def test_cloud_run_lets_cd_own_the_image():
    """OpenTofu owns the service, CD owns the image version: without ignore_changes the next `tofu apply`
    would roll production back to the placeholder image."""
    run_tf = (INFRA / "run.tf").read_text(encoding="utf-8")
    assert re.search(r"ignore_changes\s*=\s*\[[^\]]*template\[0\]\.containers\[0\]\.image", run_tf, re.S)


def test_provider_versions_are_pinned_and_locked():
    for module in (INFRA, INFRA / "bootstrap"):
        versions = (module / "versions.tf").read_text(encoding="utf-8")
        assert re.search(r'version\s*=\s*"~>\s*8\.\d+"', versions), module
        assert (module / ".terraform.lock.hcl").is_file(), f"commit {module}/.terraform.lock.hcl"


@pytest.mark.parametrize("pattern", [r"\b179143178348\b", r"\b[A-F0-9]{6}-[A-F0-9]{6}-[A-F0-9]{6}\b"])
def test_no_account_specific_ids_in_tf_code(pattern):
    """Project number and billing account come from variables (terraform.tfvars, git-ignored), not from code.
    Test fixtures in infra/tests may use mock values."""
    assert not re.search(pattern, all_tf())


def test_local_state_and_variable_files_are_git_ignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("*.tfstate", ".terraform/", "*.tfvars", "backend.hcl"):
        assert pattern in ignored, pattern
