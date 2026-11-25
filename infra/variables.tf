# Account-specific values (project, billing account) go in terraform.tfvars, which is git-ignored.
# See terraform.tfvars.example.

variable "project_id" {
  description = "Google Cloud project ID."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "A project ID has 6-30 lowercase letters, digits or hyphens, starts with a letter and doesn't end with a hyphen."
  }
}

variable "billing_account_id" {
  description = "Billing account for the budget alert, formatted XXXXXX-XXXXXX-XXXXXX."
  type        = string

  validation {
    condition     = can(regex("^[A-Z0-9]{6}-[A-Z0-9]{6}-[A-Z0-9]{6}$", var.billing_account_id))
    error_message = "The billing account ID looks like XXXXXX-XXXXXX-XXXXXX (letters and digits)."
  }
}

variable "region" {
  description = "Region for Cloud Run and Artifact Registry. europe-west1 (Belgium): Tier 1 pricing, close to Romania."
  type        = string
  default     = "europe-west1"
}

variable "service_name" {
  description = "Cloud Run service and Artifact Registry repository name."
  type        = string
  default     = "carpathian-keros"
}

variable "max_instances" {
  description = "Upper bound on Cloud Run instances, so a traffic spike can't run up a bill."
  type        = number
  default     = 2

  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 2
    error_message = "max_instances must be 1 or 2 (free-tier sizing)."
  }
}

variable "initial_image" {
  description = "Image for the very first revision, before CD has pushed one. CD replaces it; OpenTofu then ignores the image."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "budget_amount" {
  description = "Monthly budget (whole units of budget_currency). Alerts at 50%, 90%, 100% and forecast 100%."
  type        = number
  default     = 1
}

variable "budget_currency" {
  description = "Must be the billing account's currency, or the budget can't be created."
  type        = string
  default     = "EUR"
}

# GitHub identity trusted by Workload Identity Federation. The numeric IDs are what's checked: unlike names,
# they can't be taken over by renaming or re-registering a repository or account.
variable "github_repository" {
  description = "owner/name of the repository whose deploy workflow may deploy."
  type        = string
  default     = "AlexandruSimionov-XOps/carpathian-keros"
}

variable "github_repository_id" {
  description = "Numeric ID of github_repository (GET https://api.github.com/repos/OWNER/NAME → id)."
  type        = string
  default     = "1471744541"
}

variable "github_owner_id" {
  description = "Numeric ID of the repository owner (→ owner.id)."
  type        = string
  default     = "356566022"
}

variable "deploy_workflow" {
  description = "Path of the only workflow allowed to obtain GCP credentials."
  type        = string
  default     = ".github/workflows/deploy.yml"
}
