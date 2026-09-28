locals {
  project_id = var.project_id
  services = [
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "firebase.googleapis.com",
    "firebasedatabase.googleapis.com",
    "identitytoolkit.googleapis.com",
  ]
}

# ---------- Project ----------
resource "google_project" "this" {
  count    = var.create_project ? 1 : 0
  provider = google-beta.no_user_project_override

  project_id      = var.project_id
  name            = var.project_name
  billing_account = var.billing_account
  deletion_policy = "PREVENT"

  labels = {
    firebase = "enabled"
  }
}

data "google_project" "this" {
  provider   = google-beta.no_user_project_override
  project_id = local.project_id
  depends_on = [google_project.this]
}

resource "google_project_service" "services" {
  for_each = toset(local.services)
  provider = google-beta.no_user_project_override

  project            = local.project_id
  service            = each.value
  disable_on_destroy = false
  depends_on         = [google_project.this]
}

# ---------- Firebase ----------
resource "google_firebase_project" "default" {
  provider   = google-beta
  project    = local.project_id
  depends_on = [google_project_service.services]
}

resource "google_firebase_web_app" "trainer" {
  provider        = google-beta
  project         = local.project_id
  display_name    = "trainer"
  deletion_policy = "DELETE"
  depends_on      = [google_firebase_project.default]
}

data "google_firebase_web_app_config" "trainer" {
  provider   = google-beta
  project    = local.project_id
  web_app_id = google_firebase_web_app.trainer.app_id
}

# ---------- Realtime Database (default instance, free on Spark) ----------
resource "google_firebase_database_instance" "default" {
  provider    = google-beta
  project     = local.project_id
  region      = var.database_region
  instance_id = "${local.project_id}-default-rtdb"
  type        = "DEFAULT_DATABASE"
  depends_on  = [google_firebase_project.default]
}

# ---------- Authentication (optional, needs Blaze) ----------
resource "google_identity_platform_config" "auth" {
  count    = var.manage_auth ? 1 : 0
  provider = google-beta
  project  = local.project_id

  autodelete_anonymous_users = true

  sign_in {
    anonymous {
      enabled = true
    }
  }

  authorized_domains = [
    "localhost",
    "${local.project_id}.firebaseapp.com",
    "${local.project_id}.web.app",
    var.site_domain,
  ]

  depends_on = [google_firebase_project.default]
}

# ---------- Security rules (Terraform can't manage RTDB rules; use the Firebase CLI) ----------
resource "terraform_data" "rtdb_rules" {
  count            = var.deploy_rules ? 1 : 0
  triggers_replace = [filesha256("${path.module}/database.rules.json"), google_firebase_database_instance.default.id]

  provisioner "local-exec" {
    working_dir = path.module
    command     = "firebase deploy --only database --project ${local.project_id} --non-interactive"
  }
}

# ---------- Budget alert (only when billing is linked) ----------
resource "google_project_service" "billingbudgets" {
  count              = var.billing_account != null ? 1 : 0
  provider           = google-beta.no_user_project_override
  project            = local.project_id
  service            = "billingbudgets.googleapis.com"
  disable_on_destroy = false
  depends_on         = [google_project.this]
}

resource "google_billing_budget" "alert" {
  count           = var.billing_account != null ? 1 : 0
  provider        = google-beta
  billing_account = var.billing_account
  display_name    = "${local.project_id} monthly alert"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.budget_amount)
    }
  }

  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 1.0 }

  depends_on = [google_project_service.billingbudgets]
}
