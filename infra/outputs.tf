locals {
  firebase_config = {
    apiKey            = data.google_firebase_web_app_config.trainer.api_key
    authDomain        = data.google_firebase_web_app_config.trainer.auth_domain
    databaseURL       = google_firebase_database_instance.default.database_url
    projectId         = local.project_id
    storageBucket     = data.google_firebase_web_app_config.trainer.storage_bucket
    messagingSenderId = data.google_firebase_web_app_config.trainer.messaging_sender_id
    appId             = google_firebase_web_app.trainer.app_id
  }
}

output "firebase_config" {
  description = "Paste into the app (not secret; security comes from the rules and sign-in)."
  value       = local.firebase_config
}

output "firebase_config_js" {
  description = "Same config as a JavaScript snippet."
  value       = "const firebaseConfig = ${jsonencode(local.firebase_config)};"
}

output "database_url" {
  value = google_firebase_database_instance.default.database_url
}

output "next_steps" {
  value = var.manage_auth ? "Done. Auth, database and rules are configured." : "One manual step: Firebase console -> Authentication -> Get started -> Sign-in method -> Anonymous -> Enable. Then Settings -> Authorized domains -> add ${var.site_domain}."
}
