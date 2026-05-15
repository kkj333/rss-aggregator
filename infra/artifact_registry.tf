resource "google_artifact_registry_repository" "app" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repository_id
  format        = "DOCKER"
  description   = "Container images for ${var.service_name}"

  depends_on = [
    google_project_service.required,
    google_project_iam_member.github_actions_artifact_registry_admin,
  ]
}
