# Least privilege (AGENTS.md V.2): two dedicated service accounts, and every grant is scoped to one resource.
# No project-wide roles, no service-account keys (tests/unit/test_infra_policy.py enforces both).

# The identity the app runs as. It has no roles at all: the app calls only Open-Meteo and needs nothing in GCP.
resource "google_service_account" "runtime" {
  account_id   = "ck-runtime"
  display_name = "Carpathian Keros runtime"
  description  = "Cloud Run runs the app as this account. Deliberately has no roles."
  depends_on   = [google_project_service.apis]
}

# The identity GitHub Actions' deploy workflow becomes (via wif.tf). It may push images and roll out revisions.
resource "google_service_account" "deployer" {
  account_id   = "ck-deployer"
  display_name = "Carpathian Keros deployer"
  description  = "Impersonated by GitHub Actions (Workload Identity Federation). Pushes images, deploys revisions."
  depends_on   = [google_project_service.apis]
}

# Push images to this one repository.
resource "google_artifact_registry_repository_iam_member" "deployer_push" {
  repository = google_artifact_registry_repository.images.name
  location   = google_artifact_registry_repository.images.location
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

# Deploy new revisions of this one service (run.developer can't change IAM, so the deployer can't make itself admin).
resource "google_cloud_run_v2_service_iam_member" "deployer" {
  name     = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

# A revision runs as ck-runtime; deploying it requires permission to "act as" that account, and only that one.
resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
