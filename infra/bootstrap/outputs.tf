output "state_bucket" {
  description = "Put this in infra/backend.hcl as `bucket = \"…\"`."
  value       = google_storage_bucket.state.name
}
