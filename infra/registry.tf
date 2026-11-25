resource "google_artifact_registry_repository" "images" {
  repository_id = var.service_name
  location      = var.region # same region as Cloud Run: no cross-region transfer
  format        = "DOCKER"
  description   = "Carpathian Keros container images, pushed by the deploy workflow."

  docker_config {
    immutable_tags = true # a version tag, once pushed, always means the same image
  }

  # Trivy already scans every image in CI; Artifact Analysis scanning would be billed per image.
  vulnerability_scanning_config {
    enablement_config = "DISABLED"
  }

  # Stay inside the 0.5 GB free storage: keep the 5 newest images (enough to roll back), delete the rest after 7 days.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-5-newest"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }
  cleanup_policies {
    id     = "delete-older-than-7-days"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "604800s"
    }
  }

  depends_on = [google_project_service.apis]
}
