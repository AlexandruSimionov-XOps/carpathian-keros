terraform {
  required_version = ">= 1.9.0" # OpenTofu

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.12"
    }
  }

  # State in the bucket created by infra/bootstrap. Partial config: `tofu init -backend-config=backend.hcl`
  # (backend.hcl is git-ignored; see backend.hcl.example).
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region

  # Bill API quota to this project, not to gcloud's shared client project. Required for the Billing Budgets API
  # when running with user credentials (gcloud auth application-default login).
  user_project_override = true
  billing_project       = var.project_id

  default_labels = {
    app        = "carpathian-keros"
    managed-by = "opentofu"
  }
}
