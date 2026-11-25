# OpenTofu tests for the state bucket. Run from infra/bootstrap/:  tofu init && tofu test  (provider mocked)

mock_provider "google" {}

variables {
  project_id = "carpathian-keros"
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
