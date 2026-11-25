# Carpathian Keros on Google Cloud Run. Overview and apply steps: docs/infrastructure.md
#
#   apis.tf      — the Google APIs the rest needs
#   registry.tf  — Artifact Registry for the container images
#   iam.tf       — runtime and deployer service accounts, resource-scoped roles only
#   wif.tf       — Workload Identity Federation: GitHub Actions deploys without any stored key
#   run.tf       — the Cloud Run service (public, scale to zero)
#   budget.tf    — monthly budget alert

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  project_number = data.google_project.this.number
  image_repo     = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}"
}
