# Commentator Job（`services/commentator`）

## 目的

Firestore の記事のうち、**関連度が閾値以上**かつ **まだ AI コメントが無い**ものに対し、Vertex AI（Gemini）で **短い一言コメント**を生成し、`ai_comment` 等を書き戻す。

## アーキテクチャ（境界）

Classifier と同様 **Firestore 必須**。記事 URL を渡せば **`comment.fetcher`** が robots 確認のうえ HTML を取得し、本文テキストをプロンプトに足す（取得失敗時は要約のみ）。

```mermaid
flowchart LR
    FS[(Firestore articles)]
    J[Commentator Job]
    F[HTTP fetcher]
    V[Vertex AI Gemini]
    FS2[(Firestore articles)]

    FS -->|list_uncommented| J
    J -->|任意: 元記事 URL| F
    F -->|本文抜粋| J
    J -->|title+summary+body?| V
    V -->|コメント| J
    J -->|update_comment| FS2
```

## シーケンス（1 記事）

```mermaid
sequenceDiagram
    autonumber
    participant Job as Commentator Job
    participant St as CommentatorStore
    participant F as fetch_article_text
    participant C as ArticleCommenter
    participant V as Vertex AI

    Job->>St: list_uncommented(min_score=RELEVANCE_THRESHOLD)
    St-->>Job: Article[]
    loop 各記事
        Job->>C: comment(title, summary, url)
        C->>F: fetch_article_text(url)
        F-->>C: body or empty
        C->>V: プロンプト生成
        V-->>C: 一文コメント
        C-->>Job: CommentResult（ai_comment, token counts）
        Job->>St: update_comment(...)
    end
    Job->>Job: stdout JSON stats（total/commented/failed/tokens）
```

## 環境変数（主要）

| 変数 | 必須 | 備考 |
| --- | --- | --- |
| `GOOGLE_CLOUD_PROJECT` | はい | |
| `RELEVANCE_THRESHOLD` | いいえ | コメント対象の下限スコア |
| `COMMENTATOR_MODEL` | いいえ | |
| `COMMENT_BATCH_SIZE` | いいえ | 1 回の最大件数 |
| `GEMINI_LOCATION` | いいえ | Vertex リージョン |

`GOOGLE_GENAI_USE_VERTEXAI` は run.py で既定セットされる。

## 実装参照

- `services/commentator/run.py`
- `services/commentator/comment/commenter.py`
- `services/commentator/comment/fetcher.py`
