---
name: git-tagging
description: >-
  Drafts release notes, creates annotated semver tags, pushes new tags to origin,
  or when main matches the latest tag creates/publishes the GitHub Release only.
  Use for tagging, release notes, changelog, git tag, GitHub Release, versioning.
disable-model-invocation: true
---

# Git タグ付け（リリース用）

このスキルが付いた依頼では、**同一の応答のうちに**次まで **必ず** やり切る（ユーザーへの返信は、その実行のあとでよい）。

**A. 前タグから `main` の HEAD までにコミットがあるとき（通常）:** リリース文案（テンプレ）→ 注釈タグ `git tag -a` → **`git push origin <tagname>`**。タグの `-m` は一行要約にし、詳細は返信内の Markdown と GitHub Release 本文／`CHANGELOG.md` に載せる想定。

**B. 差分ゼロのとき（`git log <前タグ>..HEAD` が空、または `HEAD` が直近 `v*` と同一コミット）:** 新タグ・新タグの push は **行わない**。その版のリリース文案をテンプレどおり書き、**GitHub Release だけ** 行う: `gh release view <tag>` で未作成なら `gh release create <tag> --title "<tag>" --notes-file …`（既に Release があるなら作成はスキップし、チャットで「既存」と報告してよい）。

**ここまでがスキルの完了条件。** 「案だけ出して終わり」にしない。例外は次のみ: ユーザーが **「案のみ」「下書きだけ」「タグは打たない」「push しない」** のいずれかを明示したとき。または **メジャー上げ・特定 SHA へのタグ・過去コミットへの付け直し** が依頼に含まれるときは、semver／対象コミットを一言確認してから実行する（曖昧なら質問して止まる）。**追加で** GitHub Release まで欲しい場合は A でも `gh release create` を実行してよい（タグ push のあと）。

**通常フローで止めてはならないこと:** リリース文案を出したあとに「よければタグを」と確認して待つ、タグだけ付けて push しない、など。

**状態確認・差分取得・タグ打ちのいずれでも、`git fetch` のあとに追跡ブランチを `git pull` で最新化してから** `describe` や `git log`、注釈タグを付ける（古い main のままタグを打たない）。

## リリース文の作り方（エージェント向け）

1. **追跡ブランチを最新化:** `git fetch --tags origin` のあと `git checkout main`（またはリリース用ブランチ）し、`git pull origin main`。
2. **前タグを決める:** `git describe --tags --abbrev=0` または直近の `v*` タグを確認。初回ならリポジトリの最初のコミットからでよい。
3. **差分を集める:** `git log <前タグ>..HEAD --oneline` と、可能ならマージコミットや PR タイトル（`gh pr list --state merged` や GitHub の Compare）を参照。**ログが空なら分岐 B**（新タグは打たず、既存の `<前タグ>` について GitHub Release のみ）。
4. **ユーザー向けに整形:** 下記テンプレで Markdown をチャットに出力。破壊的変更・運用注意があれば先頭付近に明示。
5. **タグメッセージ（分岐 A のみ）:** `git tag -a vX.Y.Z -m "Release vX.Y.Z: <一行要約>"` の `<一行要約>` はリリース文の要約に合わせる。
6. **注釈タグを付ける（分岐 A のみ）:** `git tag -a vX.Y.Z -m "..."`（軽量タグにしない）。
7. **リモートへ push（分岐 A のみ）:** `git push origin vX.Y.Z`（まとめて `--tags` は使わず、今回のタグだけでよい）。
8. **GitHub Release（分岐 B、またはユーザーが Release まで欲しいとき）:** 既存タグ `vX.Y.Z` に対し `gh release create`（`--notes-file` 推奨）。分岐 A で Release も作るなら 7 のあとに同様に実行。

### リリース文テンプレ（コピー用）

```markdown
## vX.Y.Z (YYYY-MM-DD)

### Highlights
- （利用者に効く変更を1〜3件）

### Changes
- （箇条書き。必要なら Added / Fixed / Changed に分類）

### Notes
- （マイグレーション、環境変数、デプロイ手順などあれば）
```

### GitHub Release

**分岐 B（差分ゼロ）では必須。** 分岐 A では任意だが、作るならタグ push のあとに同じ本文でよい。

本文を一時ファイル（例: `release-notes-vX.Y.Z.md`）に保存したうえで:

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file release-notes-vX.Y.Z.md
```

タグが未作成なら `gh release create` がタグも作る（`--generate-notes` で自動草案も可。品質は要確認）。

## いつ付けるか

- **main（またはリリースブランチ）に、リリースとして十分な変更が入ったあと**
- CI が通っているコミットを指す（ローカルだけで未 push のコミットに付けるのは避ける）

## 命名

- **推奨:** `v` + セマンティックバージョン（例: `v0.3.0`, `v1.0.0`）
- 互換性のない変更はメジャー、後方互換の追加はマイナー、修正のみはパッチ

## 付け方（注釈付きタグ）

リリース用途では **annotated tag**（`-a`）を使う。軽量タグは注釈・日付が弱く、リリースには不向き。

```bash
git fetch --tags origin
git checkout main
git pull origin main
git tag -a v0.3.0 -m "Release v0.3.0"
git push origin v0.3.0
```

過去のコミットに付ける場合（リリースの取り直しなど。**意図した SHA か**必ず確認）:

```bash
git tag -a v0.3.0 <commit_sha> -m "Release v0.3.0"
git push origin v0.3.0
```

通常の「今の main の先頭に付ける」なら、上のフル手順どおり **fetch → checkout → pull → tag → push** まで行う（push 省略不可）。

## 現状のタグを把握する

**自動取得の仕組み（API・CI）はリポジトリにはない。** 手元またはエージェントがシェルで次を実行する。

```bash
git fetch --tags origin
git checkout main
git pull origin main
# ローカルに載っている v*（fetch 後はリモート由来も含む）
git tag -l 'v*' --sort=-version:refname
# リモート origin のタグ一覧（push 漏れやリモート専用タグの確認）
git ls-remote --tags origin
# 現在の HEAD が「直近の v* タグから何コミット進んだか」
git describe --tags --always
```

特定版のメタデータ: `git show v0.3.0`（注釈・対象コミット・日時）

## ミスしたとき

- **まだ push していない:** `git tag -d v0.3.0` で削除して付け直し
- **既に push 済み:** チーム方針に従う。一般に **公開タグの書き換え（force push）は避ける**。誤りなら次のパッチ版（例: `v0.3.1`）で正す方が安全

## まとめて push

```bash
git push origin --tags
```

初回や整理時以外は、**必要なタグだけ** `git push origin <tagname>` の方が安全
