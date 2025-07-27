"""
RAGサービスモジュール

ドキュメント処理、エンベディング生成、ベクトルデータベースを統合して、
インデックス化と検索の機能を提供します。
"""

import os
import time
import logging
from typing import List, Dict, Any

from .document_processor import DocumentProcessor
from .embedding_generator import EmbeddingGenerator
from .vector_database import VectorDatabase


class RAGService:
    """
    RAGサービスクラス

    ドキュメント処理、エンベディング生成、ベクトルデータベースを統合して、
    インデックス化と検索の機能を提供します。

    Attributes:
        document_processor: ドキュメント処理クラスのインスタンス
        embedding_generator: エンベディング生成クラスのインスタンス
        vector_database: ベクトルデータベースクラスのインスタンス
        logger: ロガー
    """

    def __init__(
        self, document_processor: DocumentProcessor, embedding_generator: EmbeddingGenerator, vector_database: VectorDatabase
    ):
        """
        RAGServiceのコンストラクタ

        Args:
            document_processor: ドキュメント処理クラスのインスタンス
            embedding_generator: エンベディング生成クラスのインスタンス
            vector_database: ベクトルデータベースクラスのインスタンス
        """
        # ロガーの設定
        self.logger = logging.getLogger("rag_service")
        self.logger.setLevel(logging.INFO)

        # コンポーネントの設定
        self.document_processor = document_processor
        self.embedding_generator = embedding_generator
        self.vector_database = vector_database

        # データベースの初期化
        try:
            self.vector_database.initialize_database()
        except Exception as e:
            self.logger.error(f"データベースの初期化に失敗しました: {str(e)}")
            raise

    def index_document(
        self,
        file_path: str,
        chunks: List[Dict[str, Any]],
    ) -> None:
        """
        ディレクトリ内のファイルをインデックス化します。

        Args:
            source_dir: インデックス化するファイルが含まれるディレクトリのパス
            processed_dir: 処理済みファイルを保存するディレクトリのパス（指定がない場合はdata/processed）
            chunk_size: チャンクサイズ（文字数）
            chunk_overlap: チャンク間のオーバーラップ（文字数）
            incremental: 差分のみをインデックス化するかどうか

        Returns:
            インデックス化の結果
                - document_count: インデックス化されたドキュメント数
                - processing_time: 処理時間（秒）
                - success: 成功したかどうか
                - error: エラーメッセージ（エラーが発生した場合）
        """
        start_time = time.time()
        document_count = 0

        # 処理済みディレクトリのデフォルト値
        if processed_dir is None:
            processed_dir = "data/processed"

        try:
            # ディレクトリ内のファイルを処理
            if incremental:
                self.logger.info(f"ディレクトリ '{source_dir}' 内の差分ファイルをインデックス化しています...")
            else:
                self.logger.info(f"ディレクトリ '{source_dir}' 内のファイルをインデックス化しています...")

            chunks = self.document_processor.process_directory(
                source_dir, processed_dir, chunk_size, chunk_overlap, incremental
            )

            if not chunks:
                self.logger.warning(f"ディレクトリ '{source_dir}' 内に処理可能なファイルが見つかりませんでした")
                return {
                    "document_count": 0,
                    "processing_time": time.time() - start_time,
                    "success": True,
                    "message": f"ディレクトリ '{source_dir}' 内に処理可能なファイルが見つかりませんでした",
                }

            # チャンクのコンテンツからエンベディングを生成
            self.logger.info(f"{len(chunks)} チャンクのエンベディングを生成しています...")
            texts = [chunk["content"] for chunk in chunks]
            embeddings = self.embedding_generator.generate_embeddings(texts)

            # ドキュメントをデータベースに挿入
            self.logger.info(f"{len(chunks)} チャンクをデータベースに挿入しています...")
            documents = []
            for i, chunk in enumerate(chunks):
                documents.append(
                    {
                        "document_id": chunk["document_id"],
                        "content": chunk["content"],
                        "file_path": chunk["file_path"],
                        "chunk_index": chunk["chunk_index"],
                        "embedding": embeddings[i],
                        "metadata": {
                            "file_name": os.path.basename(chunk["file_path"]),
                            "directory": os.path.dirname(chunk["file_path"]),
                            "original_file_path": chunk.get("original_file_path", ""),
                            "directory_suffix": chunk.get("metadata", {}).get("directory_suffix", ""),
                        },
                    }
                )

            self.vector_database.batch_insert_documents(documents)
            document_count = len(documents)

            processing_time = time.time() - start_time
            self.logger.info(f"インデックス化が完了しました（{document_count} ドキュメント、{processing_time:.2f} 秒）")

            return {
                "document_count": document_count,
                "processing_time": processing_time,
                "success": True,
                "message": f"{document_count} ドキュメントをインデックス化しました",
            }

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"インデックス化中にエラーが発生しました: {str(e)}")

            return {"document_count": document_count, "processing_time": processing_time, "success": False, "error": str(e)}

    def search(
        self, query: str, limit: int = 5, with_context: bool = False, context_size: int = 1, full_document: bool = False
    ) -> List[Dict[str, Any]]:
        """
        ベクトル検索を行います。

        Args:
            query: 検索クエリ
            limit: 返す結果の数（デフォルト: 5）
            with_context: 前後のチャンクも取得するかどうか（デフォルト: False）
            context_size: 前後に取得するチャンク数（デフォルト: 1）
            full_document: ドキュメント全体を取得するかどうか（デフォルト: False）

        Returns:
            検索結果のリスト（関連度順）
                - document_id: ドキュメントID
                - content: コンテンツ
                - file_path: ファイルパス
                - similarity: 類似度
                - metadata: メタデータ
                - is_context: コンテキストチャンクかどうか（前後のチャンクの場合はTrue）
                - is_full_document: 全文ドキュメントかどうか（ドキュメント全体の場合はTrue）
        """
        try:
            # クエリからエンベディングを生成
            self.logger.info(f"クエリ '{query}' のエンベディングを生成しています...")
            query_embedding = self.embedding_generator.generate_search_embedding(query)

            # ベクトル検索
            self.logger.info(f"クエリ '{query}' でベクトル検索を実行しています...")
            results = self.vector_database.search(query_embedding, limit)

            # 前後のチャンクも取得する場合
            if with_context and context_size > 0:
                context_results = []
                processed_files = set()  # 処理済みのファイルとチャンクの組み合わせを記録

                for result in results:
                    file_path = result["file_path"]
                    chunk_index = result["chunk_index"]
                    file_chunk_key = f"{file_path}_{chunk_index}"

                    # 既に処理済みのファイルとチャンクの組み合わせはスキップ
                    if file_chunk_key in processed_files:
                        continue

                    processed_files.add(file_chunk_key)

                    # 前後のチャンクを取得
                    adjacent_chunks = self.vector_database.get_adjacent_chunks(file_path, chunk_index, context_size)
                    context_results.extend(adjacent_chunks)

                # 結果をマージ
                all_results = results.copy()

                # 重複を避けるために、既に結果に含まれているドキュメントIDを記録
                existing_doc_ids = {result["document_id"] for result in all_results}

                # 重複していないコンテキストチャンクのみを追加
                for context in context_results:
                    if context["document_id"] not in existing_doc_ids:
                        all_results.append(context)
                        existing_doc_ids.add(context["document_id"])

                # ファイルパスとチャンクインデックスでソート
                all_results.sort(key=lambda x: (x["file_path"], x["chunk_index"]))

                self.logger.info(f"検索結果（コンテキスト含む）: {len(all_results)} 件")

                # ドキュメント全体を取得する場合
                if full_document:
                    full_doc_results = []
                    processed_files = set()  # 処理済みのファイルを記録

                    # 検索結果に含まれるファイルの全文を取得
                    for result in all_results:
                        file_path = result["file_path"]

                        # 既に処理済みのファイルはスキップ
                        if file_path in processed_files:
                            continue

                        processed_files.add(file_path)

                        # ファイルの全文を取得
                        full_doc_chunks = self.vector_database.get_document_by_file_path(file_path)
                        full_doc_results.extend(full_doc_chunks)

                    # 結果をマージ
                    merged_results = all_results.copy()

                    # 重複を避けるために、既に結果に含まれているドキュメントIDを記録
                    existing_doc_ids = {result["document_id"] for result in merged_results}

                    # 重複していない全文チャンクのみを追加
                    for doc_chunk in full_doc_results:
                        if doc_chunk["document_id"] not in existing_doc_ids:
                            merged_results.append(doc_chunk)
                            existing_doc_ids.add(doc_chunk["document_id"])

                    # ファイルパスとチャンクインデックスでソート
                    merged_results.sort(key=lambda x: (x["file_path"], x["chunk_index"]))

                    self.logger.info(f"検索結果（全文含む）: {len(merged_results)} 件")
                    return merged_results
                else:
                    return all_results
            else:
                # ドキュメント全体を取得する場合
                if full_document:
                    full_doc_results = []
                    processed_files = set()  # 処理済みのファイルを記録

                    # 検索結果に含まれるファイルの全文を取得
                    for result in results:
                        file_path = result["file_path"]

                        # 既に処理済みのファイルはスキップ
                        if file_path in processed_files:
                            continue

                        processed_files.add(file_path)

                        # ファイルの全文を取得
                        full_doc_chunks = self.vector_database.get_document_by_file_path(file_path)
                        full_doc_results.extend(full_doc_chunks)

                    # 結果をマージ
                    merged_results = results.copy()

                    # 重複を避けるために、既に結果に含まれているドキュメントIDを記録
                    existing_doc_ids = {result["document_id"] for result in merged_results}

                    # 重複していない全文チャンクのみを追加
                    for doc_chunk in full_doc_results:
                        if doc_chunk["document_id"] not in existing_doc_ids:
                            merged_results.append(doc_chunk)
                            existing_doc_ids.add(doc_chunk["document_id"])

                    # ファイルパスとチャンクインデックスでソート
                    merged_results.sort(key=lambda x: (x["file_path"], x["chunk_index"]))

                    self.logger.info(f"検索結果（全文含む）: {len(merged_results)} 件")
                    return merged_results
                else:
                    self.logger.info(f"検索結果: {len(results)} 件")
                    return results

        except Exception as e:
            self.logger.error(f"検索中にエラーが発生しました: {str(e)}")
            raise

    def clear_index(self) -> Dict[str, Any]:
        """
        インデックスをクリアします。

        Returns:
            クリアの結果
                - deleted_count: 削除されたドキュメント数
                - success: 成功したかどうか
                - error: エラーメッセージ（エラーが発生した場合）
        """
        try:
            # データベースをクリア
            self.logger.info("インデックスをクリアしています...")
            deleted_count = self.vector_database.clear_database()

            self.logger.info(f"インデックスをクリアしました（{deleted_count} ドキュメントを削除）")
            return {"deleted_count": deleted_count, "success": True, "message": f"{deleted_count} ドキュメントを削除しました"}

        except Exception as e:
            self.logger.error(f"インデックスのクリア中にエラーが発生しました: {str(e)}")

            return {"deleted_count": 0, "success": False, "error": str(e)}

    def get_document_count(self) -> int:
        """
        インデックス内のドキュメント数を取得します。

        Returns:
            ドキュメント数
        """
        try:
            # ドキュメント数を取得
            count = self.vector_database.get_document_count()
            self.logger.info(f"インデックス内のドキュメント数: {count}")
            return count

        except Exception as e:
            self.logger.error(f"ドキュメント数の取得中にエラーが発生しました: {str(e)}")
            raise
