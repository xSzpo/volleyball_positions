terraform {
  required_version = ">= 1.5"
  required_providers {
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }
}

# Used to create the project and enable APIs (no quota project yet).
provider "google-beta" {
  alias                 = "no_user_project_override"
  user_project_override = false
}

# Used for all Firebase resources; bills API calls to the project itself.
provider "google-beta" {
  user_project_override = true
  billing_project       = var.project_id
}
