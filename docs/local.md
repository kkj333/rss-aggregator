# ローカル開発

## 起動とブラウザ

どちらか一方で起動すればよいです。**ブラウザでは `http://127.0.0.1:8000`（`http://localhost:8000` でも可）** を開きます。

### Docker（推奨）

コンテナ内の待受は **8080**（Cloud Run と揃えています）。Compose でホストの **8000** に転送しています。

ローカルでも stg の Firestore に接続するため、**初回のみ** Mac 上で次を実行してください：

```bash
gcloud auth application-default login
```

Web コンテナ用の環境変数は **`services/web/.env`** に置きます（`docker-compose.yml` の `env_file` で読み込み）。テンプレートは **`services/web/.env.example`** をコピーして編集してください（`services/web/.env` は Git に含めません）。

```bash
cp services/web/.env.example services/web/.env
# services/web/.env を開き GOOGLE_CLOUD_PROJECT を stg など実際のプロジェクト ID に書き換える
```

**補足:** `docker-compose.yml` 内の **`${GOOGLE_CLOUD_PROJECT}`**（profiler / collector 用）は、Compose が **リポジトリ直下の `.env`** からだけ展開します。警告を消したい・プロファイルジョブを使うときは、直下に同名の変数を書くか、コマンドラインで `GOOGLE_CLOUD_PROJECT=...` を付けてください。

起動：

```bash
cd rss-aggregator
docker compose up --build
```

初回や Dockerfile・依存関係を変えた直後は `--build` 付きが確実です。2回目以降は `docker compose up` でも構いません。

#### Docker で `--reload`（任意）

既定の Compose は **reload なし**です（Docker Desktop とマウントの相性で、ブラウザから繋がらない／不安定になる事例を避けるため）。コード変更のたびに反映したい場合は、リポジトリ直下に **`docker-compose.override.yml`**（未コミットでよい）を置き、例:

```yaml
services:
  web:
    command:
      [
        "uvicorn",
        "web.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
        "--reload",
      ]
    environment:
      WATCHFILES_FORCE_POLLING: "true"
```

`WATCHFILES_FORCE_POLLING` は Mac の Docker でファイル監視が効かないときの回避策です。

**Python（`services/web/web` など）を編集したとき:** この override を使っていない既定の Compose では **`docker compose restart web`** で反映します（`feeds.json` だけの変更はアプリが毎リクエストで読むため、再起動不要で従来どおり）。

#### Docker で pytest

`services/web`・`services/collector`・`services/classifier` のテストを **CI と同じく** コンテナでまとめて実行するには、profile **`test`** のサービス **`tests`** を使います。

```bash
docker compose --profile test build tests   # 初回や Dockerfile.compose-test 変更後
docker compose --profile test run --rm tests
```

`services/web/Dockerfile.compose-test` はルートの `uv.lock` で **`uv sync --frozen --dev`** します。`services/**` をマウントしているので、**テストやアプリ本体の変更は再ビルドなしで**反映されます（`uv.lock` や Dockerfile を変えたときは `build` が必要）。

Web のみに絞る例: `docker compose --profile test run --rm tests uv run pytest services/web/tests -q`（ユニットだけ: 同パスに `-m unit`、結合だけ: `-m integration`）

#### Docker で profiler（ブログ紹介の一括生成）

profile **`profiler`** のサービスは **`docker compose up` では起動しません**。一回実行して終了します。

```bash
PROFILER_DEBUG=true docker compose --profile profiler run --rm profiler
```

- Web 用は **`services/web/.env`**（**Docker（推奨）** 節の手順）。profiler / collector の Compose 展開用に **直下の `.env`** にも同じ変数を書いておくと便利です。
- Apple Silicon（Colima 等）で **`exit code 132`** になる場合は、`docker-compose.yml` の **`platform: linux/arm64`** が効くよう **`docker compose build --no-cache profiler`** で再ビルドする。
- 詳細は [feeds と環境変数](env-feeds.md)（Profiler の環境変数）、設計は [プロファイラ Job](../specs/profiler-job.md) を参照。

- `~/.config/gcloud` をコンテナにマウントして stg Firestore に接続します（`gcloud auth application-default login` 済みが前提）。
- `./feeds.json` をホストからマウントしている場合、**ホスト側でファイルを編集・保存したあと、ページを再読み込みすれば** **`/blogs` のブログ一覧**に反映されます（アプリは毎リクエストで読みます）。**コンテナや uvicorn の再起動は不要**です。
- イメージ **ビルド時にだけ** `Dockerfile` の `COPY feeds.json` が使われます。Compose で `./feeds.json` をマウントしていれば、実行中は常にホストのファイルが優先されます。

止めるときは同じディレクトリで `docker compose down` です。

`docker-compose.override.yml` で **`--reload` を有効にしている場合**、Docker Desktop（Mac/Windows）でファイル変更が拾われないときは、その override に **`WATCHFILES_FORCE_POLLING: "true"`** を追加するか、環境付きで一度起動して試してください（Linux の通常開発では不要）。

```bash
WATCHFILES_FORCE_POLLING=true docker compose up --build
```

**ブラウザで開けないとき**

- URL は **`http://127.0.0.1:8000`**（**https ではない**）。ホスト側のポートは **8000** で、コンテナ内の **8080** にマッピングしています（`localhost:8080` では開きません）。別プロジェクトの Compose で **8080** を既に使っている場合でも、**Web は 8000** です。
- `docker compose` は **`docker-compose.yml` があるリポジトリ直下**で実行してください（`infra/` など別ディレクトリだけだと別プロジェクト扱いになったり、期待どおり起動しないことがあります）。
- ターミナルで `curl -s http://127.0.0.1:8000/healthz` が `{"status":"ok"}` ならサーバーは動いています。ブラウザだけ失敗するときは拡張機能やプロキシを疑ってください。
- `curl` が繋がらないとき: `docker compose ps` で `web` が **Up** か確認し、`docker compose logs web --tail 50` で起動直後のエラーを見る。古いコンテナが残っている場合は `docker compose down` のあと `docker compose up --build` を試す。
- **`curl http://127.0.0.1:8000/healthz` は成功するのに `GET /` で「Empty reply」になり、すぐ `docker compose ps` で `web` が `Exited (132)` になる場合**  
  **`services/web/.env` に `GOOGLE_CLOUD_PROJECT` が入っている**と、トップの **`GET /` で Firestore（gRPC）にアクセス**します。Docker Desktop（特に **Apple Silicon**）と **gRPC のネイティブバイナリ**の組み合わせで、**終了コード 132（SIGILL 等）** になることがあります。`/healthz` は記事ストアを使わないため **だけ動いて見える**パターンです。  
  **既定の回避:** `docker-compose.yml` の **`web` に `platform: linux/amd64`** を指定しています（該当しない Linux 環境では外してよい）。**確認用の回避:** `services/web/.env` で **`GOOGLE_CLOUD_PROJECT` を外す**と **インメモリの `ArticleStore`** で起動し **`GET /` が 200** になります（一覧は空でも UI は確認できます）。stg の Firestore をそのまま読みたいときは、**Mac 上で `uv run uvicorn ...`**（README の uv 節）のように **ホストの ADC で直接繋ぐ**ほうが安定することが多いです。

### uv（Python 直接）

```bash
cd rss-aggregator
uv sync --dev --extra cloud
GOOGLE_CLOUD_PROJECT=<stg-project-id> \
FIRESTORE_COLLECTION=articles \
FEEDS_JSON_PATH=./feeds.json \
uv run uvicorn web.main:app --reload --app-dir services/web --port 8000
```

`gcloud auth application-default login` で ADC を設定済みであれば、Mac 上から直接 stg Firestore に繋がります。FastAPI の **`/docs`** をローカルで使うときだけ **`ENABLE_OPENAPI_DOCS=true`** を環境に付けるか `services/web/.env` に書いてください（既定は無効。本番と同じ）。

## 使い方（初回）

1. `gcloud auth application-default login` で ADC を設定する（初回のみ）。
2. `services/web/.env` に `GOOGLE_CLOUD_PROJECT=<stg-project-id>` を書く（`cp services/web/.env.example services/web/.env`）。
3. `feeds.json` を確認する（必要なら RSS の追加・削除）。
4. 上記の手順でアプリを起動し、`http://127.0.0.1:8000` を開く。
5. stg Firestore にすでに記事データがあればすぐに表示されます。ローカルで記事を追加したい場合は collector を実行します（Docker の場合は `docker compose --profile collector run --rm collector`）。
6. 一覧は **最初 50 件**表示です。件数が多いときは **「もっと見る」** で 50 件ずつ増やせます（**最大 200 件**まで。htmx が `/articles?limit=…` を取りに行きます）。

## ディレクトリ構成

リポジトリ直下の主要な配置です（`uv sync` 後の `.venv` などは含みません）。

```
rss-aggregator/
├── services/
│   ├── shared/
│   │   ├── shared/           # 共有パッケージ `shared`（config / models / storage）
│   │   └── pyproject.toml    # `rss-aggregator-shared`
│   ├── web/
│   │   ├── web/              # FastAPI UI パッケージ `web`（`main`・`routes/`・`core/`・`blog/`・`syndication/`）
│   │   ├── tests/
│   │   │   ├── unit/         # 純ロジック（`pytest -m unit`）
│   │   │   └── integration/ # TestClient（`pytest -m integration`）
│   │   ├── Dockerfile        # Web イメージ（Compose・Cloud Run）
│   │   └── pyproject.toml    # `rss-aggregator-web`
│   ├── collector/
│   │   ├── collect/          # RSS 収集（パッケージ `collect`）
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml    # `rss-aggregator-collector`
│   │   └── run.py
│   ├── classifier/
│   │   ├── classify/         # 採点（パッケージ `classify`）
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml    # `rss-aggregator-classifier`
│   │   └── run.py
│   ├── commentator/
│       ├── comment/          # コメント生成（パッケージ `comment`）
│       ├── tests/
│       ├── Dockerfile
│       ├── pyproject.toml    # `rss-aggregator-commentator`
│       └── run.py
│   └── profiler/
│       ├── feed_profiler/    # ブログ紹介生成（パッケージ `feed_profiler`）
│       ├── tests/
│       ├── Dockerfile
│       ├── pyproject.toml    # `rss-aggregator-profiler`
│       └── run.py
├── infra/
│   ├── main.tf
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   ├── variables.tf
│   └── versions.tf
├── .dockerignore
├── .gitignore
├── docker-compose.yml
├── README.md
├── docs/
├── feeds.json
├── pyproject.toml
└── uv.lock
```

## 開発

ルートの `pyproject.toml` が **uv workspace** の起点です。メンバーは `rss-aggregator-shared`（`services/shared`）、`rss-aggregator-web`（`services/web`）、`rss-aggregator-collector`（`services/collector`）、`rss-aggregator-classifier`（`services/classifier`）、`rss-aggregator-commentator`（`services/commentator`）、`rss-aggregator-profiler`（`services/profiler`）の 6 つ。`uv sync --dev` で全て開発用に入ります。

```bash
uv sync --dev
uv run pytest
uv run ruff check services/shared/shared/ services/web/web/ services/collector/ services/classifier/ services/commentator/ services/profiler/
```

`services/web` のみ実行する例: `uv run pytest services/web/tests -q`。層別には **`pytest -m unit`**（`tests/unit/`）と **`pytest -m integration`**（`tests/integration/`）。マーカー定義は `services/web/pyproject.toml` の `[tool.pytest.ini_options]`。
