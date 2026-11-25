# tflint for infra/ and infra/bootstrap/ (run with --recursive from infra/). CI: the "Infrastructure" job.

config {
  call_module_type = "none" # no child modules here
}

plugin "terraform" {
  enabled = true
  preset  = "recommended" # unused declarations, missing versions, naming conventions, …
}

plugin "google" {
  enabled = true
  version = "0.41.0"
  source  = "github.com/terraform-linters/tflint-ruleset-google"
}
