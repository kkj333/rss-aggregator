---
name: create-pr
description: >-
  このリポジトリの変更をブランチに切り出し、日本語のプルリクエストを作成する。
  PR を出す、プルリクを作る、ブランチを切ってPRを出す、と言われたら使う。
disable-model-invocation: true
---

# PR 作成（rss-aggregator）

## 事前チェック

PR を出す前に必ず通す。

```bash
uv run ruff check services/shared/shared/ services/web/web/ services/collector/ services/classifier/
uv run pytest -q
cd infra && terraform fmt -check -recursive && terraform validate   # Terraform を変更した場合のみ
```

失敗したら先に直す。

## ブランチ作成

```bash
git checkout main && git pull origin main
git checkout -b <prefix>/<slug>
```

prefix: `feature/`（新機能）、`fix/`（バグ修正）、`refactor/`（リファクタ）

## コミット

意味のある単位でコミットする。メッセージは日本語または英語（リポの慣習に合わせる）。

```bash
git add -A
git commit -m "$(cat <<'EOF'
<件名（何をどう変えたか>

<必要なら本文>
EOF
)"
```

## Push & PR 作成

```bash
git push -u origin <branch>
gh pr create --title "<日本語タイトル>" --body "$(cat <<'EOF'
## 概要

<1〜3行で何のPRか>

## 変更内容

| ファイル／領域 | 内容 |
| --- | --- |
| `path/to/file` | 説明 |

## 受け入れ条件の確認

- [ ] `uv run pytest` 全テスト通過
- [ ] `uv run ruff check` クリーン
- [ ] （Terraform変更があれば）`terraform validate` 通過
- [ ] （該当する場合）`services/collector/` のコードは変更なし
EOF
)"
```

## タイトルの書き方

| 種別 | 例 |
| --- | --- |
| 新機能 | `採点 Cloud Run Job（services/classifier）を新規追加` |
| バグ修正 | `fix(infra): Workflow 作成前に actAs IAM が完了するよう depends_on を追加` |
| 設定変更 | `Gemini モデルを gemini-3-flash-preview に変更` |

## やらないこと

- `main` へ直接 push しない
- `--force` push は明示指示がない限り使わない
- テストが落ちたまま PR を出さない
