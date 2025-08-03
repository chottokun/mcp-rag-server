# Docker Compose 環境構築・運用指針

本ドキュメントは、Docker Compose を用いて再現性が高く、開発と本番の両方で利用しやすいコンテナ環境を構築するための指針を定めます。GPU と CPU のどちらの環境でも動作できるように、設定の切り替えや上書きが容易な構成を目指します。

## 全体的な指針

提示する実装方針は、理論的に極めて堅牢であり、実現可能性も非常に高いと結論付けます。ディスク容量という環境依存の物理的制約さえクリアできれば、この方針でプロジェクトを成功に導くことができます。

最重要戦略として、まずは CPU 版に特化してビルドを成功させることを目指します。`pyproject.toml` から `torch` の明記をなくし、依存関係を最小に抑えることが重要です。巨大なモデルファイル（約2.24GB）のダウンロードが最後のハードルとなりますが、本指針で示すキャッシュ戦略により、再ダウンロードを防ぎます。

将来的な GPU への拡張、CI/CD 連携など、発展性も十分に考慮された、スケーラブルな設計です。

---

## 0. 事前確認と考慮事項

Docker Compose 環境の構築を開始する前に、以下の点を確認し、潜在的な問題を未然に防ぐことを推奨します。

### 0.1. ディスク容量の確認

特にモデルのダウンロードとキャッシュのために、十分なディスク容量があることを確認してください。`intfloat/multilingual-e5-large` モデルは約 2.24GB のサイズがあり、Docker イメージのビルドプロセス中に一時的にさらに多くの容量を消費する可能性があります。

CPU 版に切り替えることで、`torch` 関連のライブラリサイズは劇的に削減されます（数 GB → 数百 MB）。`.dockerignore` により、ビルドコンテキストも数 KB に抑えられます。これにより、ビルド時の一次的なディスク使用量は、サンドボックス環境の制限内に収まる可能性が非常に高いです。

ただし、モデル自体のサイズ（約 2.24GB）が、環境に残された「最後の関門」となります。Dockerfile 内でダウンロードすると、イメージレイヤーがこの分だけ肥大化します。ボリュームマウントでホストにキャッシュする戦略は正しいですが、ビルドの初回実行時にはこのダウンロードが発生し、一時領域を消費します。これが許容範囲内に収まるかが鍵となります。

*   **Linux/macOS**: `df -h .` コマンドで現在のディレクトリが属するファイルシステムの空き容量を確認できます。
*   **Windows**: エクスプローラーでドライブのプロパティを確認するか、PowerShell で `Get-WmiObject Win32_LogicalDisk | Format-Table DeviceID,Size,Freespace` を実行します。

### 0.2. ポートの可用性

Docker Compose で起動するサービスが使用するポートが、ホストマシンで既に他のアプリケーションによって使用されていないことを確認してください。

*   **PostgreSQL**: デフォルトで `5432` 番ポートを使用します。
*   **MCPサーバー**: デフォルトで `8000` 番ポートを使用します。

ポートの使用状況は、以下のコマンドで確認できます。

*   **Linux/macOS**: `sudo lsof -i :5432` または `sudo netstat -tulnp | grep 5432`
*   **Windows (PowerShell)**: `Get-NetTCPConnection -LocalPort 5432`

### 0.3. Python 環境の確認 (任意)

ローカルで開発やテストを行う場合、Dockerfile で指定されている Python バージョン (3.11) と、`pyproject.toml` に記載されている依存関係が、ローカル環境でも適切に動作するかを事前に確認しておくと、デバッグが容易になります。

---

## 1. ディレクトリ構成

最終的なディレクトリ構成は以下のようになります。

```
.
├── .dockerignore # Dockerビルドから不要なファイルを除外
├── .env # 環境変数の定義（Git管理外）
├── .env.sample # 環境変数のサンプル
├── docker-compose.yml # 基本的なサービス構成を定義
├── Dockerfile # CPU版の基本イメージをビルド
├── data/ # ホスト側に配置するデータ（マウントして利用）
│   └── source/
│       └── ...
└── src/ # アプリケーションソースコード
    ├── cli.py
    └── ...```

## 2. .dockerignore ファイル

ビルドコンテキストを最小化し、ビルド速度の向上とイメージサイズの削減を図るために、このファイルを作成します。

```
# Git
.git
.gitignore

# Python
__pycache__/
*.pyc
.venv/

# IDE / Editor
.idea/
.vscode/

# データとキャッシュ（ホストからマウントするためイメージに含めない）
data/
.cache/

# 環境変数ファイル
.env
.env.sample

# その他
Dockerfile
docker-compose.yml
*.log
docs/
```

## 3. Dockerfile (CPU版)

CPU 環境での動作を基本とし、軽量なイメージを作成します。

```dockerfile
# ベースイメージ
FROM python:3.11-slim

# 環境変数
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# sentence-transformersのキャッシュディレクトリをコンテナ内に指定
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/torch/sentence_transformers

WORKDIR /app

# uvをインストール
RUN pip install uv

# 依存関係ファイルをコピー
COPY pyproject.toml ./

# 依存関係をインストール（CPU版torchが自動で入る）
# このレイヤーをキャッシュさせることで、ソースコード変更時に再インストールが走らない
RUN uv pip install --system --no-cache --requirement pyproject.toml

# モデルの事前ダウンロード
# この処理も独立したレイヤーにすることで、毎回ダウンロードするのを防ぐ
# embedding_generator.py のみに依存するため、先にコピーしてキャッシュ効率を高める
COPY src/embedding_generator.py ./src/embedding_generator.py
RUN python -c "from src.embedding_generator import EmbeddingGenerator; EmbeddingGenerator()"

# アプリケーションソースコードをコピー
COPY src/ ./src/

# ポート公開
EXPOSE 8000

# サーバー起動
CMD ["python", "-m", "src.cli", "runserver", "--host", "0.0.0.0"]
```

**補足:**

*   `pyproject.toml` に `torch` を明記しないことで、`sentence-transformers` が CPU 版の `torch` を依存としてインストールします。これにより、イメージサイズを大幅に削減できます。
*   モデルのキャッシュ場所を `ENV` で明示的に指定し、後述の `docker-compose.yml` でホストと共有できるようにします。
*   モデルダウンロードのステップは、ソースコードに依存しない独立した処理であるべきです。`embedding_generator.py` のみを先にコピーしてモデルダウンロードを実行することで、`embedding_generator.py` 自体に変更がない限り、ソースコードの他の部分を変更してもモデルダウンロードのレイヤーはキャッシュが利用され、より最適化されたキャッシュ効率を実現します。

## 4. docker-compose.yml ファイル

サービスの定義と設定の管理を行います。

```yaml
version: '3.8'

services:
  # PostgreSQL (pgvector) データベース
  postgres:
    image: ankane/pgvector
    container_name: mcp_rag_postgres
    env_file: .env
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  # MCPサーバー (CPU版)
  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mcp_rag_server
    ports:
      - "8000:8000"
    volumes:
      # ホストのデータをコンテナの/app/dataにマウント
      - ./data:/app/data
      # ホストのキャッシュをコンテナのキャッシュディレクトリにマウント
      # これにより、モデルをホスト側に永続化できる
      - ./.cache:/app/.cache
    env_file: .env
    depends_on:
      - postgres
    restart: unless-stopped
    # GPU を利用する場合は、下の "mcp-server-gpu" サービスを利用します

  # ドキュメントのインデックスを作成するためのワンショットコンテナ
  indexer:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mcp_rag_indexer
    volumes:
      - ./data:/app/data
      - ./.cache:/app/.cache
    env_file: .env
    depends_on:
      - postgres
    # サーバーは起動せず、インデックス作成コマンドを実行して終了
    command: python -m src.cli index

volumes:
  postgres_data:
```

**補足:**

*   **ボリュームマウント**:
    *   `./data:/app/data`: ホストの `data` ディレクトリをコンテナ内にマウントし、インデックス作成時にホスト側のファイルを読み込めるようにします。
    *   `./.cache:/app/.cache`: Dockerfile でダウンロードしたモデルキャッシュをホスト側に永続化します。これにより、コンテナを再作成してもモデルを再ダウンロードする必要がなくなります。
*   **`indexer` サービス**: インデックス作成を、サーバー起動とは別の `indexer` サービスとして定義しています。これにより、関心の分離が図られ、サーバーを起動せずにインデックス作成だけを実行できます。将来的に、新しいデータを追加した際に `docker compose run --rm indexer` というコマンド一つでインデックス更新のジョブを CI/CD パイプラインに組み込むことが容易になります。また、インデックス作成で問題が発生した場合、サーバーログと分離して問題を確認できるため、デバッグが容易になります。

## 5. GPU 対応の方針

GPU を利用したい場合は、`docker-compose.override.yml` のようなファイルで設定を上書きするのがクリーンな方法です。この方針により、CPU 版と GPU 版の構成をクリーンに分離し、宣言的に管理することが完全に可能であり、GPU 対応という要件は間違いなく満たされます。

### Dockerfile.gpu の作成

GPU 版は NVIDIA の CUDA ランタイムを含むイメージをベースにし、CUDA に対応した `torch` をインストールします。

```dockerfile
# GPU版はNVIDIAのCUDAランタイムを含むイメージをベースにする
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Python等の環境をセットアップ
RUN apt-get update && apt-get install -y python3.11 python3-pip

# 依存関係ファイルをコピー
COPY pyproject.toml ./

# 依存関係のインストール時に、CUDAに対応したtorchをインストールする
# この部分は uv pip install torch --extra-index-url https://download.pytorch.org/whl/cu121 のように
# 明示的にCUDAバージョンを指定する必要がある
RUN uv pip install --system --no-cache --requirement pyproject.toml torch --extra-index-url https://download.pytorch.org/whl/cu121

# モデルの事前ダウンロード
COPY src/embedding_generator.py ./src/embedding_generator.py
RUN python -c "from src.embedding_generator import EmbeddingGenerator; EmbeddingGenerator()"

# アプリケーションソースコードをコピー
COPY src/ ./src/

# ポート公開
EXPOSE 8000

# サーバー起動
CMD ["python", "-m", "src.cli", "runserver", "--host", "0.0.0.0"]```

### docker-compose.override.yml の作成

`docker-compose.override.yml` を作成し、CPU 版のサービス名を上書きして GPU 版の Dockerfile を指定します。

```yaml
services:
  mcp-server: # CPU版のサービス名を上書き
    build:
      context: .
      dockerfile: Dockerfile.gpu # GPU版のDockerfileを指定
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### 実行方法

*   **CPU 版**: `docker compose up`
*   **GPU 版**: `docker compose -f docker-compose.yml -f docker-compose.override.yml up`

この方法により、基本の `docker-compose.yml` を汚すことなく、環境に応じた設定の切り替えが可能になります。

---

## 6. 実装手順

このセクションでは、上記で定義した Docker Compose 環境を実際に構築し、運用するための具体的な手順を詳述します。

### 6.1. 前提条件

*   **Docker Desktop または Docker Engine のインストール**: お使いの OS（Linux, macOS, Windows）に応じた Docker 環境がインストールされていることを確認してください。GPU 版を利用する場合は、NVIDIA Docker (nvidia-container-toolkit) のセットアップも必要です。

### 6.2. 環境変数の設定

`.env.sample` を参考に、プロジェクトルートに `.env` ファイルを作成し、必要な環境変数を設定します。特にデータベース接続情報やモデル名などを適切に設定してください。

```bash
cp .env.sample .env
# .env ファイルをエディタで開き、内容を編集する
```

### 6.3. Docker イメージのビルド

プロジェクトルートディレクトリで以下のコマンドを実行し、Docker イメージをビルドします。初回は依存関係のインストールやモデルのダウンロードに時間がかかります。

```bash
docker compose build
```

### 6.4. サービスの起動

ビルドが完了したら、以下のコマンドでサービスを起動します。`mcp-server` と `postgres` が起動します。

```bash
docker compose up -d
```

*   `-d` オプションはバックグラウンドでサービスを起動します。ログを確認したい場合は `-d` なしで実行してください。

### 6.5. 初期データのインデックス作成

`data/source/markdown/` ディレクトリに配置した Markdown ファイルをデータベースにインデックス化します。これはワンショットのコマンドとして実行します。

```bash
docker compose run --rm indexer
```

*   `--rm` オプションはコンテナの実行終了後に自動的にコンテナを削除します。
*   このコマンドは、サーバーを起動せずにインデックス作成だけを実行します。新しいデータソースを追加した際などに、このコマンドを再実行することでインデックスを更新できます。

### 6.6. 動作確認

`mcp-server` が起動していることを確認し、API エンドポイントにアクセスして動作を検証します。例えば、`http://localhost:8000/docs` にアクセスして FastAPI の Swagger UI が表示されるか確認します。

### 6.7. サービスの停止

サービスを停止し、コンテナを削除するには以下のコマンドを実行します。

```bash
docker compose down
```

*   データベースの永続データを削除したい場合は、`docker compose down -v` を実行してください（注意：データが失われます）。

### 6.8. データベースのクリア (オプション)

開発中やテスト時にデータベースのデータをリセットしたい場合、以下のコマンドでデータベース内のすべてのドキュメントを削除できます。

```bash
docker compose run --rm mcp-server python -m src.cli clear
```

*   このコマンドはデータベースのテーブルをクリアし、再作成します。永続ボリューム自体を削除する場合は `docker compose down -v` を使用してください。

---

## 7. テスト戦略

このセクションでは、構築した Docker Compose 環境におけるテストの実施方法と戦略について説明します。

### 7.1. 単体テスト (Unit Test)

アプリケーションの各モジュールや関数の単体テストは、Docker コンテナ内で実行できます。`pytest` がインストールされていることを前提とします。

```bash
docker compose run --rm mcp-server pytest src/tests/test_embedding_generator.py
# または、すべてのテストを実行する場合
docker compose run --rm mcp-server pytest
```

### 7.2. 結合テスト (Integration Test)

データベースとの連携など、複数のコンポーネントが協調して動作するかのテストです。`mcp-server` サービスが `postgres` サービスに依存しているため、両方が起動している状態でテストを実行します。

```bash
# 結合テスト用のスクリプトがある場合
docker compose run --rm mcp-server python -m pytest tests/test_integration.py
```

### 7.3. システムテスト / E2E テスト

実際にサービスを起動し、外部から API を叩く形式のテストです。これは、アプリケーション全体が期待通りに動作するかを確認するために重要です。

```bash
# サービスを起動
docker compose up -d

# 外部からAPIを叩くテストスクリプトを実行（例: curl, Python requestsなど）
# 例: curl http://localhost:8000/health

# テスト終了後、サービスを停止
docker compose down
```

### 7.4. インデックス作成のテスト

`indexer` サービスを利用して、ドキュメントのインデックス作成が正しく行われるかを確認します。これは、新しいデータソースを追加した際などに特に有用です。

```bash
# 既存のデータをクリアし、再度インデックス作成を行う場合
docker compose down -v # データベースデータを削除
docker compose up -d
docker compose run --rm indexer

# ログを確認して、インデックス作成が成功したか検証
```

### 7.5. CI/CD パイプラインへの組み込み

これらのテストコマンドは、GitHub Actions などの CI/CD パイプラインに容易に組み込むことができます。例えば、プルリクエストが作成された際に自動的に Docker イメージのビルドと単体テスト、結合テストを実行し、デプロイ前に品質を保証するフローを構築できます。

*   `.github/workflows/pytest.yml` や `.github/workflows/ruff.yml` を参考に、Docker 環境でのテスト実行ステップを追加検討してください。
