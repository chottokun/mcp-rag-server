import pytest
import os
import time
import subprocess
import requests
from requests.exceptions import ConnectionError

# --- テスト設定 ---
HOST = "localhost"
PORT = 8001  # 通常のポートと衝突しないように
BASE_URL = f"http://{HOST}:{PORT}"
API_KEY = "integration-test-key"

# --- ヘルパー関数とフィクスチャ ---

def wait_for_server(url, timeout=30):
    """サーバーが起動するまで待機する"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            requests.get(url, timeout=1)
            return True
        except ConnectionError:
            time.sleep(0.5)
    return False

@pytest.fixture(scope="module")
def setup_test_environment():
    """
    テスト全体のセットアップとクリーンアップを行うフィクスチャ
    - Dockerコンテナの起動
    - テスト用ドキュメントの作成
    - インデックス化の実行
    - MCPサーバーの起動
    """
    # 1. Docker ComposeでPostgreSQLを起動
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    time.sleep(5) # DBが完全に起動するのを待つ

    # 2. テスト用の環境変数を設定
    test_env = os.environ.copy()
    test_env["POSTGRES_PORT"] = "5432" # docker-compose.ymlで公開されているポート
    test_env["API_KEY"] = API_KEY
    test_env["SOURCE_DIR"] = "tests/test_data/source"

    # 3. テスト用のドキュメントを作成
    source_dir = test_env["SOURCE_DIR"]
    os.makedirs(source_dir, exist_ok=True)
    with open(os.path.join(source_dir, "test_doc.md"), "w") as f:
        f.write("# テストドキュメント\n\nこれはインテグレーションテスト用のドキュメントです。fastapi-mcpは素晴らしいライブラリです。")

    # 4. CLIでドキュメントをインデックス化
    cli_process = subprocess.run(
        ["python", "-m", "src.cli", "index"],
        env=test_env,
        capture_output=True, text=True
    )
    assert cli_process.returncode == 0, f"インデックス化に失敗: {cli_process.stderr}"
    assert "インデックス化が完了しました" in cli_process.stdout

    # 5. MCPサーバーをバックグラウンドで起動
    server_process = subprocess.Popen(
        ["python", "-m", "src.main", "--port", str(PORT), "--module", "src.example_tool"],
        env=test_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # サーバーが起動するのを待つ
    assert wait_for_server(f"{BASE_URL}/docs"), "サーバーの起動に失敗しました"

    yield # ここでテストが実行される

    # --- クリーンアップ ---
    server_process.terminate()
    server_process.wait()
    subprocess.run(["docker-compose", "down"], check=True)
    # テスト用ドキュメントのクリーンアップは不要 (gitで管理されていないため)

# --- テストケース ---

@pytest.mark.integration
def test_swagger_ui_accessible(setup_test_environment):
    """Swagger UIが正常に表示されることを確認する"""
    response = requests.get(f"{BASE_URL}/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text

@pytest.mark.integration
def test_mcp_ui_accessible(setup_test_environment):
    """fastapi-mcpのUIが正常に表示されることを確認する"""
    response = requests.get(f"{BASE_URL}/mcp")
    assert response.status_code == 200
    assert "MCP" in response.text

@pytest.mark.integration
def test_authentication(setup_test_environment):
    """APIキー認証が正しく機能することを確認する"""
    # APIキーなし -> 403 Forbidden
    response = requests.get(f"{BASE_URL}/rag/documents/count")
    assert response.status_code == 403

    # 不正なAPIキー -> 403 Forbidden
    headers = {"X-API-KEY": "wrong-key"}
    response = requests.get(f"{BASE_URL}/rag/documents/count", headers=headers)
    assert response.status_code == 403

    # 正しいAPIキー -> 200 OK
    headers = {"X-API-KEY": API_KEY}
    response = requests.get(f"{BASE_URL}/rag/documents/count", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] > 0

@pytest.mark.integration
def test_rag_search(setup_test_environment):
    """RAG検索が正しく機能することを確認する"""
    headers = {"X-API-KEY": API_KEY}
    json_data = {"query": "素晴らしいライブラリ"}

    response = requests.post(f"{BASE_URL}/rag/search", headers=headers, json=json_data)

    assert response.status_code == 200
    data = response.json()
    assert "検索結果" in data["message"]
    assert len(data["results"]) > 0
    # 検索結果に期待されるテキストが含まれているか確認
    assert "fastapi-mcpは素晴らしいライブラリです" in data["results"][0]["content"]

@pytest.mark.integration
def test_example_tool(setup_test_environment):
    """追加モジュールが正しく読み込まれ、機能することを確認する"""
    headers = {"X-API-KEY": API_KEY}
    json_data = {"name": "Integration Test"}

    response = requests.post(f"{BASE_URL}/example/hello", headers=headers, json=json_data)

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Integration Test!"}
