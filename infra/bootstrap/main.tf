# The GCS bucket that holds the OpenTofu state of infra/ (and, after migration, of this bootstrap too).
# Created once, by hand, from a laptop: everything else is created by infra/ using this state.

resource "google_project_service" "storage" {
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_storage_bucket" "state" {
  name     = "${var.project_id}-tfstate" # bucket names are global; the project ID makes it unique
  location = upper(var.region)

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true       # IAM only, no per-object ACLs
  public_access_prevention    = "enforced" # state can describe resources: never public
  force_destroy               = false      # deleting the bucket must never silently delete the state

  versioning {
    enabled = true # recover from a corrupted or deleted state file
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 10 # keep the 10 most recent previous versions of each state file
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    app        = "carpathian-keros"
    managed-by = "opentofu"
  }

  depends_on = [google_project_service.storage]
}
