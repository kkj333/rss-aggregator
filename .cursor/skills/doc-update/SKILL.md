---
name: doc-update
description: >-
  Updates the right markdown under docs/ and the root README when code or ops
  change. Includes Mermaid architecture diagrams in README and docs/deploy.md
  when pipelines change. Canonical pages: docs/api.md, docs/env-feeds.md,
  docs/local.md, docs/deploy.md, docs/troubleshooting.md (see docs/README.md
  index). Use after HTTP routes, env vars, feeds, Docker, Terraform, CI/CD, or
  when the user asks to sync documentation with the implementation.
disable-model-invocation: true
---

# ドキュメントアップデート

実装・設定を変えたら、**対応する `docs/` と、必要ならルートの `README.md` を同じ PR で更新する**。本文の長い複製はせず、**既存ページの表・1段落**を直す。

一覧は **`docs/README.md`** の表が正（リンクテキストは日本語でも、ファイル名は短い英語）。

## ルートの Markdown（現状 `README.md` のみ）

GitHub の入口なので、次が変わったら **`README.md` も更新対象**に含める（詳細は `docs/` に寄せ、README は短く保つ）。

- `docs/` へのリンクやファイル名（リネーム・新規ページ）
- **概要のアーキテクチャ**（ルート `README.md` の「アーキテクチャ（概要）」セクション内の **Mermaid**。パイプラインや GCP コンポーネントを変えたら図も更新）
- クローン後の最短手順・代表コマンド・前提ツール
- プロジェクトの一言説明・リポジトリの役割

将来ルートに `CONTRIBUTING.md` などを増やしたら、同様に「そのファイルがカバーする範囲が変わったら更新」と読み替える。

## `docs/*.md` の対応（ファイル名）

| ファイル | 内容 |
| --- | --- |
| `docs/api.md` | HTTP（HTML / JSON）、`/rss`、`/healthz` |
| `docs/env-feeds.md` | `feeds.json`、環境変数、ストレージ関連 |
| `docs/local.md` | Docker / uv、ディレクトリ、ローカル初回手順 |
| `docs/deploy.md` | Terraform、Cloud Run、Scheduler、GitHub Actions CD、bootstrap、**バッチの Mermaid 図**（構成・シーケンス） |
| `docs/troubleshooting.md` | 起動失敗・ポート・よくある切り分け |

**旧ファイル名（参照・検索用のみ）:** `feeds-and-configuration.md` → `env-feeds.md`、`cloud-run-and-deployment.md` → `deploy.md`、`local-development.md` → `local.md`。

## `specs/*.md` の対応

`specs/` は **設計の意図・データモデル・サービス境界**を記述する（運用手順・コマンドは `docs/` が正）。

| ファイル | 内容 |
| --- | --- |
| `specs/README.md` | 論理アーキテクチャ・サービス境界の全体図（Mermaid）、各 spec へのリンク |
| `specs/collector-job.md` | 収集ロジック・`upsert_many`・RSS パース設計 |
| `specs/classifier-job.md` | 採点フロー・`relevance_score` の意味・Firestore クエリ設計 |
| `specs/commentator-job.md` | コメント生成フロー・`CommentResult`・プロンプト設計・stdout stats フォーマット |
| `specs/web-service.md` | FastAPI ルート設計・`ArticleStore.list_latest` の表示フィルター仕様 |
| `specs/profiler-job.md` | プロファイラ設計（設計先行の可能性あり） |
| `specs/blog-pages.md` | ブログ一覧・個別ページ設計（設計先行の可能性あり） |

**`specs/` を更新するのは次の場合**（コマンド・設定の変更だけなら `docs/` のみ）:

- Job やサービスの**処理フロー・入出力・データモデル**が変わった（例: `CommentResult` のフィールド追加、stdout stats の形式変更）
- `ArticleStore` のクエリ条件・表示フィルターの**仕様**が変わった
- Mermaid **シーケンス図**や**アーキテクチャ図**が実装と乖離した
- 新しい Job やサービスを追加した（対応する `specs/*.md` を新規作成 → `specs/README.md` の一覧表にも追加）

## 変更種別 → 直すファイル

| 触った領域 | 更新先（リポジトリルートからのパス） |
| --- | --- |
| Web のパス・HTML・`/rss`・`/api/*`・`/healthz` | `docs/api.md`、`specs/web-service.md`（表示フィルター仕様が変わった場合） |
| 環境変数・`feeds.json`・ストレージ | `docs/env-feeds.md` |
| `docker-compose`・`uv`・ディレクトリ・初回手順 | `docs/local.md` |
| Terraform・Cloud Run・Scheduler・GHA CD・bootstrap スクリプト・**Workflows / Job の順序・データフロー** | `docs/deploy.md`（必要ならルート `README.md` の概要 Mermaid も同じ PR で整合） |
| 起動失敗・ポート・よくある切り分け | `docs/troubleshooting.md` |
| Job の**処理フロー・入出力・stdout フォーマット**が変わった | 対応する `specs/<job>-job.md` |
| サービス全体のアーキテクチャ・コンポーネント境界 | `specs/README.md` の Mermaid |
| **新しい `docs/*.md` を増やした** | `docs/README.md` の一覧表に1行追加 **と**、ルート `README.md` にそのページへのリンクが必要なら追加・修正 |
| **新しい `specs/*.md` を増やした** | `specs/README.md` の一覧表に1行追加 |
| 入口・リンク・最短手順・一言説明 | ルート `README.md` |

## 手順（短く）

1. 上の表で **当たるファイルを全部** 開き、古い記述がないか確認。**`docs/` のリンクやリネームを触ったらルート `README.md` のリンクも確認**する。
2. パス・既定値・コマンド例は **実コード・`docker-compose.yml`・`infra/` と一致**させる。
3. **Mermaid** は GitHub でそのままレンダリングされる。ノード名や矢印が実構成とずれたら **README と `docs/deploy.md` の両方**を確認（二重管理は最小限にし、README は概要・deploy は詳細に寄せる）。
4. 新規ページを足したら **`docs/README.md`** を忘れない。
5. ユーザーが明示していなくても、**挙動が変わる変更ならドキュメント更新を提案または実施**する。

## やらないこと

- 仕様の長文を README に貼り付けて `docs/` と二重管理する。
- 依頼されていないのに無関係なドキュメントだけ大量リライトする。
