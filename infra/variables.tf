variable "project_id" {
  description = "Globally unique Google Cloud project ID, e.g. ksv-volleyball-7421 (6-30 chars, lowercase, digits, hyphens)."
  type        = string
}

variable "project_name" {
  description = "Display name of the project."
  type        = string
  default     = "KSV volleyball trainer"
}

variable "create_project" {
  description = "true = Terraform creates the project. false = use an existing project (see README for import commands)."
  type        = bool
  default     = true
}

variable "billing_account" {
  description = "Cloud Billing account ID (XXXXXX-XXXXXX-XXXXXX). Leave null to stay on the free Spark plan. Required only if manage_auth = true."
  type        = string
  default     = null
}

variable "manage_auth" {
  description = "Let Terraform enable anonymous sign-in and authorized domains. Needs billing_account (Blaze) and upgrades the project to Identity Platform. If false, enable Anonymous sign-in once in the Firebase console."
  type        = bool
  default     = false

  validation {
    condition     = !var.manage_auth || var.billing_account != null
    error_message = "manage_auth = true requires billing_account (the Blaze plan)."
  }
}

variable "database_region" {
  description = "Realtime Database location. europe-west1 (Belgium) is closest to Denmark."
  type        = string
  default     = "europe-west1"
}

variable "site_domain" {
  description = "Domain that hosts the app (added to authorized domains when manage_auth = true)."
  type        = string
  default     = "xszpo.github.io"
}

variable "deploy_rules" {
  description = "Upload database.rules.json with the Firebase CLI after apply (needs `firebase` installed and `firebase login`)."
  type        = bool
  default     = true
}

variable "budget_amount" {
  description = "Monthly budget alert amount (only when billing_account is set). Alerts only; it does not stop spending."
  type        = number
  default     = 5
}

variable "budget_currency" {
  description = "Currency of your billing account, e.g. EUR or DKK. Must match the billing account."
  type        = string
  default     = "EUR"
}
