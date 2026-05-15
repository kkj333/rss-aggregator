# トラブルシュート

**`/feeds` の掲載元が期待より少ない／記事が特定ソースだけ**

- ブラウザまたは `curl` で `GET http://127.0.0.1:8000/api/feeds` を確認する。ここに並ぶのが **実行時に `feeds.json` から実際に読めている**登録ソース一覧です。
- `docker compose` を **リポジトリ直下**で実行しているか（`./feeds.json` のマウント元がズレると中身が違います）。
- `docker run` だけの場合、**ビルド時にイメージへ焼き込んだ `feeds.json`** のままになることがあります。`docker compose` のように `feeds.json` をマウントするか、フィードを変えたら `docker compose build --no-cache` で取り直す。

**既存の記事が残る**

- 重複は URL 単位で弾きます。一度取り込んだ行は **意図的に DB に残ります**（他ソースに切り替えても、古い行は消えません）。

**トップに異常な未来日付の記事が張り付く（例: 2100/01/01）**

- 元サイトの RSS / Atom が誤った公開日時を返していることがあります（予約投稿の誤設定など）。
- アプリは「現在から約 2 週間より先」の `published_at` を収集日時相当に置き換え、一覧の並びもそれに合わせます（`services/shared/shared/published_at.py`）。

**Firestore を Docker で使う**

- `.env` に `GOOGLE_CLOUD_PROJECT` を設定し、ホストで `gcloud auth application-default login` 済みであること（`docker-compose.yml` が `~/.config/gcloud` をマウントします）。詳細は [ローカル開発](local.md)。

**Docker Compose の profiler がすぐ終わる／`exit code 132`（Apple Silicon）**

- **132** は多くの場合 **CPU アーキテクチャ不一致**（ARM Mac で amd64 バイナリが SIGILL）。`docker-compose.yml` の profiler は **`platform: linux/arm64`** を指定しているため、イメージを作り直す: `docker compose build --no-cache profiler`（古いキャッシュ層のままだと直らないことがある）。
- 実行ログが出ないうちに終了する場合は、同じリポジトリ直下で `docker compose --profile profiler run --rm profiler` になっているか、`.env` の `GOOGLE_CLOUD_PROJECT` を確認する。

**commentator Job が「成功」なのに 0 件のまま**

- Cloud Run Job 実行ログに `Articles to comment:` が出ているか確認する。`Starting Task ... Completed Task ...` しか出ない場合、プレースホルダ image で起動している可能性があります。
- commentator Job のコンテナ image が `services/commentator` 由来の最新 Artifact Registry タグか確認する。
- commentator Job の環境変数に `GOOGLE_CLOUD_PROJECT`、`FIRESTORE_COLLECTION`、`RELEVANCE_THRESHOLD` が正しく設定されているか確認する。

**Cloud Workflows が FAILED（`run.executions.get` で 403）**

- Workflows 実行 SA が Job の **Execution を GET** できない。Terraform で Workflows 用 SA に **`roles/run.viewer`**（または同等で `run.executions.get` が付くロール）がプロジェクトに付いているか確認する（Job にだけ `roles/run.invoker` では不足することがある）。

**Classifier job polling timed out（約 10 / 30 分）**

- Workflow の classifier 完了待ちが上限に達した。記事数・Vertex の遅延で長引く場合がある。`infra/workflows/collect_then_classify.yaml.tmpl` の **`max_classifier_poll_attempts`** と sleep 間隔で調整するか、Job 側のバッチサイズを見直す。

**Cloud Run Job「Terminating task … maximum timeout of 600 seconds」**

- タスクの既定上限は **600 秒（10 分）**。classifier / commentator は Gemini の連続呼び出しで容易に超える。
- **コード側の対応**: `infra/main.tf` の各 `google_cloud_run_v2_job` に `timeout`（変数 `cloud_run_job_task_timeout`、既定 **3600s**）が入っている。`terraform apply` で反映する。
- **CD の対応**: `.github/workflows/cd.yml` の `gcloud run jobs deploy` に **`--task-timeout`** を付けている（`CLOUD_RUN_JOB_TASK_TIMEOUT`、既定 **3600s**）。ジョブのみイメージ更新する場合も、この値で再デプロイされる。
- さらに長くしたい場合は `infra/terraform.tfvars` で `cloud_run_job_task_timeout = "7200s"` のように変更し、`.github/workflows/cd.yml` の **`CLOUD_RUN_JOB_TASK_TIMEOUT`** を同じ値に合わせる。

**classifier Job が「成功」なのに 0 件のまま**

- 実行ログの `Unclassified articles to score:` を確認する。`0` の場合、未分類抽出条件で対象が取れていない。
- 既存記事に `relevance_score` フィールドが無い時期のデータがある場合、`relevance_score == null` クエリにヒットしない。`scripts/backfill_null_fields.py` を実行して欠落フィールドを補完してください（[マイグレーション手順](deploy.md#監視メトリクス)は deploy.md を参照）。
- Workflows を使う場合、collector のあと classifier 完了を待ってから commentator が起動する構成になっているか確認する（順序のみで完了待ちがない構成だと commentator が先行して 0 件になりうる）。
