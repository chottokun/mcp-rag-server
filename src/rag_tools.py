"""
RAGツールモジュール

MCPサーバーに登録するRAG関連ツールを提供します。
FastAPIルーターを使用してツールを定義します。
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from .rag_service import RAGService
from .embedding_generator import EmbeddingGenerator
from .vector_database import VectorDatabase
from .document_processor import DocumentProcessor

def create_rag_service_from_env() -> RAGService:
    """
    環境変数からRAGサービスを作成します。

    Returns:
        RAGサービスのインスタンス
    """
    # 環境変数から接続情報を取得
    postgres_host = os.environ.get("POSTGRES_HOST", "localhost")
    postgres_port = os.environ.get("POSTGRES_PORT", "5432")
    postgres_user = os.environ.get("POSTGRES_USER", "postgres")
    postgres_password = os.environ.get("POSTGRES_PASSWORD", "password")
    postgres_db = os.environ.get("POSTGRES_DB", "ragdb")

    embedding_model = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")

    # コンポーネントの作成
    document_processor = DocumentProcessor()
    embedding_generator = EmbeddingGenerator(model_name=embedding_model)
    vector_database = VectorDatabase(
        {
            "host": postgres_host,
            "port": postgres_port,
            "user": postgres_user,
            "password": postgres_password,
            "database": postgres_db,
        }
    )

    # RAGサービスの作成
    rag_service = RAGService(document_processor, embedding_generator, vector_database)

    return rag_service

# FastAPIルーターの作成
router = APIRouter()

# --- 依存性注入用の関数 ---

from functools import lru_cache

@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    """
    RAGServiceのインスタンスを提供する依存性関数。
    lru_cacheデコレータにより、この関数はアプリケーションのライフサイクル中に
    一度だけ実行され、RAGServiceのインスタンスがシングルトンとして再利用されます。
    これにより、重いモデルの読み込みが一度で済みます。
    """
    return create_rag_service_from_env()

# --- Pydanticモデルの定義 ---

class SearchInput(BaseModel):
    query: str = Field(..., description="検索クエリ")
    limit: int = Field(5, description="返す結果の数")
    with_context: bool = Field(True, description="前後のチャンクも取得するかどうか")
    context_size: int = Field(1, description="前後に取得するチャンク数")
    full_document: bool = Field(False, description="ドキュメント全体を取得するかどうか")

class SearchResultItem(BaseModel):
    file_path: str
    content: str
    chunk_index: int
    similarity: float
    is_context: bool
    is_full_document: bool

class SearchOutput(BaseModel):
    results: List[SearchResultItem]
    message: str

class DocumentCountOutput(BaseModel):
    count: int
    message: str

# --- APIエンドポイントの定義 ---

@router.post("/search", response_model=SearchOutput, summary="ベクトル検索", description="ベクトル検索を行います")
def search(params: SearchInput, rag_service: RAGService = Depends(get_rag_service)) -> Dict[str, Any]:
    """
    ベクトル検索を行うAPIエンドポイント

    Args:
        params (SearchInput): 検索パラメータ
        rag_service (RAGService): DIによって注入されるRAGサービス

    Returns:
        Dict[str, Any]: 検索結果
    """
    try:
        # ドキュメント数を確認
        doc_count = rag_service.get_document_count()
        if doc_count == 0:
            raise HTTPException(
                status_code=404,
                detail="インデックスにドキュメントが存在しません。CLIコマンド `python -m src.cli index` を使用してドキュメントをインデックス化してください。",
            )

        # 検索を実行
        results = rag_service.search(
            params.query, params.limit, params.with_context, params.context_size, params.full_document
        )

        if not results:
            return {"results": [], "message": f"クエリ '{params.query}' に一致する結果が見つかりませんでした"}

        # Pydanticモデルに準拠した形式で返す
        return {"results": [result for result in results], "message": f"クエリ '{params.query}' の検索結果（{len(results)} 件）"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"検索中にエラーが発生しました: {str(e)}")


@router.get("/documents/count", response_model=DocumentCountOutput, summary="ドキュメント数取得", description="インデックス内のドキュメント数を取得します")
def get_document_count(rag_service: RAGService = Depends(get_rag_service)) -> Dict[str, Any]:
    """
    インデックス内のドキュメント数を取得するAPIエンドポイント

    Args:
        rag_service (RAGService): DIによって注入されるRAGサービス

    Returns:
        Dict[str, Any]: ドキュメント数
    """
    try:
        # ドキュメント数を取得
        count = rag_service.get_document_count()
        return {"count": count, "message": f"インデックス内のドキュメント数: {count}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ドキュメント数の取得中にエラーが発生しました: {str(e)}")

def register_rag_tools(server):
    """
    RAG関連ツール（ルーター）をMCPサーバーに登録します。

    Args:
        server: MCPサーバーのインスタンス
    """
    server.register_router(router, prefix="/rag", tags=["RAG"])
