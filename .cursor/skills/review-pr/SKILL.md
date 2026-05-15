---
name: review-pr
description: Review a GitHub pull request by fetching its diff and metadata with gh CLI, then report findings by severity. Use when the user asks to review a PR, says "レビューして", or provides a PR number or GitHub PR URL.
disable-model-invocation: true
---

# PR レビュー

## 手順

1. **PR情報と差分を取得**（親エージェントが並列実行）

```bash
gh pr view <number> --json title,body,files,commits,headRefName,baseRefName,url
gh pr diff <number>
```

URLが渡されたときは番号を抽出する（例: `.../pull/49` → `49`）。

2. **`code-reviewer` サブエージェントにレビューを委譲する**

取得した diff テキストと PR メタ情報を prompt に埋め込んで `code-reviewer` サブエージェントを呼び出す。
`gh` 認証やリポのパスに依存するコマンド（`terraform validate` など）は親エージェントが先に実行し、その出力もサブエージェントの prompt に含める。

> **サブエージェントに渡す prompt のテンプレート**
>
> ```
> 以下の PR をレビューしてください。
>
> ## メタ情報
> <gh pr view の JSON 出力をここに貼る>
>
> ## diff
> <gh pr diff の出力をここに貼る>
>
> ## 事前検証結果（あれば）
> <terraform validate / uv run pytest などの出力をここに貼る>
>
> 報告フォーマット: Critical(blocking) → Medium → Low/Nit の順。
> blocking がなければ冒頭に「Approve してよい」と書くこと。
> ```

3. **サブエージェントの結果を受け取りユーザーに報告**（下記フォーマット）

## 報告フォーマット

- **blocking（マージ前に修正必須）** があれば先頭に明示
- blocking がなければ「Approve してよい」と結論を先に書く
- 指摘は以下の3段階で分類：
  - **Critical（blocking）**: バグ・セキュリティリスク・データ破壊の恐れ
  - **Medium**: 運用リスク・非効率・将来の問題になりうる箇所
  - **Low / Nit**: スタイル・命名・軽微な改善提案
- 指摘がない項目はセクションを省略する
- コードを引用するときはファイルパスと行番号を示す

## 注意

- `terraform validate` や `uv run pytest` など、検証できるものは実際に実行して結果を示す
- スコープ外の既存コードへの指摘は「Nit（スコープ外）」として分ける
- 「問題なし」のときは理由を一言添える
