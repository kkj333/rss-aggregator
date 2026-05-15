#!/usr/bin/env bash
# Terraform state 用 GCS バケットを作成する（手元で gcloud が使えること）。
# 使い方:
#   chmod +x infra/scripts/create_tf_state_bucket.sh
#   ./infra/scripts/create_tf_state_bucket.sh
# または:
#   GCP_PROJECT_ID=your-project-id TF_STATE_BUCKET_NAME=my-unique-bucket ./infra/scripts/create_tf_state_bucket.sh
#
# バケット名は全世界で一意である必要があります。デフォルトは ${PROJECT}-rss-aggregator-tfstate

set -euo pipefail

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud が見つかりません。Google Cloud SDK をインストールしてください。" >&2
  exit 1
fi

PROJECT="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT}" || "${PROJECT}" == "(unset)" ]]; then
  echo "GCP プロジェクトが未設定です。次のいずれかを実行してください:" >&2
  echo "  gcloud config set project YOUR_PROJECT_ID" >&2
  echo "  GCP_PROJECT_ID=YOUR_PROJECT_ID $0" >&2
  exit 1
fi

REGION="${GCP_REGION:-asia-northeast1}"
BUCKET="${TF_STATE_BUCKET_NAME:-${PROJECT}-rss-aggregator-tfstate}"
PREFIX="${TF_STATE_PREFIX:-rss-aggregator/terraform}"

echo "project=$PROJECT"
echo "bucket=$BUCKET"
echo "region=$REGION"

if gcloud storage buckets describe "gs://${BUCKET}" --project="${PROJECT}" >/dev/null 2>&1; then
  echo "バケット gs://${BUCKET} は既に存在します。作成はスキップします。"
else
  gcloud storage buckets create "gs://${BUCKET}" \
    --project="${PROJECT}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
  echo "作成しました: gs://${BUCKET}"
fi

# Terraform state の復旧用にオブジェクトバージョニングを有効化（新規・既存どちらでも実行）
gcloud storage buckets update "gs://${BUCKET}" \
  --project="${PROJECT}" \
  --versioning
echo "オブジェクトバージョニングを有効にしました。"

BACKEND_SNIPPET=$(cat <<EOF
bucket = "${BUCKET}"
prefix = "${PREFIX}"
EOF
)

if [[ "${WRITE_BACKEND_HCL:-}" == "1" ]]; then
  ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
  BC="${ROOT}/infra/backend.hcl"
  printf '%s\n' "$BACKEND_SNIPPET" >"$BC"
  echo "Wrote $BC"
else
  echo ""
  echo "infra/backend.hcl に次を書いてください:"
  echo "---"
  printf '%s\n' "$BACKEND_SNIPPET"
  echo "---"
  echo ""
  echo "自動生成: WRITE_BACKEND_HCL=1 $0"
fi

echo "次: cd infra && terraform init -backend-config=backend.hcl && terraform plan"
