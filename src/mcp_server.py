"""
MCPサーバー関連のヘルパーモジュール
"""

import os
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

# 環境変数からAPIキーを取得
API_KEY = os.environ.get("API_KEY")
API_KEY_NAME = "X-API-KEY"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key: str = Depends(api_key_header)):
    """
    APIキーを検証するFastAPIの依存関係。
    """
    if not API_KEY:
        # 環境変数にAPI_KEYが設定されていない場合は認証をスキップ
        return
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key
