"""
MCP RAG Server Application Factory

このモジュールはFastAPIアプリケーションのインスタンスを作成し、設定します。
"""

import os
import importlib
import logging
from fastapi import FastAPI
from dotenv import load_dotenv

from .mcp_server import get_api_key
from fastapi import Depends
from .rag_tools import router as rag_router
from fastapi_mcp import FastApiMCP

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_app(no_auth: bool = False, additional_modules: list = None) -> FastAPI:
    """
    FastAPIアプリケーションを作成し、設定します。

    Args:
        no_auth (bool, optional): Trueの場合、認証を無効にします。 Defaults to False.
        additional_modules (list, optional): 追加で読み込むツールモジュールのリスト。 Defaults to None.

    Returns:
        FastAPI: 設定済みのFastAPIアプリケーションインスタンス。
    """
    # FastAPIアプリの作成
    app = FastAPI(
        title="MCP RAG Server",
        version="0.2.0",
        description="fastapi-mcpを使用してRAG機能を提供するサーバー",
    )

    # fastapi-mcpのセットアップ
    mcp = FastApiMCP(app)
    mcp.mount()

    # 認証依存関係の設定
    auth_dependencies = []
    if not no_auth and os.environ.get("API_KEY"):
        auth_dependencies.append(Depends(get_api_key))

    # RAGツールのルーターを登録
    app.include_router(rag_router, prefix="/rag", tags=["RAG"], dependencies=auth_dependencies)
    logger.info("RAGツールを登録しました")

    # 追加のツールモジュールを登録
    if additional_modules:
        for module_name in additional_modules:
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "router") and hasattr(module, "prefix") and hasattr(module, "tags"):
                    app.include_router(
                        module.router,
                        prefix=module.prefix,
                        tags=module.tags,
                        dependencies=auth_dependencies
                    )
                    logger.info(f"モジュール '{module_name}' からルーターを登録しました")
                else:
                    logger.warning(f"モジュール '{module_name}' に登録可能なルーターが見つかりません")
            except ImportError as e:
                logger.error(f"モジュール '{module_name}' の読み込みに失敗しました: {e}")

    return app

# このファイルはアプリケーションファクトリを提供します。
# サーバーを起動するには、src/cli.py を使用してください。
