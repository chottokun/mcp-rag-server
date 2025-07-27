"""
コマンドラインインターフェース（CLI）

ドキュメントのインデックス化やサーバーの起動タスクを提供します。
"""

import os
import argparse
import logging
import uvicorn
from dotenv import load_dotenv

from .rag_tools import create_rag_service_from_env
from .document_processor import DocumentProcessor
from .main import create_app

# ロギングの設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cli")

def main():
    """
    CLIのメイン関数
    """
    # .envファイルから環境変数を読み込む
    load_dotenv()

    parser = argparse.ArgumentParser(description="MCP RAG Server CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- indexコマンド ---
    index_parser = subparsers.add_parser("index", help="ソースディレクトリからドキュメントをインデックス化します")
    index_parser.add_argument(
        "--source-dir",
        default=os.environ.get("SOURCE_DIR", "data/source"),
        help="ドキュメントソースディレクトリ"
    )
    index_parser.add_argument(
        "--processed-dir",
        default=os.environ.get("PROCESSED_DIR", "data/processed"),
        help="処理済みドキュメントを保存するディレクトリ"
    )

    # --- runserverコマンド ---
    run_parser = subparsers.add_parser("runserver", help="MCPサーバーを起動します")
    run_parser.add_argument("--host", default="0.0.0.0", help="ホスト")
    run_parser.add_argument("--port", type=int, default=8000, help="ポート")
    run_parser.add_argument("--no-auth", action="store_true", help="APIキー認証を無効にする")
    run_parser.add_argument("--module", action="append", help="追加のツールモジュール（例: src.example_tool）")

    args = parser.parse_args()

    if args.command == "index":
        index_documents(args.source_dir, args.processed_dir)
    elif args.command == "runserver":
        # ディレクトリの作成
        os.makedirs("logs", exist_ok=True)
        os.makedirs(os.environ.get("SOURCE_DIR", "data/source"), exist_ok=True)
        os.makedirs(os.environ.get("PROCESSED_DIR", "data/processed"), exist_ok=True)

        # アプリケーションを作成
        app = create_app(no_auth=args.no_auth, additional_modules=args.module)

        # uvicornでサーバーを起動
        uvicorn.run(app, host=args.host, port=args.port)


def index_documents(source_dir: str, processed_dir: str):
    """
    指定されたディレクトリのドキュメントを処理し、ベクトルデータベースにインデックス化します。

    Args:
        source_dir (str): ドキュメントソースディレクトリ
        processed_dir (str): 処理済みドキュメントを保存するディレクトリ
    """
    logger.info("ドキュメントのインデックス化を開始します...")
    logger.info(f"ソースディレクトリ: {source_dir}")
    logger.info(f"処理済みディレクトリ: {processed_dir}")

    try:
        # ディレクトリの存在確認
        if not os.path.isdir(source_dir):
            logger.error(f"ソースディレクトリが見つかりません: {source_dir}")
            return

        # RAGサービスとDocumentProcessorのインスタンスを作成
        rag_service = create_rag_service_from_env()
        document_processor = DocumentProcessor()

        # 既存のインデックスをクリア
        logger.info("既存のインデックスをクリアしています...")
        # rag_service.vector_database.clear_all_data() # ToDo: 引数でクリアするかどうか選べるようにする
        logger.info("インデックスのクリア処理はスキップされました（実装保留）")

        # ドキュメントの処理とインデックス化
        total_files = 0
        total_chunks = 0
        for root, _, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    logger.info(f"'{file_path}' を処理中...")
                    # ドキュメントをチャンクに分割
                    chunks = document_processor.process_file(file_path)
                    if not chunks:
                        logger.warning(f"'{file_path}' からチャンクが生成されませんでした。")
                        continue

                    # チャンクをインデックス化
                    rag_service.index_document(file_path, chunks)
                    logger.info(f"'{file_path}' をインデックス化しました（{len(chunks)} チャンク）")
                    total_files += 1
                    total_chunks += len(chunks)

                except Exception as e:
                    logger.error(f"'{file_path}' の処理中にエラーが発生しました: {e}", exc_info=True)

        logger.info("すべてのドキュメントのインデックス化が完了しました。")
        logger.info(f"合計ファイル数: {total_files}")
        logger.info(f"合計チャンク数: {total_chunks}")

    except Exception as e:
        logger.error(f"インデックス化プロセス全体でエラーが発生しました: {e}", exc_info=True)

if __name__ == "__main__":
    main()
