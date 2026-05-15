# State は GCS に置く（bucket / prefix は init 時に指定）。
# ローカル: terraform init -backend-config="bucket=YOUR_BUCKET" -backend-config="prefix=rss-aggregator/terraform"
# CI: TF_STATE_BUCKET を Repository variables に設定し TF_APPLY_IN_CD で有効化。
terraform {
  backend "gcs" {}
}
