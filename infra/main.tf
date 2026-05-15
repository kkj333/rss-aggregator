locals {
  required_services = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "serviceusage.googleapis.com",
    # Bucket IAM (terraform_state_bucket) uses Storage API
    "storage.googleapis.com",
    "sts.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "workflowexecutions.googleapis.com",
    "workflows.googleapis.com",
  ])

  # First apply must use an image that already exists. Use Google's sample in
  # us-docker.pkg.dev (same host as collector job); regional *.docker.pkg.dev/cloudrun/...
  # often fails with downloadArtifacts / missing repo. CD replaces via gcloud deploy.
  cloud_run_initial_image = coalesce(
    var.container_image,
    "us-docker.pkg.dev/cloudrun/container/hello",
  )

  # Collector Job: Google-provided sample until CI pushes services/collector image.
  collector_job_initial_image = coalesce(
    var.collector_container_image,
    "us-docker.pkg.dev/cloudrun/container/job",
  )

  # Classifier Job: Google-provided sample until CI pushes services/classifier image.
  classifier_job_initial_image = coalesce(
    var.classifier_container_image,
    "us-docker.pkg.dev/cloudrun/container/job",
  )

  # Commentator Job: Google-provided sample until CI pushes services/commentator image.
  commentator_job_initial_image = coalesce(
    var.commentator_container_image,
    "us-docker.pkg.dev/cloudrun/container/job",
  )

  # Profiler Job: Google-provided sample until CI pushes services/profiler image.
  profiler_job_initial_image = coalesce(
    var.profiler_container_image,
    "us-docker.pkg.dev/cloudrun/container/job",
  )
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "cloud_run" {
  project      = var.project_id
  account_id   = "${var.service_name}-run"
  display_name = "Cloud Run runtime for ${var.service_name}"

  depends_on = [
    google_project_service.required,
    google_project_iam_member.github_actions_iam_sa_admin,
  ]
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "${var.service_name}-scheduler"
  display_name = "Cloud Scheduler invoking Run Jobs for ${var.service_name}"

  depends_on = [
    google_project_service.required,
    google_project_iam_member.github_actions_iam_sa_admin,
  ]
}

resource "google_project_iam_member" "cloud_run_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Pull images from this project's Artifact Registry (CD-deployed app/collector/classifier).
resource "google_project_iam_member" "cloud_run_artifact_registry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Classifier Job calls Gemini via Vertex AI.
resource "google_project_iam_member" "cloud_run_vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  depends_on = [
    google_project_service.required,
    google_project_iam_member.github_actions_datastore_owner,
  ]
}

resource "google_cloud_run_v2_service" "app" {
  project             = var.project_id
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.cloud_run_deletion_protection

  template {
    service_account = google_service_account.cloud_run.email

    containers {
      image = local.cloud_run_initial_image

      ports {
        container_port = 8080
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      env {
        name  = "FIRESTORE_COLLECTION"
        value = var.firestore_collection
      }

      env {
        name  = "TZ"
        value = "Asia/Tokyo"
      }

      dynamic "env" {
        for_each = length(trimspace(var.public_base_url)) > 0 ? [trimspace(var.public_base_url)] : []
        content {
          name  = "PUBLIC_BASE_URL"
          value = env.value
        }
      }

      dynamic "env" {
        for_each = length(trimspace(var.ga_measurement_id)) > 0 ? [trimspace(var.ga_measurement_id)] : []
        content {
          name  = "GA_MEASUREMENT_ID"
          value = env.value
        }
      }
    }
  }

  depends_on = [
    google_firestore_database.default,
    google_project_iam_member.cloud_run_firestore_user,
    google_project_iam_member.cloud_run_artifact_registry_reader,
  ]

  # 本番イメージは GitHub Actions（cd.yml）が gcloud で更新する。再 apply で
  # var.container_image（例: :latest）へ巻き戻さないよう、イメージだけ Terraform 管理外にする。
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# If apply returns 409 "already exists" (job created outside state), import once:
# terraform import 'google_cloud_run_v2_job.collect' 'projects/PROJECT_ID/locations/REGION/jobs/SERVICE_NAME-collector'
resource "google_cloud_run_v2_job" "collect" {
  project             = var.project_id
  name                = "${var.service_name}-collector"
  location            = var.region
  deletion_protection = var.cloud_run_deletion_protection

  template {
    template {
      timeout         = var.cloud_run_job_task_timeout
      service_account = google_service_account.cloud_run.email

      containers {
        image = local.collector_job_initial_image

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }

        env {
          name  = "FIRESTORE_COLLECTION"
          value = var.firestore_collection
        }

        env {
          name  = "TZ"
          value = "Asia/Tokyo"
        }
      }
    }
  }

  depends_on = [
    google_firestore_database.default,
    google_project_iam_member.cloud_run_firestore_user,
    google_project_iam_member.cloud_run_artifact_registry_reader,
  ]

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# If apply returns 409 "already exists" (job created outside state), import once:
# terraform import 'google_cloud_run_v2_job.classify' 'projects/PROJECT_ID/locations/REGION/jobs/SERVICE_NAME-classifier'
resource "google_cloud_run_v2_job" "classify" {
  project             = var.project_id
  name                = "${var.service_name}-classifier"
  location            = var.region
  deletion_protection = var.cloud_run_deletion_protection

  template {
    template {
      timeout         = var.cloud_run_job_task_timeout
      service_account = google_service_account.cloud_run.email

      containers {
        image = local.classifier_job_initial_image

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }

        env {
          name  = "FIRESTORE_COLLECTION"
          value = var.firestore_collection
        }

        env {
          name  = "GEMINI_LOCATION"
          value = "global"
        }

        env {
          name  = "GEMINI_MODEL"
          value = "gemini-3-flash-preview"
        }

        env {
          name  = "TZ"
          value = "Asia/Tokyo"
        }
      }
    }
  }

  depends_on = [
    google_firestore_database.default,
    google_project_iam_member.cloud_run_firestore_user,
    google_project_iam_member.cloud_run_artifact_registry_reader,
    google_project_iam_member.cloud_run_vertex_ai_user,
  ]

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# If apply returns 409 "already exists" (job created outside state), import once:
# terraform import 'google_cloud_run_v2_job.comment' 'projects/PROJECT_ID/locations/REGION/jobs/SERVICE_NAME-commentator'
resource "google_cloud_run_v2_job" "comment" {
  project             = var.project_id
  name                = "${var.service_name}-commentator"
  location            = var.region
  deletion_protection = var.cloud_run_deletion_protection

  template {
    template {
      timeout         = var.cloud_run_job_task_timeout
      service_account = google_service_account.cloud_run.email

      containers {
        image = local.commentator_job_initial_image

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }

        env {
          name  = "FIRESTORE_COLLECTION"
          value = var.firestore_collection
        }

        env {
          name  = "GEMINI_LOCATION"
          value = "global"
        }

        env {
          name  = "COMMENTATOR_MODEL"
          value = "gemini-3-flash-preview"
        }

        env {
          name  = "TZ"
          value = "Asia/Tokyo"
        }
      }
    }
  }

  depends_on = [
    google_firestore_database.default,
    google_project_iam_member.cloud_run_firestore_user,
    google_project_iam_member.cloud_run_artifact_registry_reader,
    google_project_iam_member.cloud_run_vertex_ai_user,
  ]

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# If apply returns 409 "already exists" (job created outside state), import once:
# terraform import 'google_cloud_run_v2_job.profile' 'projects/PROJECT_ID/locations/REGION/jobs/SERVICE_NAME-profiler'
resource "google_cloud_run_v2_job" "profile" {
  project             = var.project_id
  name                = "${var.service_name}-profiler"
  location            = var.region
  deletion_protection = var.cloud_run_deletion_protection

  template {
    template {
      timeout         = var.cloud_run_job_task_timeout
      service_account = google_service_account.cloud_run.email

      containers {
        image = local.profiler_job_initial_image

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }

        env {
          name  = "FIRESTORE_FEEDS_COLLECTION"
          value = "feeds"
        }

        env {
          name  = "GEMINI_LOCATION"
          value = "global"
        }

        env {
          name  = "PROFILER_MODEL"
          value = "gemini-3-flash-preview"
        }

        env {
          name  = "PROFILER_SKIP_EXISTING"
          value = "true"
        }

        env {
          name  = "TZ"
          value = "Asia/Tokyo"
        }
      }
    }
  }

  depends_on = [
    google_firestore_database.default,
    google_project_iam_member.cloud_run_firestore_user,
    google_project_iam_member.cloud_run_artifact_registry_reader,
    google_project_iam_member.cloud_run_vertex_ai_user,
  ]

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# ---- Workflows SA and Workflow ----

resource "google_service_account" "workflows" {
  project      = var.project_id
  account_id   = "${var.service_name}-workflows"
  display_name = "Cloud Workflows executor for ${var.service_name}"

  depends_on = [
    google_project_service.required,
    google_project_iam_member.github_actions_iam_sa_admin,
  ]
}

# Workflows SA invokes both Cloud Run Jobs.
resource "google_cloud_run_v2_job_iam_member" "workflows_invoker_collect" {
  project  = var.project_id
  location = google_cloud_run_v2_job.collect.location
  name     = google_cloud_run_v2_job.collect.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.workflows.email}"

  depends_on = [google_project_iam_member.github_actions_run_admin]
}

resource "google_cloud_run_v2_job_iam_member" "workflows_invoker_classify" {
  project  = var.project_id
  location = google_cloud_run_v2_job.classify.location
  name     = google_cloud_run_v2_job.classify.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.workflows.email}"

  depends_on = [google_project_iam_member.github_actions_run_admin]
}

resource "google_cloud_run_v2_job_iam_member" "workflows_invoker_comment" {
  project  = var.project_id
  location = google_cloud_run_v2_job.comment.location
  name     = google_cloud_run_v2_job.comment.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.workflows.email}"

  depends_on = [google_project_iam_member.github_actions_run_admin]
}

resource "google_project_iam_member" "workflows_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.workflows.email}"
}

# Job への roles/run.invoker は :run のみ。Workflow の poll_execution（GET .../executions/...）には
# run.executions.get が必要なため、プロジェクトで閲覧ロールを付与する。
resource "google_project_iam_member" "workflows_run_viewer" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = "serviceAccount:${google_service_account.workflows.email}"

  depends_on = [
    google_project_service.required,
    google_service_account.workflows,
  ]
}

# Scheduler SA invokes the Workflow (not the jobs directly).
resource "google_project_iam_member" "scheduler_workflows_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_workflows_workflow" "collect_then_classify" {
  project         = var.project_id
  name            = "${var.service_name}-collect-then-classify"
  region          = var.region
  description     = "Run collector job, wait for completion, then run classifier job."
  service_account = google_service_account.workflows.email

  source_contents = templatefile("${path.module}/workflows/collect_then_classify.yaml.tmpl", {
    region       = var.region
    service_name = var.service_name
  })

  depends_on = [
    google_service_account.workflows,
    google_cloud_run_v2_job_iam_member.workflows_invoker_collect,
    google_cloud_run_v2_job_iam_member.workflows_invoker_classify,
    google_project_iam_member.workflows_run_viewer,
    # GHA SA に actAs が付く前に Workflow を作ろうとすると 403 になるため、
    # IAM binding が完了してから Workflow を作成する。
    google_service_account_iam_member.github_actions_act_as_workflows,
  ]
}

# Web GET /blogs/{feed_id}: WHERE feed_url == ? ORDER BY published_at DESC（ArticleStore.list_by_feed）
resource "google_firestore_index" "articles_by_feed_url" {
  project    = var.project_id
  database   = google_firestore_database.default.name
  collection = var.firestore_collection

  fields {
    field_path = "feed_url"
    order      = "ASCENDING"
  }
  fields {
    field_path = "published_at"
    order      = "DESCENDING"
  }
  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.default]
}

# commentator list_uncommented: ai_comment == null AND relevance_score >= threshold
resource "google_firestore_index" "uncommented_by_score" {
  project    = var.project_id
  database   = google_firestore_database.default.name
  collection = var.firestore_collection

  fields {
    field_path = "ai_comment"
    order      = "ASCENDING"
  }
  fields {
    field_path = "relevance_score"
    order      = "ASCENDING"
  }
  fields {
    field_path = "__name__"
    order      = "ASCENDING"
  }

  depends_on = [google_firestore_database.default]
}

# Jobs: use roles/run.invoker (roles/run.jobsInvoker is not supported on Job IAM).
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_job.collect.location
  name     = google_cloud_run_v2_job.collect.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"

  depends_on = [google_project_iam_member.github_actions_run_admin]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"

  depends_on = [google_project_iam_member.github_actions_run_admin]
}

resource "google_cloud_scheduler_job" "collect" {
  project     = var.project_id
  region      = var.region
  name        = "${var.service_name}-collect-schedule"
  description = "Trigger Workflow: collect RSS then classify (${google_workflows_workflow.collect_then_classify.name})."
  schedule    = var.scheduler_cron
  time_zone   = var.scheduler_time_zone

  http_target {
    http_method = "POST"
    uri = format(
      "https://workflowexecutions.googleapis.com/v1/projects/%s/locations/%s/workflows/%s/executions",
      var.project_id,
      var.region,
      google_workflows_workflow.collect_then_classify.name,
    )

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_workflows_workflow.collect_then_classify,
    google_project_iam_member.scheduler_workflows_invoker,
    google_project_iam_member.github_actions_cloud_scheduler_admin,
    # GHA SA に scheduler SA への actAs が付く前に更新しようとすると 403 になる。
    google_service_account_iam_member.github_actions_act_as_scheduler,
  ]
}

# Log-based metric: commentator job が出力する JSON stats の tokens.total を分布メトリクスとして記録する。
# Cloud Logging の structuredPayload（jsonPayload）から抽出し、Cloud Monitoring でグラフ化・アラートに使える。
resource "google_logging_metric" "commentator_tokens_total" {
  project = var.project_id
  name    = "commentator/tokens_total"
  # Cloud Run Job のログのうち、commentator job が出力する JSON stats 行を対象にする。
  # run.py が print(json.dumps(stats)) で出力する1行: {"total":...,"tokens":{"total":N,...}}
  filter = <<-EOT
    resource.type="cloud_run_job"
    resource.labels.job_name="${var.service_name}-commentator"
    jsonPayload.tokens.total>=0
  EOT

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "DISTRIBUTION"
    unit         = "1"
    display_name = "Commentator tokens total (per job run)"
  }

  value_extractor = "EXTRACT(jsonPayload.tokens.total)"

  bucket_options {
    explicit_buckets {
      # 0, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000 tokens
      bounds = [0, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000]
    }
  }

  depends_on = [
    google_project_service.required,
    google_project_iam_member.github_actions_logging_config_writer,
  ]
}
