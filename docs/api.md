# HTTP エンドポイント

Web サービスは **人がブラウザで見る画面（HTML）** と **`curl` や監視向けの JSON・ヘルス等** を分けて考えると整理しやすいです。実装上は同じ FastAPI アプリですが、用途が異なります。

## ブラウザ向け（HTML）

| メソッド | パス | 説明 |
| --- | --- | --- |
| GET | `/` | メイン画面 |
| GET | `/about` | サイト紹介・掲載一覧・お問い合わせ案内などの静的 HTML（ヘッダー／フッターのナビ表記は「About」） |
| GET | `/blogs` | ブログ一覧（掲載元の HTML）。クエリ `page` は 1〜500、既定 1。1 ページあたりの件数は `services/web/web/core/constants.py` の `FEEDS_PAGE_SIZE`（既定 20） |
| GET | `/blogs/{path}` | ブログ個別ページ（紹介文＋当該フィードの記事一覧）。紹介文は Firestore **`feeds`** の **`profile`**（Profiler Job が生成）。`feeds.json` に **`slug`** があれば `/blogs/{slug}`、なければ **`feed_url` の SHA-256 hex 64 文字**。legacy の hex URL は **`slug` があるとき 301 で `/blogs/{slug}` へ**リダイレクト。未登録なら 404 |
| GET | `/feeds` | `/blogs` への **301 リダイレクト**（`/feeds?page=N` は `/blogs?page=N` へ） |
| GET | `/articles` | 記事一覧の HTML フラグメント（htmx 向け。**先頭から `limit` 件**をまとめて返す。`limit` は 1〜200、既定 50。「もっと見る」は 50 件ずつ `limit` を増やして `#collection-area` を差し替え） |
| GET | `/static/...` | CSS など静的ファイル |
| GET | `/rss` | 集約新着の **RSS 2.0**（購読アプリ向け。HTML テンプレートには `/rss` への目立ったリンクは置かず、`<head>` の `<link rel="alternate" type="application/rss+xml">` で検出可能）。チャンネルの `<link>`（サイトの代表 URL）は **ブログ一覧 `/blogs`**。各 item の `link` は元記事 URL。クエリ `limit` は 1〜200、既定 50 |

HTML では **トップの記事タイトル**（元記事 URL）・**掲載元名**（当サイトの **`/blogs/{slug|hex}`**）・**ブログ一覧のブログ名**（同）・掲載元の **ホームページ／RSS** を **`target="_blank"`**（別タブ・`rel="noopener noreferrer"`）で開きます。サイト内の **`/`・`/about`・`/blogs`（一覧）** などへのナビは同一タブのままです。

トップ・`/articles`・`/rss` は **`relevance_score >= RELEVANCE_THRESHOLD` かつ `ai_comment` が存在する記事のみ**返します（評価＋コメント生成が完了したものだけ表示）。

### トップの「もっと見る」（HTML）

- 初回は先頭 **50 件**のみ表示し、続きがあるときだけ **「もっと見る」** を出します。
- クリックで htmx が `GET /articles?limit=100` … のように **`limit` を 50 ずつ増やし**（最大 **200**）、`#collection-area` 内を差し替えます。
- 表示上限の定数は `services/web/web/core/constants.py` の `ARTICLE_MAX_DISPLAY`（既定 200）です。

## JSON API（一覧・デバッグ用）

画面とは別に、データだけ JSON で返すパスです（監視・切り分け・外部連携を想定しないならブラウザでは開かなくてよい）。

| メソッド | パス | 説明 |
| --- | --- | --- |
| GET | `/api/feeds` | `feeds.json` に基づく登録ソース一覧（各要素に `title`・`url`・`site_url`・`slug`。未設定時は `site_url` / `slug` が `null`。実行時の確認用・機械可読） |
| GET | `/api/articles` | 記事一覧 JSON（クエリ `limit` は 1〜200、既定 50）。**関連度しきい値・コメント有無は適用しない**（新着順のみ）。トップ・`/articles`・`/rss` とは異なりフィルタなしで全記事を返す |

OpenAPI（Swagger UI **`/docs`**、ReDoc **`/redoc`**、スキーマ **`/openapi.json`**）は **既定で無効**です。ローカルで有効にする場合のみ環境変数 **`ENABLE_OPENAPI_DOCS=true`**（または `1` / `yes` / `on`）を設定してください（[feeds と環境変数](env-feeds.md) の Web 表）。

## 運用

| メソッド | パス | 説明 |
| --- | --- | --- |
| GET | `/healthz` | ヘルスチェック（`{"status":"ok"}`） |
| GET | `/robots.txt` | クローラ向け（`Sitemap:` に絶対 URL。`PUBLIC_BASE_URL` 推奨） |
| GET | `/sitemap.xml` | サイトマップ（`/`・`/about`・`/blogs` および `feeds.json` 各掲載元の `/blogs/{slug|hex}`） |

---

**公開運用時の注意:** HTML も JSON も **認証はかけていません**。インターネットにそのまま晒す場合は、リバースプロキシや Cloud Run/IAP でアクセスを制限するなどの対策を検討してください（JSON は機械可読なので、画面より第三者が叩きやすい点もあります）。
