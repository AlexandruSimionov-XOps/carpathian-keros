terraform {
  required_version = ">= 1.9.0" # OpenTofu

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.12"
    }
  }

  # The bootstrap starts with local state (it creates the bucket the main config stores its state in).
  # After the first apply, it migrates its own state into that bucket: see docs/infrastructure.md.
  # backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
