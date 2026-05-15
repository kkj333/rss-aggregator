# feeds と環境変数

## feeds.json

リポジトリ同梱の `feeds.json` に **ブログ・ニュースなど複数ソースの RSS / Atom（RDF 形式含む）の例** を入れています（クローン直後からマルチソースで試せます）。不要な行は削除し、追記で増やしてください。

各オブジェクトは **`title` と `url`（購読用フィード URL）が必須**です。オプションで **`site_url`** に **ブラウザで読むサイトのトップ URL** を `http://` または `https://` で書けます。オプションで **`slug`**（小文字・数字・ハイフンのみ、例: `mitsubishi-salaryman`）を書くと **ブログ個別ページが `/blogs/{slug}`** になります（省略時は従来どおり `feed_url` の SHA-256 hex）。`/blogs` の一覧リンク・canonical・`GET /api/feeds` の `slug` に反映されます。一部サイトでフィード取得に失敗する場合のみ、任意で **`user_agent`** に文字列を指定できます（収集ジョブの HTTP リクエストに使われます）。

### JSON への追記例

配列の **末尾のオブジェクトの後にカンマを付けて**、次のように 1 ブロック追加します（JSON では最後の要素の後ろにカンマを付けないこと）。

```json
  {
    "title": "ブログの表示名",
    "url": "https://example.com/feed.xml",
    "site_url": "https://example.com/",
    "slug": "my-blog-slug"
  }
```

`site_url` を省略すれば、`url`（RSS）だけが登録されます。

編集後は **ページを再読み込み**すれば **`/blogs` のブログ一覧**が更新されます（ホストマウントまたはローカルファイルを直接編集している場合）。環境変数 `FEEDS_JSON_PATH` で別パスを指定することもできます。

`feeds.json` は **HTTP リクエストのたびに**読み直すため、アプリのプロセス再起動や Docker コンテナの再起動は **不要**です（ホストをボリュームマウントしている場合）。

> **ストレージ**: SQLite は廃止済みです。記事の永続化はすべて **Firestore** で行います。ローカル開発は stg の Firestore をそのまま使います（詳細は [ローカル開発](local.md)）。

## 環境変数

Docker Compose の Web 用の雛形は **`services/web/.env.example`** を **`services/web/.env`** にコピーして編集します（`services/web/.env` は Git に含めません）。`uv` でホスト直起動するときも同じ変数名を使えます。

名前と既定値は **`services/shared/shared/config.py` の `Settings`** が正です。すべてのコンポーネントが同じ変数名を読みますが、**実際に効く場所**が違うので、下では用途ごとに表を分けています。

### フィード定義・ストレージ（Web・collector Job・Firestore を使う Job）

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `GOOGLE_CLOUD_PROJECT` | なし（**必須**） | GCP プロジェクト ID。未設定時 Web は記事なしで起動（`InMemoryArticleStore`）、collector はエラー |
| `FIRESTORE_COLLECTION` | `articles` | Firestore コレクション名 |
| `FEEDS_JSON_PATH` | （プロジェクト直下の）`feeds.json` | 読み込むフィード定義ファイルのパス |
| `FIRESTORE_FEEDS_COLLECTION` | `feeds` | Web がブログ紹介文（`profile`）を読むコレクション名。Profiler Job の書き込み先と揃える |

### Web（Cloud Run サービス）

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `APP_NAME` | `RSS Aggregator` | 画面タイトルなど |
| `PUBLIC_BASE_URL` | なし | 本番の絶対 URL（末尾スラッシュ不要）。未設定時はリクエストから。canonical・`/rss`・`robots.txt`・`sitemap.xml` に使う |
| `GA_MEASUREMENT_ID` | なし | Google Analytics の測定 ID（例: `G-…`）。未設定時はページに計測タグを出さない |
| `ENABLE_OPENAPI_DOCS` | `false` | `true` / `1` / `yes` / `on` のときだけ FastAPI の **`/docs`**・**`/redoc`**・**`/openapi.json`** を有効化。本番 Cloud Run では未設定のまま（既定オフ）を推奨 |

### 関連度しきい値（Web の一覧・`/rss` と commentator Job）

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `RELEVANCE_THRESHOLD` | `0.5` | Web のトップ・`/articles`・`/rss` では `relevance_score >= しきい値` かつ `ai_comment` が存在する記事のみ表示する。commentator は**コメント対象**を選ぶときに同じ値を使う（`GET /api/articles` はフィルタしない） |

### 採点 Job（classifier）

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `GEMINI_LOCATION` | `global` | Vertex AI のリージョン |
| `GEMINI_MODEL` | `gemini-3-flash-preview` | 使用モデル。Firestore の `classifier_version` に記録される |
| `CLASSIFY_BATCH_SIZE` | `100` | 1 回の実行で採点する最大記事数 |

### コメント生成 Job（commentator）

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `GEMINI_LOCATION` | `global` | Vertex の場所（ジョブ起動時に `GOOGLE_CLOUD_LOCATION` の既定にも使う） |
| `COMMENTATOR_MODEL` | `gemini-3-flash-preview` | 使用モデル。Firestore の `commentator_version` に記録される |
| `COMMENT_BATCH_SIZE` | `50` | 1 回の実行でコメントする最大記事数 |

### Profiler Job（ブログ紹介）

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `GEMINI_LOCATION` | `global` | Vertex の場所 |
| `PROFILER_MODEL` | `gemini-3-flash-preview` | 使用モデル（Firestore の `profiler_version` に記録） |
| `PROFILER_SKIP_EXISTING` | `true` | `true` のとき Firestore の `profile` が既に非空ならそのフィードはスキップ |
| `PROFILER_DEBUG` | （未設定） | `true` / `1` / `yes` のときログレベルを DEBUG に（ローカルや切り分け用） |
