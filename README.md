# ヘルプQAチャットボット

既存のウェブサイトにヘルプチャットウィジェットを追加するブラウザ拡張機能と、ベクトル検索で回答を返すバックエンドAPIのセットです。

## プロジェクト概要

ユーザーがヘルプページに関する質問をチャット形式で入力すると、あらかじめインデックスしたQAデータから意味的に近い回答を返します。OpenAI のEmbeddingモデルでベクトル化し、ChromaDB で近傍検索を行います。

## システム構成図

```
[ブラウザ]
  └─ 拡張機能 (content.js)
       │  fetch POST /api/chat
       ▼
[FastAPI バックエンド :8000]
  ├─ POST /api/chat      ... ベクトル検索して回答を返す
  ├─ GET  /api/health    ... ヘルスチェック
  └─ POST /api/index     ... QAデータを再インデックス
       │
       ├─ OpenAI Embeddings API  (テキスト → ベクトル変換)
       └─ ChromaDB (ローカル永続化)  (ベクトル近傍検索)

[バッチ処理]
  └─ batch/ingest.py     ... sample_qa.json を読み込んでインデックスに投入
```

## セットアップ手順

### 前提条件

- Docker / Docker Compose がインストール済みであること
- OpenAI APIキーを取得済みであること

### 1. 環境変数の設定

`.env.example` を参考に `.env` ファイルを作成します。

```bash
cp .env.example .env
```

`.env` を編集して OpenAI APIキーを設定します。

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

### 2. Docker でバックエンドを起動

```bash
docker-compose up -d --build
```

起動確認:

```bash
curl http://localhost:8000/api/health
# {"status":"ok"}
```

### 3. QAデータのインデックス投入

バックエンドコンテナ内でバッチを実行します。

```bash
docker-compose exec backend python -m batch.ingest
```

または、APIエンドポイント経由でも実行できます。

```bash
curl -X POST http://localhost:8000/api/index
```

### 4. 動作確認

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "料金はいくらですか"}'
```

## ブラウザ拡張機能の導入手順

### Chrome / Edge の場合

1. ブラウザのアドレスバーに `chrome://extensions` と入力して拡張機能管理ページを開く
2. 右上の「デベロッパーモード」をオンにする
3. 「パッケージ化されていない拡張機能を読み込む」をクリック
4. `/workspace/extension` ディレクトリを選択する
5. 拡張機能が追加されたら、任意のウェブページを開くと右下にチャットボタンが表示される

### 注意事項

- バックエンドが `http://localhost:8000` で起動している必要があります
- `manifest.json` の `host_permissions` でバックエンドURLを許可しています
- 本番環境では `host_permissions` と CORS 設定を適切なドメインに制限してください

## API仕様

### POST /api/chat

ユーザーの質問に対して最適なQA回答を返します。

**リクエスト:**

```json
{
  "message": "料金はいくらですか？"
}
```

**レスポンス:**

```json
{
  "answer": "基本プランは月額1,980円（税込）です。年払いの場合は月額1,650円になりお得です。",
  "matched_qas": [
    {
      "question": "料金はいくらですか？",
      "answer": "基本プランは月額1,980円（税込）です。年払いの場合は月額1,650円になりお得です。",
      "score": 0.9512,
      "category": "料金",
      "url": "/pricing"
    }
  ]
}
```

### GET /api/health

サービスの死活確認。

**レスポンス:**

```json
{"status": "ok"}
```

### POST /api/index

QAデータをベクトルDBに再投入します。

**レスポンス:**

```json
{
  "status": "ok",
  "indexed_count": 20
}
```

## ディレクトリ構成

```
/workspace/
├── backend/
│   ├── app/
│   │   ├── config.py        # 環境変数管理 (pydantic-settings)
│   │   ├── models.py        # Pydantic モデル定義
│   │   ├── vector_store.py  # ChromaDB ラッパー
│   │   ├── main.py          # FastAPI アプリ
│   │   └── routes/
│   │       ├── chat.py      # POST /api/chat
│   │       ├── health.py    # GET /api/health
│   │       └── index.py     # POST /api/index
│   ├── batch/
│   │   ├── data_source.py   # QAデータ読み込み抽象化
│   │   ├── sample_qa.json   # サンプルQAデータ (20件)
│   │   └── ingest.py        # インデックス投入バッチ
│   ├── Dockerfile
│   └── requirements.txt
├── extension/
│   ├── manifest.json        # 拡張機能マニフェスト (Manifest V3)
│   ├── content.js           # チャットウィジェット本体
│   ├── content.css          # ウィジェットスタイル
│   └── background.js        # Service Worker
├── docker-compose.yml
├── .env.example
└── README.md
```

## 今後の改善ポイント

### 機能面

- **LLMによる回答生成**: 現在は最類似QAの回答をそのまま返しているが、GPT-4などを使ってより自然な文章で回答を生成する
- **会話履歴の管理**: マルチターン会話に対応し、前の質問の文脈を踏まえた回答を行う
- **ヘルプページのスクレイピング**: `data_source.py` の `_load_from_scraping` を実装し、実際のヘルプページから自動でQAデータを生成する
- **フィードバック機能**: 回答に「役に立った/役に立たなかった」ボタンを追加し、品質改善に活用する

### インフラ面

- **ChromaDBのサーバーモード化**: 現在はローカル永続化だが、ChromaDB をサーバーとして独立させてスケーラビリティを向上させる
- **認証・認可**: APIエンドポイントにAPIキー認証を追加してセキュリティを強化する
- **レート制限**: 過剰なリクエストを防ぐためのレート制限を実装する
- **キャッシュ**: 同一クエリに対するキャッシュを導入してレスポンス速度を向上させる

### 運用面

- **ログ・モニタリング**: 構造化ログ出力と外部モニタリングサービスへの連携
- **CI/CD**: テストと自動デプロイのパイプラインを整備する
- **QAデータ管理UI**: 管理者がブラウザからQAデータを編集・追加できる管理画面の実装
