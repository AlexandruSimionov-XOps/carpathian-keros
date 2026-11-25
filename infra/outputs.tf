# The deploy workflow needs the first four as GitHub repository variables (not secrets: none of them grants access
# on its own; Workload Identity Federation checks the workflow's identity). See docs/infrastructure.md.

output "workload_identity_provider" {
  description = "GitHub variable GCP_WORKLOAD_IDENTITY_PROVIDER."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "GitHub variable GCP_DEPLOYER_SERVICE_ACCOUNT."
  value       = google_service_account.deployer.email
}

output "image_repository" {
  description = "GitHub variable GCP_IMAGE_REPOSITORY (images are pushed as <this>/app:<version>)."
  value       = local.image_repo
}

output "service_name" {
  description = "GitHub variable GCP_SERVICE_NAME."
  value       = google_cloud_run_v2_service.app.name
}

output "service_url" {
  description = "The public *.run.app URL (HTTPS, managed certificate)."
  value       = google_cloud_run_v2_service.app.uri
}

output "runtime_service_account" {
  description = "The identity the app runs as (no roles)."
  value       = google_service_account.runtime.email
}
