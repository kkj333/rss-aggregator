# GitHub Actions が GCS backend で terraform init / apply するために必要。
# 初回のみ init が 403 になりうる（権限が state 内にまだ無い）。README のワンショットを参照。
resource "google_storage_bucket_iam_member" "github_actions_tf_state" {
  count  = var.terraform_state_bucket != "" ? 1 : 0
  bucket = var.terraform_state_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.github_actions.email}"

  depends_on = [google_project_iam_member.github_actions_storage_admin]
}
