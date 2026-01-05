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

    def test_favicon_request(self, app, client, monkeypatch):
        """Test favicon.ico request returns 404."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        with app.test_client() as client:
            response = client.get('/favicon.ico')
            assert response.status_code == 404
            assert response.data == b''

    def test_openai_format_detection(self, app, client, mocker, monkeypatch):
        """Test OpenAI format detection and routing."""
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
                                 json={'model': 'gpt-3.5-turbo', 'messages': [{'role': 'user', 'content': 'Hello'}]})
            assert response.status_code == 200
            # Verify Authorization header was set
            mock_requests.assert_called_once()
            call_args = mock_requests.call_args
            headers = call_args[1]['headers']
            assert 'Authorization' in headers
            assert headers['Authorization'] == 'Bearer test_key'

    def test_streaming_disabled(self, app, client, mocker, monkeypatch):
        """Test non-streaming response when streaming is disabled."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.content = b'{"usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1}}'
        mock_response.headers = {'Content-Type': 'application/json'}

        mock_session_request = mocker.patch('app.proxy.session.request')
        mock_requests = mocker.patch('requests.request')
        mock_session_request.return_value = mock_response
        mock_requests.return_value = mock_response

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.return_value = {'id': 1, 'name': 'Test Key', 'key_value': 'test_key'}
        mock_km.get_setting.side_effect = lambda key, default: 'false' if key == 'streaming_enabled' else default

        with app.test_client() as client:
            response = client.post('/v1/models/gemini-pro:streamGenerateContent',
                                 json={'contents': []})
            assert response.status_code == 200

    def test_connection_pooling_disabled(self, app, client, mocker, monkeypatch):
        """Test direct requests when connection pooling is disabled."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.content = b'{"result": "success"}'
        mock_response.headers = {'Content-Type': 'application/json'}

        mock_session_request = mocker.patch('app.proxy.session.request')
        mock_requests = mocker.patch('requests.request')
        mock_requests.return_value = mock_response

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.return_value = {'id': 1, 'name': 'Test Key', 'key_value': 'test_key'}
        mock_km.get_setting.side_effect = lambda key, default: 'false' if key == 'connection_pooling_enabled' else default

        with app.test_client() as client:
            response = client.post('/v1/models/gemini-pro:generateContent',
                                 json={'contents': [{'parts': [{'text': 'Hello'}]}]})
            assert response.status_code == 200
            # Verify session.request was not called, but requests.request was
            mock_session_request.assert_not_called()
            mock_requests.assert_called_once()

    def test_retry_on_503(self, app, client, mocker, monkeypatch):
        """Test retry logic on 503 errors."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_response_503 = mocker.Mock()
        mock_response_503.status_code = 503
        mock_response_503.ok = False
        mock_response_503.content = b'{"error": "Service unavailable"}'

        mock_response_200 = mocker.Mock()
        mock_response_200.status_code = 200
        mock_response_200.ok = True
        mock_response_200.content = b'{"result": "success"}'
        mock_response_200.headers = {'Content-Type': 'application/json'}

        mock_requests = mocker.patch('requests.request')
        mock_requests.side_effect = [mock_response_503, mock_response_200]

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.side_effect = [
            {'id': 1, 'name': 'Test Key 1', 'key_value': 'test_key1'},
            {'id': 2, 'name': 'Test Key 2', 'key_value': 'test_key2'}
        ]

        with app.test_client() as client:
            response = client.post('/v1/models/gemini-pro:generateContent',
                                 json={'contents': [{'parts': [{'text': 'Hello'}]}]})
            assert response.status_code == 200
            # Verify two calls were made (first failed, second succeeded)
            assert mock_requests.call_count == 2

    def test_max_retries_exceeded(self, app, client, mocker, monkeypatch):
        """Test when max retries are exceeded."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_response = mocker.Mock()
        mock_response.status_code = 503
        mock_response.ok = False
        mock_response.content = b'{"error": "Service unavailable"}'

        mock_session_request = mocker.patch('app.proxy.session.request')
        mock_requests = mocker.patch('requests.request')
        mock_session_request.return_value = mock_response
        mock_requests.return_value = mock_response

        mock_km = mocker.patch('app.proxy.key_manager')
        mock_km.get_next_key.return_value = {'id': 1, 'name': 'Test Key', 'key_value': 'test_key'}
        mock_km.get_setting.side_effect = lambda key, default: '0' if key == 'max_retries' else default

        with app.test_client() as client:
            response = client.post('/v1/models/gemini-pro:generateContent',
                                 json={'contents': [{'parts': [{'text': 'Hello'}]}]})
            assert response.status_code == 503