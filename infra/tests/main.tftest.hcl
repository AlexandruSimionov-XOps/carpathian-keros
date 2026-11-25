# OpenTofu tests for the Cloud Run infrastructure. Run from infra/:  tofu init -backend=false && tofu test
# The Google provider is mocked: nothing is created, no credentials or network calls are needed.

mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      number = "179143178348"
    }
  }
  mock_resource "google_service_account" {
    defaults = {
      email = "mock-sa@carpathian-keros.iam.gserviceaccount.com"
      name  = "projects/carpathian-keros/serviceAccounts/mock-sa@carpathian-keros.iam.gserviceaccount.com"
    }
  }
  mock_resource "google_iam_workload_identity_pool" {
    defaults = {
      name = "projects/179143178348/locations/global/workloadIdentityPools/github"
    }
  }
}

# Every value the assertions depend on is set here: `tofu test` also loads a local terraform.tfvars (git-ignored,
# account-specific), and the tests must give the same result on every machine and in CI.
variables {
  project_id         = "carpathian-keros"
  billing_account_id = "ABCDEF-123456-ABCDEF"
  region             = "europe-west1"
  max_instances      = 2
  budget_amount      = 1
  budget_currency    = "EUR"
}

run "workload_identity_trusts_only_this_repository_and_its_deploy_workflow" {
  command = apply

  assert {
    condition     = strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "assertion.repository_id == '1471744541'")
    error_message = "WIF must trust the repository by its immutable numeric ID."
  }
  assert {
    condition     = strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "assertion.repository_owner_id == '356566022'")
    error_message = "WIF must trust the owner by its immutable numeric ID."
  }
  assert {
    condition     = strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "AlexandruSimionov-XOps/carpathian-keros/.github/workflows/deploy.yml@")
    error_message = "Only the deploy workflow may obtain GCP credentials."
  }
  assert {
    condition     = strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "refs/tags/v")
    error_message = "Deploys must come from release tags."
  }
  assert {
    condition     = google_iam_workload_identity_pool_provider.github.oidc[0].issuer_uri == "https://token.actions.githubusercontent.com"
    error_message = "The provider must trust GitHub's OIDC issuer only."
  }
  assert {
    condition     = google_service_account_iam_member.github_deployer.member == "principalSet://iam.googleapis.com/projects/179143178348/locations/global/workloadIdentityPools/github/attribute.repository_id/1471744541"
    error_message = "Only identities from this repository may impersonate the deployer."
  }
  assert {
    condition     = google_service_account_iam_member.github_deployer.role == "roles/iam.workloadIdentityUser"
    error_message = "GitHub gets workloadIdentityUser on the deployer, nothing broader."
  }
}

run "cloud_run_fits_the_free_tier_and_is_hardened" {
  command = apply

  assert {
    condition     = google_cloud_run_v2_service.app.location == "europe-west1"
    error_message = "Region must be europe-west1."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.template[0].scaling[0].min_instance_count == 0
    error_message = "Scale to zero: no idle instances (free tier)."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.template[0].scaling[0].max_instance_count <= 2
    error_message = "Cap instances so a traffic spike can't run up a bill."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.template[0].containers[0].resources[0].cpu_idle == true
    error_message = "CPU only while handling requests (request-based billing)."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.template[0].containers[0].resources[0].limits["memory"] == "512Mi"
    error_message = "512 MiB is enough for the app and stays well inside the free allowance."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.template[0].containers[0].ports[0].container_port == 8080
    error_message = "The image listens on 8080."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.template[0].containers[0].startup_probe[0].http_get[0].path == "/healthz"
    error_message = "Startup probe must use the dependency-free /healthz."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.template[0].containers[0].liveness_probe[0].http_get[0].path == "/healthz"
    error_message = "Liveness probe must use the dependency-free /healthz."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.template[0].service_account == google_service_account.runtime.email
    error_message = "The app runs as the dedicated runtime service account, not the default compute account."
  }
  assert {
    condition     = google_cloud_run_v2_service.app.ingress == "INGRESS_TRAFFIC_ALL"
    error_message = "Public website."
  }
  assert {
    condition     = google_cloud_run_v2_service_iam_member.public.member == "allUsers" && google_cloud_run_v2_service_iam_member.public.role == "roles/run.invoker"
    error_message = "Anyone may call the service; that's the only public grant."
  }
}

run "deployer_has_only_resource_scoped_roles" {
  command = apply

  assert {
    condition     = google_artifact_registry_repository_iam_member.deployer_push.role == "roles/artifactregistry.writer"
    error_message = "The deployer may push images to this one repository."
  }
  assert {
    condition     = google_cloud_run_v2_service_iam_member.deployer.role == "roles/run.developer"
    error_message = "The deployer may update this one service (new revisions), not manage IAM."
  }
  assert {
    condition     = google_service_account_iam_member.deployer_acts_as_runtime.role == "roles/iam.serviceAccountUser"
    error_message = "The deployer may run revisions as the runtime account, and only that account."
  }
}

run "artifact_registry_cleans_up_old_images" {
  command = apply

  assert {
    condition     = google_artifact_registry_repository.images.format == "DOCKER" && google_artifact_registry_repository.images.location == "europe-west1"
    error_message = "A Docker repository in the same region as Cloud Run (no cross-region transfer)."
  }
  assert {
    condition     = anytrue([for p in google_artifact_registry_repository.images.cleanup_policies : p.action == "KEEP" && p.most_recent_versions[0].keep_count == 5])
    error_message = "Keep the 5 newest images (rollback) and let the rest be deleted: stays inside the 0.5 GB free storage."
  }
  assert {
    condition     = google_artifact_registry_repository.images.cleanup_policy_dry_run == false
    error_message = "Cleanup must actually run."
  }
}

run "budget_alerts_early" {
  command = apply

  assert {
    condition     = google_billing_budget.monthly.amount[0].specified_amount[0].units == "1" && google_billing_budget.monthly.amount[0].specified_amount[0].currency_code == "EUR"
    error_message = "A €1 monthly budget: any real spend is noticed immediately."
  }
  assert {
    condition     = contains([for t in google_billing_budget.monthly.threshold_rules : t.threshold_percent], 0.5)
    error_message = "Alert at 50% of the budget."
  }
  assert {
    condition     = google_billing_budget.monthly.budget_filter[0].projects == toset(["projects/179143178348"])
    error_message = "The budget watches this project only."
  }
}

run "rejects_a_malformed_project_id" {
  command = plan
  variables {
    project_id = "Not A Project!"
  }
  expect_failures = [var.project_id]
}

run "rejects_a_malformed_billing_account" {
  command = plan
  variables {
    billing_account_id = "123"
  }
  expect_failures = [var.billing_account_id]
}

run "rejects_more_than_two_instances" {
  command = plan
  variables {
    max_instances = 10
  }
  expect_failures = [var.max_instances]
}
