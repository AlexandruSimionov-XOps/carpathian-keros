# Workload Identity Federation: the deploy workflow trades GitHub's short-lived OIDC token for short-lived GCP
# credentials. No key exists anywhere, so there's nothing to leak or rotate.
#
# Trust is as narrow as GitHub's token allows. All of these must hold:
#   - the repository and its owner, by numeric ID (names can be renamed and re-registered by someone else)
#   - the workflow file is deploy.yml in this repository (not any workflow a contributor might add)
#   - the run is for a release tag (v*) or main
#
# Note: a deleted pool keeps its ID reserved for 30 days; recreating "github" sooner fails.

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  description               = "OIDC identities from GitHub Actions."
  depends_on                = [google_project_service.apis]
}

locals {
  wif_condition = join(" && ", [
    "assertion.repository_id == '${var.github_repository_id}'",
    "assertion.repository_owner_id == '${var.github_owner_id}'",
    "assertion.job_workflow_ref.startsWith('${var.github_repository}/${var.deploy_workflow}@')",
    "(assertion.ref == 'refs/heads/main' || assertion.ref.startsWith('refs/tags/v'))",
  ])
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "carpathian-keros"
  display_name                       = "carpathian-keros deploys"
  description                        = "Only ${var.github_repository}'s ${var.deploy_workflow} on main or v* tags."

  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
    "attribute.ref"                 = "assertion.ref"
    "attribute.workflow_ref"        = "assertion.job_workflow_ref"
  }
  attribute_condition = local.wif_condition

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Identities that pass the condition above may act as the deployer, and only the deployer.
resource "google_service_account_iam_member" "github_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}
