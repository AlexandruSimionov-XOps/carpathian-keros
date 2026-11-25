# Storage, Resource Manager and Service Usage are enabled by infra/bootstrap (needed before this configuration plans).
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",              # Cloud Run
    "artifactregistry.googleapis.com", # container images
    "iam.googleapis.com",              # service accounts, Workload Identity pools
    "iamcredentials.googleapis.com",   # short-lived tokens for the deployer
    "sts.googleapis.com",              # exchanging GitHub's OIDC token
    "billingbudgets.googleapis.com",   # the budget alert
  ])

  service            = each.value
  disable_on_destroy = false # turning an API off can break things that aren't managed here
}
