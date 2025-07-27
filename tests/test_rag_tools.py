import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.main import create_app
from src.rag_tools import get_rag_service

# --- モックとフィクスチャのセットアップ ---

@pytest.fixture
def client():
    """
    RAGツールのテスト用に、依存性をオーバーライドした
    FastAPI TestClientを提供するフィクスチャ。
    """
    # モックRAGサービス
    mock_rag_service = MagicMock()

    # テスト用のアプリケーションインスタンスを作成
    app = create_app()

    # get_rag_service依存性をモックに差し替える
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service

    # 各テストの前にモックをリセット
    mock_rag_service.reset_mock()

    return TestClient(app), mock_rag_service

# --- テストケース ---

def test_get_document_count_success(client):
    """get_document_countが成功した場合のテスト"""
    test_client, mock_service = client
    mock_service.get_document_count.return_value = 123

    response = test_client.get("/rag/documents/count")

    assert response.status_code == 200
    assert response.json() == {"count": 123, "message": "インデックス内のドキュメント数: 123"}
    mock_service.get_document_count.assert_called_once()

def test_get_document_count_error(client):
    """get_document_countで例外が発生した場合のテスト"""
    test_client, mock_service = client
    mock_service.get_document_count.side_effect = Exception("Database connection failed")

    response = test_client.get("/rag/documents/count")

    assert response.status_code == 500
    assert "Database connection failed" in response.json()["detail"]

def test_search_with_no_documents(client):
    """ドキュメントがインデックスにない場合にsearchを呼び出した場合のテスト"""
    test_client, mock_service = client
    mock_service.get_document_count.return_value = 0

    response = test_client.post("/rag/search", json={"query": "test"})

    assert response.status_code == 404
    assert "インデックスにドキュメントが存在しません" in response.json()["detail"]
    mock_service.search.assert_not_called()

def test_search_success(client):
    """searchが成功した場合のテスト"""
    test_client, mock_service = client
    mock_service.get_document_count.return_value = 1
    mock_results = [
        {"file_path": "/path/to/doc1", "content": "hello world", "chunk_index": 0, "similarity": 0.9, "is_context": False, "is_full_document": False}
    ]
    mock_service.search.return_value = mock_results

    response = test_client.post("/rag/search", json={"query": "hello"})

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["message"] == "クエリ 'hello' の検索結果（1 件）"
    assert len(json_response["results"]) == 1
    assert json_response["results"][0]["content"] == "hello world"

    mock_service.search.assert_called_once_with("hello", 5, True, 1, False)

def test_search_no_results(client):
    """searchで結果が見つからなかった場合のテスト"""
    test_client, mock_service = client
    mock_service.get_document_count.return_value = 1
    mock_service.search.return_value = []

    response = test_client.post("/rag/search", json={"query": "unknown"})

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["message"] == "クエリ 'unknown' に一致する結果が見つかりませんでした"
    assert len(json_response["results"]) == 0

def test_search_with_custom_params(client):
    """searchにカスタムパラメータを指定した場合のテスト"""
    test_client, mock_service = client
    mock_service.get_document_count.return_value = 1
    mock_service.search.return_value = []

    test_client.post("/rag/search", json={
        "query": "custom",
        "limit": 10,
        "with_context": False,
        "context_size": 3,
        "full_document": True
    })

    mock_service.search.assert_called_once_with("custom", 10, False, 3, True)
