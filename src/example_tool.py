"""
追加のツールモジュールのサンプル

このモジュールは、MCPサーバーに追加のツールを登録する方法を示します。
FastAPIのAPIRouterとして定義します。
"""

from fastapi import APIRouter
from pydantic import BaseModel

# FastAPIルーターと、ルーターを登録するための情報を定義
router = APIRouter()
prefix = "/example"
tags = ["Example"]

class HelloInput(BaseModel):
    name: str

class HelloOutput(BaseModel):
    message: str

@router.post("/hello", response_model=HelloOutput)
def hello(params: HelloInput):
    """
    挨拶を返すシンプルなツール
    """
    return {"message": f"Hello, {params.name}!"}

# register_tools関数は下位互換性のために残してもよいが、
# create_appではrouter, prefix, tagsを直接参照する
#
# def register_tools(app):
#     """
#     このモジュールのツールをFastAPIアプリに登録します。
#     """
#     app.include_router(router, prefix="/example", tags=["Example"])
