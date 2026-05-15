#!/usr/bin/env bash
# プロジェクト *Owner*（または同等）が、GitHub Actions 用の Terraform apply に入る *前に 1 回* 実行する。
# - main.tf locals.required_services と同じ API を有効化する（この一覧は main を変えたら追従すること）
# - github_actions_wif.tf の GitHub Actions 用 SA ロールと同じ一覧を、手元で先に付ける（鶏卵の解消）
#
# 使い方:
#   chmod +x infra/scripts/bootstrap_gcp_for_ci.sh
#   GCP_PROJECT_ID=your-project ./infra/scripts/bootstrap_gcp_for_ci.sh
#
# 先に `rss-aggregator-gha@...` 用のサービスアカウントが必要。無い場合は、一度だけ
# オーナーアカウントで `cd infra && terraform apply` するか、手動で SA を作成してから再実行。

set -euo pipefail

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud が必要です。" >&2
  exit 1
fi

PROJECT="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT}" || "${PROJECT}" == "(unset)" ]]; then
  echo "GCP_PROJECT_ID を渡すか、gcloud config set project してください。" >&2
  exit 1
fi

SERVICE_NAME="${SERVICE_NAME:-rss-aggregator}"
SA_EMAIL="${SERVICE_NAME}-gha@${PROJECT}.iam.gserviceaccount.com"
MEMBER="serviceAccount:${SA_EMAIL}"

# Keep in sync with: infra/main.tf → locals.required_services
REQUIRED_APIS=(
  aiplatform.googleapis.com
  artifactregistry.googleapis.com
  cloudresourcemanager.googleapis.com
  cloudscheduler.googleapis.com
  firestore.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  run.googleapis.com
  serviceusage.googleapis.com
  logging.googleapis.com
  monitoring.googleapis.com
  storage.googleapis.com
  sts.googleapis.com
  workflowexecutions.googleapis.com
  workflows.googleapis.com
)

# Keep in sync with: infra/github_actions_wif.tf (google_project_iam_member for github_actions)
ROLES=(
  roles/serviceusage.serviceUsageAdmin
  roles/iam.serviceAccountAdmin
  roles/artifactregistry.admin
  roles/datastore.owner
  roles/cloudscheduler.admin
  roles/storage.admin
  roles/resourcemanager.projectIamAdmin
  roles/run.admin
  roles/iam.workloadIdentityPoolAdmin
  roles/logging.configWriter
  roles/workflows.admin
)

echo "project=$PROJECT"
echo "member=$MEMBER"
echo ""

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT" >/dev/null 2>&1; then
  echo "エラー: サービスアカウント $SA_EMAIL がまだありません。" >&2
  echo "  例: オーナーで cd infra && terraform apply（一部成功で SA 作成まで）" >&2
  echo "  例: gcloud iam service-accounts create ${SERVICE_NAME}-gha --project=$PROJECT --display-name='GitHub Actions deploy'" >&2
  exit 1
fi

echo "==> Enabling APIs"
for api in "${REQUIRED_APIS[@]}"; do
  echo "    $api"
  gcloud services enable "$api" --project="$PROJECT"
done

echo ""
echo "==> IAM role bindings (idempotent)"
for role in "${ROLES[@]}"; do
  echo "    $role"
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="$MEMBER" \
    --role="$role" \
    --quiet
done

echo ""
echo "完了。次: GCS state 用バケットと backend.hcl → terraform init/apply、または CD。"
