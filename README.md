# MCP RAG Server

[![CI](https://github.com/tadata-org/mcp-rag-server/actions/workflows/pytest.yml/badge.svg)](https://github.com/tadata-org/mcp-rag-server/actions/workflows/pytest.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Model Context Protocol (MCP) に準拠したRAG（Retrieval-Augmented Generation）機能を持つPythonサーバーです。
`fastapi-mcp` を利用して、FastAPIアプリケーションをMCPサーバーとして公開します。

## 特徴

- **MCP準拠**: Model Context Protocol をサポートし、対応クライアントと連携できます。
- **RAG機能**: 指定されたドキュメントをベクトル化し、セマンティック検索を提供します。
- **FastAPIベース**: `fastapi-mcp` を使用し、FastAPIの強力な機能を活用しています（自動APIドキュメント、依存性注入など）。
- **拡張性**: 新しいツールセットをモジュールとして簡単に追加できます。
- **認証**: APIキーによる認証機能をサポートしています。
- **Docker対応**: PostgreSQL + pgvector を Docker で簡単にセットアップできます。

## セットアップと実行

### 1. 前提条件

- [Python 3.10+](https://www.python.org/)
- [Docker](https://www.docker.com/) と [Docker Compose](https://docs.docker.com/compose/)
- [uv](https://docs.astral.sh/uv/) (推奨パッケージインストーラー)

### 2. 環境設定

#### a. 仮想環境の作成と依存関係のインストール

```bash
# 仮想環境を作成
python -m venv .venv
source .venv/bin/activate

# uvを使って依存関係をインストール
uv pip install -r requirements.txt
```

#### b. 環境変数の設定

`.env.sample` ファイルをコピーして `.env` ファイルを作成します。

```bash
cp .env.sample .env
```

`.env` ファイルには、データベースの接続情報やAPIキーなどが含まれています。必要に応じて値を変更してください。

```dotenv
# .env
# PostgreSQL接続情報
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=ragdb

# サーバーの認証に使用するAPIキー
API_KEY=your-secret-api-key

# ドキュメントのソースディレクトリ
SOURCE_DIR=data/source
# 処理済みドキュメントを保存するディレクトリ
PROCESSED_DIR=data/processed

# 埋め込みモデル
EMBEDDING_MODEL=intfloat/multilingual-e5-large
```

### 3. データベースの起動

Docker Compose を使用して、`pgvector` をサポートしたPostgreSQLデータベースを起動します。

```bash
docker-compose up -d
```

データベースを停止する場合は、以下のコマンドを実行します。

```bash
docker-compose down
```

### 4. ドキュメントのインデックス化

検索対象のドキュメントを `data/source` ディレクトリに配置してください。
その後、CLIを使用してドキュメントをインデックス化します。

```bash
python -m src.cli index
```

このコマンドは、`data/source` 内のドキュメントを読み込み、チャンクに分割し、ベクトル化してデータベースに保存します。

### 5. MCPサーバーの起動

以下のコマンドでMCPサーバーを起動します。

```bash
python -m src.main
```

サーバーはデフォルトで `http://0.0.0.0:8000` で起動します。

#### オプション

- `--no-auth`: APIキー認証を無効にしてサーバーを起動します。
- `--module <module_name>`: 追加のツールモジュールを読み込みます (例: `--module src.example_tool`)。

## APIのテスト (Swagger UI)

サーバーが起動したら、Webブラウザで **`http://localhost:8000/docs`** にアクセスしてください。

FastAPIによって自動生成されたSwagger UIが表示され、以下のことが可能です。

- **API仕様の確認**: 各エンドポイント（ツール）の詳細な仕様（パス、パラメータ、レスポンスなど）を確認できます。
- **インタラクティブなテスト**: 「Try it out」機能を使って、ブラウザから直接APIを呼び出し、レスポンスを確認できます。
- **認証**: 認証が必要な場合（`--no-auth` なしで起動した場合）、右上の「Authorize」ボタンをクリックし、`.env` で設定したAPIキーを `X-API-KEY` ヘッダーとして入力することで、認証付きのAPIをテストできます。

![Swagger UI Screenshot](docs/swagger-ui-example.png)

## 開発と貢献

### 追加ツールの作成

1. `src` ディレクトリに新しいPythonファイルを作成します (例: `src/my_tools.py`)。
2. `fastapi.APIRouter` を使用して、ツールとなるAPIエンドポイントを定義します。
3. `register_tools(server)` 関数を定義し、その中で作成したルーターを `server.register_router()` を使って登録します。
4. サーバー起動時に `--module src.my_tools` のように指定して、作成したツールを読み込みます。

詳細な例として `src/example_tool.py` を参照してください。

### コントリビューション

Issueの報告やPull Requestを歓迎します。貢献する前に `CONTRIBUTING.md` をお読みください。

## ライセンス

[MIT License](LICENSE)
