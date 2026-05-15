# CI 初回: 期待どおり apply する前に、オーナーが infra/scripts/bootstrap_gcp_for_ci.sh を一度実行する（権限の鶏卵回避）。
data "google_project" "current" {
  project_id = var.project_id
}

locals {
  github_wif_pool_id       = "github-actions"
  github_wif_provider_id   = "github-oidc"
  github_wif_provider_name = "projects/${data.google_project.current.number}/locations/global/workloadIdentityPools/${local.github_wif_pool_id}/providers/${local.github_wif_provider_id}"
  github_actions_member    = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_service_account" "github_actions" {
  project      = var.project_id
  account_id   = "${var.service_name}-gha"
  display_name = "GitHub Actions deploy for ${var.service_name}"

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = local.github_wif_pool_id
  display_name              = "GitHub Actions"
  description               = "OIDC federation for GitHub Actions"

  depends_on = [
    google_project_service.required,
    google_project_iam_member.github_actions_workload_identity_pool_admin,
  ]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = local.github_wif_provider_id
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
    allowed_audiences = [
      "//iam.googleapis.com/${local.github_wif_provider_name}",
      "https://iam.googleapis.com/${local.github_wif_provider_name}",
      local.github_wif_provider_name,
      "https://github.com/${var.github_repository}",
    ]
  }

  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  depends_on = [google_iam_workload_identity_pool.github]
}

resource "google_service_account_iam_member" "github_wif_user" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# Replaces roles/editor: one role per area this stack touches (still powerful — see comments).
resource "google_project_iam_member" "github_actions_service_usage_admin" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = local.github_actions_member
}

resource "google_project_iam_member" "github_actions_iam_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = local.github_actions_member
}

resource "google_project_iam_member" "github_actions_artifact_registry_admin" {
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  member  = local.github_actions_member
}

# google_firestore_database + runtime needs DB admin; includes full Firestore data access (predefined limitation).
resource "google_project_iam_member" "github_actions_datastore_owner" {
  project = var.project_id
  role    = "roles/datastore.owner"
  member  = local.github_actions_member
}

resource "google_project_iam_member" "github_actions_cloud_scheduler_admin" {
  project = var.project_id
  role    = "roles/cloudscheduler.admin"
  member  = local.github_actions_member
}

# google_storage_bucket_iam_member (tf state): needs buckets.setIamPolicy; scopes all buckets in project.
resource "google_project_iam_member" "github_actions_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = local.github_actions_member
}

resource "google_project_iam_member" "github_actions_project_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = local.github_actions_member
}

# run.services / run.jobs setIamPolicy (e.g. allUsers on service, scheduler on job).
resource "google_project_iam_member" "github_actions_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = local.github_actions_member
}

resource "google_project_iam_member" "github_actions_workload_identity_pool_admin" {
  project = var.project_id
  role    = "roles/iam.workloadIdentityPoolAdmin"
  member  = local.github_actions_member
}

resource "google_service_account_iam_member" "github_actions_act_as_cloud_run" {
  service_account_id = google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.github_actions_member
}

# google_logging_metric (log-based metrics) を作成・管理するために必要。
resource "google_project_iam_member" "github_actions_logging_config_writer" {
  project = var.project_id
  role    = "roles/logging.configWriter"
  member  = local.github_actions_member
}

# Manage Cloud Workflows resources (workflow + IAM on workflow).
resource "google_project_iam_member" "github_actions_workflows_admin" {
  project = var.project_id
  role    = "roles/workflows.admin"
  member  = local.github_actions_member
}

resource "google_service_account_iam_member" "github_actions_act_as_workflows" {
  service_account_id = google_service_account.workflows.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.github_actions_member
}

resource "google_service_account_iam_member" "github_actions_act_as_scheduler" {
  service_account_id = google_service_account.scheduler.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.github_actions_member
}
