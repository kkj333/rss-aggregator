output "cloud_run_url" {
  description = "Cloud Run service URL."
  value       = google_cloud_run_v2_service.app.uri
}

output "scheduler_job_name" {
  description = "Cloud Scheduler job name (triggers the collect-then-classify Workflow)."
  value       = google_cloud_scheduler_job.collect.name
}

output "collector_job_name" {
  description = "Cloud Run Job name for RSS collection."
  value       = google_cloud_run_v2_job.collect.name
}

output "classifier_job_name" {
  description = "Cloud Run Job name for article relevance scoring."
  value       = google_cloud_run_v2_job.classify.name
}

output "workflow_name" {
  description = "Cloud Workflows workflow that chains collector → classifier."
  value       = google_workflows_workflow.collect_then_classify.name
}

output "service_account_email" {
  description = "Cloud Run runtime service account."
  value       = google_service_account.cloud_run.email
}

output "github_actions_workload_identity_provider" {
  description = "GitHub Actions: set as secret WIF_PROVIDER (google-github-actions/auth)."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "github_actions_service_account_email" {
  description = "GitHub Actions: set as secret WIF_SERVICE_ACCOUNT."
  value       = google_service_account.github_actions.email
}

output "artifact_registry_docker_url" {
  description = "Docker registry host for gcloud auth configure-docker (region-docker.pkg.dev/PROJECT/REPO)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository_id}"
}
