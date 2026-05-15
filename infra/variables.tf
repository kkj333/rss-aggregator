variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run and Cloud Scheduler."
  type        = string
  default     = "asia-northeast1"
}

variable "firestore_location" {
  description = "Location ID for the Firestore database."
  type        = string
  default     = "asia-northeast1"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "rss-aggregator"
}

variable "container_image" {
  description = "Optional. Initial Cloud Run image; omit to use Google's cloudrun/container/hello until CI pushes your app. If set, the image must already exist (e.g. after a manual docker push)."
  type        = string
  default     = null
}

variable "collector_container_image" {
  description = "Optional. Initial Cloud Run Job (collector) image; omit to use Google's cloudrun/container/job until CI pushes services/collector."
  type        = string
  default     = null
}

variable "classifier_container_image" {
  description = "Optional. Initial Cloud Run Job (classifier) image; omit to use Google's cloudrun/container/job until CI pushes services/classifier."
  type        = string
  default     = null
}

variable "commentator_container_image" {
  description = "Optional. Initial Cloud Run Job (commentator) image; omit to use Google's cloudrun/container/job until CI pushes services/commentator."
  type        = string
  default     = null
}

variable "profiler_container_image" {
  description = "Optional. Initial Cloud Run Job (profiler) image; omit to use Google's cloudrun/container/job until CI pushes services/profiler."
  type        = string
  default     = null
}

variable "firestore_collection" {
  description = "Firestore collection used by the application."
  type        = string
  default     = "articles"
}

variable "public_base_url" {
  description = "Optional. Public site URL for SEO (https://example.com, no trailing slash). Sets Cloud Run env PUBLIC_BASE_URL; omit or empty to let the app use the request host."
  type        = string
  default     = ""
}

variable "ga_measurement_id" {
  description = "Optional. Google Analytics 4 measurement ID (e.g. G-XXXXXXXX). Sets Cloud Run env GA_MEASUREMENT_ID; omit or empty to omit gtag from HTML."
  type        = string
  default     = ""
}

variable "scheduler_cron" {
  description = "Cloud Scheduler cron for RSS collection. Default: 08:00, 12:00, and 20:00 in scheduler_time_zone (three times per day)."
  type        = string
  default     = "0 8,12,20 * * *"
}

variable "scheduler_time_zone" {
  description = "Time zone used by Cloud Scheduler."
  type        = string
  default     = "Asia/Tokyo"
}

variable "cloud_run_deletion_protection" {
  description = "Whether Cloud Run deletion protection is enabled."
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "GitHub repository allowed for Workload Identity (owner/name)."
  type        = string
  default     = "kkj333/rss-aggregator"
}

variable "artifact_registry_repository_id" {
  description = "Artifact Registry Docker repository id (image path segment)."
  type        = string
  default     = "rss-aggregator"
}

variable "terraform_state_bucket" {
  description = "GCS bucket name for Terraform state (same as TF_STATE_BUCKET in GitHub Actions). Grants github_actions SA roles/storage.objectAdmin on this bucket."
  type        = string
  default     = ""
}

variable "cloud_run_job_task_timeout" {
  description = <<-EOT
    Per-task timeout for each Cloud Run Job (collector, classifier, commentator).
    RFC3339 duration ending with s (e.g. 3600s). Cloud Run default is 600s (10 min),
    which is often too short for Gemini batch jobs.
  EOT
  type        = string
  default     = "3600s"
}
