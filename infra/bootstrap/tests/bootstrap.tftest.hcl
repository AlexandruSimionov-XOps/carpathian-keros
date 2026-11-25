# OpenTofu tests for the state bucket. Run from infra/bootstrap/:  tofu init && tofu test  (provider mocked)

mock_provider "google" {}

variables {
  project_id = "carpathian-keros"
}

run "foundation_apis_are_enabled_before_the_main_configuration_plans" {
  command = apply

  # Regression: infra/ reads the project (data "google_project") during `plan`, which needs the Resource Manager
  # API. Enabling it in infra/ itself only happens during `apply`, so a fresh project failed with SERVICE_DISABLED.
  assert {
    condition     = contains(keys(google_project_service.foundation), "cloudresourcemanager.googleapis.com")
    error_message = "The bootstrap must enable the Resource Manager API (infra/ reads the project while planning)."
  }
  assert {
    condition     = contains(keys(google_project_service.foundation), "serviceusage.googleapis.com")
    error_message = "The bootstrap must enable the Service Usage API (infra/ enables the other APIs through it)."
  }
  assert {
    condition     = contains(keys(google_project_service.foundation), "storage.googleapis.com")
    error_message = "The state bucket needs the Storage API."
  }
  assert {
    condition     = alltrue([for s in google_project_service.foundation : s.disable_on_destroy == false])
    error_message = "Foundation APIs are never disabled on destroy (other things depend on them)."
  }
}

run "state_bucket_is_private_versioned_and_regional" {
  command = apply

  assert {
    condition     = google_storage_bucket.state.name == "carpathian-keros-tfstate"
    error_message = "Bucket name is derived from the project ID (globally unique)."
  }
  assert {
    condition     = google_storage_bucket.state.location == "EUROPE-WEST1"
    error_message = "State lives in the same region as the service."
  }
  assert {
    condition     = google_storage_bucket.state.versioning[0].enabled
    error_message = "Versioning lets a corrupted or deleted state be recovered."
  }
  assert {
    condition     = google_storage_bucket.state.public_access_prevention == "enforced"
    error_message = "State can contain resource details: never public."
  }
  assert {
    condition     = google_storage_bucket.state.uniform_bucket_level_access
    error_message = "IAM only, no per-object ACLs."
  }
  assert {
    condition     = google_storage_bucket.state.force_destroy == false
    error_message = "Deleting the bucket must never silently delete the state."
  }
}
