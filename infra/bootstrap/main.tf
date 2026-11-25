# The GCS bucket that holds the OpenTofu state of infra/ (and, after migration, of this bootstrap too).
# Created once, by hand, from a laptop: everything else is created by infra/ using this state.

# Foundation APIs: everything else depends on them, so they're enabled here, before infra/ ever runs.
# infra/ reads the project (data "google_project") while planning, which needs Resource Manager; and it enables
# its own APIs through Service Usage. Enabling these from infra/ itself would only happen at apply time: too late.
resource "google_project_service" "foundation" {
  for_each = toset([
    "storage.googleapis.com",              # the state bucket
    "cloudresourcemanager.googleapis.com", # reading project metadata (infra/ data sources)
    "serviceusage.googleapis.com",         # enabling the other APIs
  ])

  service            = each.value
  disable_on_destroy = false
}

# The Storage API used to be a single resource; this keeps the existing state (no disable/re-enable).
moved {
  from = google_project_service.storage
  to   = google_project_service.foundation["storage.googleapis.com"]
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

  depends_on = [google_project_service.foundation]
}
