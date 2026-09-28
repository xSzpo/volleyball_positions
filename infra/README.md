# Firebase infrastructure (Terraform)

Creates the Firebase backend for online multiplayer: a Google Cloud project with Firebase, a web app registration, the default Realtime Database in `europe-west1`, the database security rules (uploaded with the Firebase CLI), and optionally anonymous sign-in and a budget alert.

## Two ways to run it

| | Free (default) | Fully automated |
|---|---|---|
| Plan | Spark, no billing account | Blaze, billing account linked |
| Anonymous sign-in | **one manual click** in the Firebase console | Terraform (`manage_auth = true`) |
| Cost | 0 | 0 at team-sized usage, but a card is linked; a budget alert is created |
| Why | Terraform can only configure sign-in through Identity Platform, which requires Blaze | |

Terraform cannot manage Realtime Database security rules, so `database.rules.json` is uploaded with the Firebase CLI (Terraform runs it for you when `deploy_rules = true`).

## Prerequisites

```bash
# Google Cloud SDK (gcloud), Terraform >= 1.5, Node.js
npm install -g firebase-tools
gcloud auth login
gcloud auth application-default login   # credentials Terraform uses
firebase login                          # credentials the rules upload uses
```

## Run

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # set a globally unique project_id
terraform init
terraform validate
terraform plan
terraform apply
terraform output firebase_config_js           # paste this into the app / give it to Claude Code
```

Free setup only, after `apply`: Firebase console → **Authentication → Get started → Sign-in method → Anonymous → Enable**, then **Settings → Authorized domains → Add domain → `xszpo.github.io`**. `terraform output next_steps` shows this too.

## Already created the project in the console?

Set `create_project = false` in `terraform.tfvars` and use the existing `project_id`, then import what already exists before `apply`:

```bash
terraform import google_firebase_project.default projects/PROJECT_ID
terraform import google_firebase_database_instance.default projects/PROJECT_ID/locations/europe-west1/instances/PROJECT_ID-default-rtdb
# If you already registered a web app, either import it (ID from Project settings):
#   terraform import google_firebase_web_app.trainer projects/PROJECT_ID/webApps/APP_ID
# or let Terraform register a new one named "trainer" and use its config.
```

## Notes

- `terraform.tfvars` and `*.tfstate` are git-ignored. The state contains the web API key (not a secret, but keep state out of the public repo anyway).
- The project has `deletion_policy = "PREVENT"`, and the default Realtime Database can never be deleted once created, so `terraform destroy` won't remove them. Delete the project in the Cloud console if you really want it gone.
- Changing `database.rules.json` and running `terraform apply` re-uploads the rules. You can also run `firebase deploy --only database --project PROJECT_ID` from this folder.
