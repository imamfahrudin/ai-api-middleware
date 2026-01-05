import pytest
from flask import json
from app.proxy import proxy_bp, configure_session_timeout
import requests

class TestProxy:
    """Test proxy blueprint."""

    def test_configure_session_timeout(self, mocker):
        """Test session timeout configuration."""
        mock_session = mocker.Mock()
        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_setting.side_effect = lambda key, default: {
            'retry_total': '5',
            'retry_backoff_factor': '0.2',
            'pool_connections': '10',
            'pool_maxsize': '50'
        }.get(key, default)

        from app.proxy import configure_session_timeout
        configure_session_timeout(mock_session, 5, 30)

        # Assert that mount was called for http and https
        assert mock_session.mount.call_count == 2
        mock_session.mount.assert_any_call("http://", mocker.ANY)
        mock_session.mount.assert_any_call("https://", mocker.ANY)

        # Assert timeout was set
        assert mock_session.timeout == (5, 30)

    def test_proxy_request_gemini(self, app, client, mocker, monkeypatch):
        """Test proxying Gemini request."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.content = b'{"result": "success"}'
        mock_response.headers = {'Content-Type': 'application/json'}

        mock_requests = mocker.patch('requests.request')
        mock_requests.return_value = mock_response

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.return_value = {'id': 1, 'name': 'Test Key', 'key_value': 'test_key'}

        with app.test_client() as client:
            response = client.post('/v1/models/gemini-pro:generateContent',
                                 json={'contents': [{'parts': [{'text': 'Hello'}]}]})
            assert response.status_code == 200

    def test_proxy_request_openai(self, app, client, mocker, monkeypatch):
        """Test proxying OpenAI request."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.content = b'{"choices": [{"message": {"content": "Hi"}}]}'
        mock_response.headers = {'Content-Type': 'application/json'}

        mock_requests = mocker.patch('requests.request')
        mock_requests.return_value = mock_response

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.return_value = {'id': 1, 'name': 'Test Key', 'key_value': 'test_key'}

        with app.test_client() as client:
            response = client.post('/v1/chat/completions',
                                 json={'messages': [{'role': 'user', 'content': 'Hello'}]})
            assert response.status_code == 200

    def test_invalid_provider(self, app, client, monkeypatch):
        """Test invalid provider detection."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        with app.test_client() as client:
            response = client.post('/invalid/provider',
                                 json={'test': 'data'})
            assert response.status_code == 503  # No healthy keys available
            data = json.loads(response.data)
            assert 'error' in data

    def test_missing_api_key(self, app, client, mocker, monkeypatch):
        """Test handling missing API key."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.return_value = None

        with app.test_client() as client:
            response = client.post('/v1/models/gemini-pro:generateContent',
                                 json={'contents': []})
            assert response.status_code == 503
            data = json.loads(response.data)
            assert 'No healthy API keys available' in data['error']

    def test_streaming_response(self, app, client, mocker, monkeypatch):
        """Test streaming response handling."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.content = b'{"usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1}}'
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.iter_content.return_value = [b'chunk1', b'chunk2']

        mock_requests = mocker.patch('requests.request')
        mock_requests.return_value = mock_response

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.return_value = {'id': 1, 'name': 'Test Key', 'key_value': 'test_key'}

        with app.test_client() as client:
            response = client.post('/v1/models/gemini-pro:streamGenerateContent',
                                 json={'contents': []})
            assert response.status_code == 200

    def test_error_handling(self, app, client, mocker, monkeypatch):
        """Test error handling in proxy."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_requests = mocker.patch('requests.request')
        mock_requests.side_effect = requests.exceptions.RequestException("Network error")

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.return_value = {'id': 1, 'name': 'Test Key', 'key_value': 'test_key'}

        with app.test_client() as client:
            response = client.post('/v1/models/gemini-pro:generateContent',
                                 json={'contents': []})
            assert response.status_code == 502
            data = json.loads(response.data)
            assert 'error' in data