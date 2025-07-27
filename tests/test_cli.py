import pytest
from unittest.mock import patch, MagicMock
import os
from click.testing import CliRunner

from src.cli import main as cli_main

@pytest.fixture
def runner():
    """Clickのテストランナーを提供します。"""
    return CliRunner()

@patch('src.cli.uvicorn')
def test_runserver_command(mock_uvicorn, runner):
    """'runserver' コマンドが正しい引数でuvicornを呼び出すことを確認する。"""
    result = runner.invoke(cli_main, ['runserver', '--host', '127.0.0.1', '--port', '8888', '--no-auth', '--module', 'src.example_tool'])
    assert result.exit_code == 0

    # uvicorn.runが呼び出されたことを確認
    mock_uvicorn.run.assert_called_once()

    # 呼び出しの引数を取得
    call_args, call_kwargs = mock_uvicorn.run.call_args

    # FastAPIアプリケーションインスタンスが渡されていることを確認
    assert 'fastapi.applications.FastAPI' in str(type(call_args[0]))

    # ホストとポートが正しく渡されていることを確認
    assert call_kwargs['host'] == '127.0.0.1'
    assert call_kwargs['port'] == 8888


@patch('src.cli.create_rag_service_from_env')
@patch('src.cli.DocumentProcessor')
def test_index_documents_success(MockDocumentProcessor, mock_create_rag_service, runner):
    """'index' コマンドが成功する場合のテスト。"""
    # モックの設定
    mock_rag_service = MagicMock()
    mock_create_rag_service.return_value = mock_rag_service

    mock_doc_processor = MagicMock()
    MockDocumentProcessor.return_value = mock_doc_processor
    mock_doc_processor.process_file.return_value = [
        {"id": "chunk1", "content": "This is a test chunk."},
    ]

    with runner.isolated_filesystem():
        source_dir = 'test_source'
        os.makedirs(source_dir)
        with open(os.path.join(source_dir, 'test1.txt'), 'w') as f:
            f.write('test file 1')

        result = runner.invoke(cli_main, ['index', '--source-dir', source_dir])

        assert result.exit_code == 0
        assert "ドキュメントのインデックス化を開始します..." in result.output
        assert "合計ファイル数: 1" in result.output

        mock_create_rag_service.assert_called_once()
        mock_rag_service.index_document.assert_called_once()


def test_index_documents_source_dir_not_found(runner):
    """ソースディレクトリが存在しない場合のテスト。"""
    with patch('src.cli.create_rag_service_from_env') as mock_create_service:
        result = runner.invoke(cli_main, ['index', '--source-dir', 'non_existent_dir'])

        assert result.exit_code == 0
        assert "ソースディレクトリが見つかりません: non_existent_dir" in result.output
        mock_create_service.assert_not_called()
