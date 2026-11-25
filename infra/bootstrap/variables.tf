variable "project_id" {
  description = "Google Cloud project ID (e.g. carpathian-keros)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "A project ID has 6-30 lowercase letters, digits or hyphens, starts with a letter and doesn't end with a hyphen."
  }
}

variable "region" {
  description = "Region for the state bucket; the same as the service."
  type        = string
  default     = "europe-west1"
}
