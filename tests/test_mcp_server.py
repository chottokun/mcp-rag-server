import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import os

from src.main import create_app
from src.rag_tools import get_rag_service

# --- 環境変数とモックの設定 ---
os.environ["API_KEY"] = "test-key"
mock_rag_service = MagicMock()

# --- テストクライアントのフィクスチャ ---

@pytest.fixture
def client():
    """認証を有効にしたテスト用のFastAPIクライアントを提供します。"""
    app = create_app(no_auth=False, additional_modules=['src.example_tool'])
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    mock_rag_service.reset_mock()
    return TestClient(app)

@pytest.fixture
def client_no_auth():
    """認証を無効にしたテスト用のFastAPIクライアントを提供します。"""
    app = create_app(no_auth=True, additional_modules=['src.example_tool'])
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    mock_rag_service.reset_mock()
    return TestClient(app)

# --- テストケース ---

def test_auth_required(client):
    """認証が必要なエンドポイントにAPIキーなしでアクセスした場合、403エラーが返されることを確認します。"""
    response = client.get("/rag/documents/count")
    assert response.status_code == 403
    assert response.json() == {"detail": "Could not validate credentials"}

    response = client.post("/example/hello", json={"name": "World"})
    assert response.status_code == 403

def test_auth_with_invalid_key(client):
    """不正なAPIキーでアクセスした場合、403エラーが返されることを確認します。"""
    headers = {"X-API-KEY": "invalid-key"}
    response = client.get("/rag/documents/count", headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Could not validate credentials"}

def test_auth_with_valid_key(client):
    """有効なAPIキーでアクセスした場合、正常にレスポンスが返されることを確認します。"""
    mock_rag_service.get_document_count.return_value = 10
    headers = {"X-API-KEY": "test-key"}

    response = client.get("/rag/documents/count", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"count": 10, "message": "インデックス内のドキュメント数: 10"}

def test_no_auth_server(client_no_auth):
    """認証が無効なサーバーでは、APIキーなしでアクセスできることを確認します。"""
    mock_rag_service.get_document_count.return_value = 5

    response = client_no_auth.get("/rag/documents/count")

    assert response.status_code == 200
    assert response.json()["count"] == 5

def test_mcp_mount(client):
    """fastapi-mcpが正しくマウントされ、MCP用のエンドポイントが利用可能であることを確認します。"""
    response = client.get("/mcp")
    assert response.status_code == 200
    assert "MCP" in response.text
    assert "Tools" in response.text
