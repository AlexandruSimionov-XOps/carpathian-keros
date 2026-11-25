# Monthly budget alert. Email goes to the billing account's admins (Google's default recipients).
# A budget only alerts: it never stops services. The real cost guards are scale-to-zero and max_instances.

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account_id
  display_name    = "${var.service_name} monthly"

  budget_filter {
    projects        = ["projects/${local.project_number}"]
    calendar_period = "MONTH"
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.budget_amount)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND" # warn before the month ends if the trend would cross the budget
  }

  depends_on = [google_project_service.apis]
}
