# The public website. Sized for the free tier: scale to zero, CPU only while a request is being handled,
# at most var.max_instances instances. The image uses PORT=8080 (Cloud Run sets it) and GET /healthz.

resource "google_cloud_run_v2_service" "app" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = true # `tofu destroy` must first set this to false on purpose

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "60s" # matches gunicorn's timeout (gunicorn.conf.py)
    max_instance_request_concurrency = 40    # 2 gunicorn workers × 4 threads, with headroom while waiting on Open-Meteo

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      image = var.initial_image # CD deploys the real image; see lifecycle below

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true # CPU is allocated only while handling requests (request-based billing)
        startup_cpu_boost = true # faster cold starts at no extra cost
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds    = 2
        timeout_seconds   = 2
        failure_threshold = 15 # up to 30 s to start
      }

      liveness_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds    = 30
        timeout_seconds   = 3
        failure_threshold = 3
      }
    }
  }

  lifecycle {
    # OpenTofu owns the service's configuration; the deploy workflow owns which image version runs.
    # Without this, the next `tofu apply` would roll production back to var.initial_image.
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.apis]
}

# It's a public website: anyone may call it. This is the only allUsers grant in the project (policy-tested).
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
