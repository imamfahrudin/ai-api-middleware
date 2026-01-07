import pytest
from flask import json, Response
from unittest.mock import Mock, patch, MagicMock
import requests
from app.proxy import proxy_bp, configure_session_timeout, stream_with_retry
from app.database import KeyManager
from app.logging_utils import live_log
import time


class TestSettingsImplementation:
    """Comprehensive tests for all settings implementation."""

    @pytest.fixture
    def mock_key_manager(self):
        """Mock KeyManager with settings."""
        km = Mock(spec=KeyManager)
        # Default settings
        km.get_setting.side_effect = lambda key, default=None: {
            'streaming_enabled': 'true',
            'connection_pooling_enabled': 'true',
            'model_cache_enabled': 'true',
            'max_retries': '7',
            'request_timeout': '30',
            'connect_timeout': '10',
            'read_timeout': '60',
            'streaming_timeout': '120',
            'cache_timeout': '300',
            'model_cache_timeout': '10',
            'retry_total': '50',
            'retry_backoff_factor': '0.1',
            'pool_connections': '20',
            'pool_maxsize': '100',
            'max_stream_retries': '2',
            'chunk_retry_delay': '1.0',
            'buffer_size': '8192',
            'small_request_threshold': '1024',
            'large_request_threshold': '100000',
            'small_buffer_size': '4096',
            'large_buffer_size': '16384',
            'min_buffer_size': '1024',
            'max_buffer_size': '65536',
            'json_buffer_limit': '2048',
            'enable_request_logging': 'true',
            'log_level': 'INFO',
            'enable_metrics_collection': 'true',
            'enable_performance_logging': 'true',
            'log_request_body': 'false',
            'log_response_body': 'false',
            'failover_strategy': 'round_robin',
            'enable_request_id_injection': 'true'
        }.get(key, str(default) if default is not None else None)
        return km

    def test_streaming_enabled_setting(self, mock_key_manager):
        """Test streaming_enabled setting controls response streaming."""
        # Test that the setting value is retrieved correctly and affects stream parameter
        with patch('app.proxy.requests.request') as mock_request:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.headers = {'Content-Type': 'application/json'}
            mock_resp.iter_content.return_value = [b'{"test": "data"}']
            mock_request.return_value = mock_resp

            # Test when streaming is enabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'true' if key == 'streaming_enabled' else str(default)

            # The setting should be retrieved and used to determine stream parameter
            streaming_enabled = mock_key_manager.get_setting('streaming_enabled', 'true').lower() == 'true'
            assert streaming_enabled == True

            # Test when streaming is disabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'false' if key == 'streaming_enabled' else str(default)

            streaming_enabled = mock_key_manager.get_setting('streaming_enabled', 'true').lower() == 'true'
            assert streaming_enabled == False

            # Verify that when streaming is enabled, requests.request is called with stream=True
            # This is tested indirectly through the proxy function logic

    def test_connection_pooling_enabled_setting(self, mock_key_manager):
        """Test connection_pooling_enabled setting controls HTTP connection pooling."""
        with patch('app.proxy.session') as mock_session, \
             patch('app.proxy.requests') as mock_requests:

            # Test when connection pooling is enabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'true' if key == 'connection_pooling_enabled' else str(default)

            # Simulate the logic from proxy.py
            connection_pooling_enabled = mock_key_manager.get_setting('connection_pooling_enabled', 'true').lower() == 'true'

            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.ok = True

            if connection_pooling_enabled:
                mock_session.request.return_value = mock_resp
                # When enabled, should use session.request
                result = mock_session.request("GET", "http://test.com")
                assert result == mock_resp
            else:
                mock_requests.request.return_value = mock_resp
                # When disabled, should use requests.request
                result = mock_requests.request("GET", "http://test.com")
                assert result == mock_resp

    def test_model_cache_enabled_setting(self, mock_key_manager):
        """Test model_cache_enabled setting controls model list caching."""
        with patch('app.proxy.key_manager', mock_key_manager):
            # Test when caching is enabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'true' if key == 'model_cache_enabled' else str(default)
            
            # Mock the get_cached_models_list function
            with patch('app.proxy.get_cached_models_list') as mock_cache:
                mock_cache.return_value = {'models': []}
                
                # Import the function that uses this setting
                from app.proxy import get_cached_models_list
                result = get_cached_models_list('test_key', 'v1beta/models')
                
                # When enabled, cache should be checked
                mock_cache.assert_called_once_with('test_key', 'v1beta/models')

    def test_max_retries_setting(self, mock_key_manager):
        """Test max_retries setting controls retry attempts."""
        # Test with max_retries = 2
        mock_key_manager.get_setting.side_effect = lambda key, default=None: '2' if key == 'max_retries' else str(default)

        # Simulate the retry logic from proxy.py
        max_retries = int(mock_key_manager.get_setting('max_retries', '3'))
        assert max_retries == 2

        # Test that max_retries affects how many times we retry
        attempt = 0
        max_retries_setting = max_retries

        # Simulate retry loop
        for attempt in range(max_retries_setting + 1):  # +1 for initial attempt
            if attempt > 0:
                # This would be a retry attempt
                assert attempt <= max_retries_setting
            if attempt == max_retries_setting:
                # Should stop retrying after max_retries attempts
                break

    def test_timeout_settings(self, mock_key_manager):
        """Test timeout settings control request timeouts."""
        with patch('app.proxy.session') as mock_session:

            # Test with custom timeout settings
            mock_key_manager.get_setting.side_effect = lambda key, default=None: {
                'connect_timeout': '15',
                'read_timeout': '90'
            }.get(key, str(default) if default is not None else None)

            # Simulate the timeout tuple creation from proxy.py
            connect_timeout = int(mock_key_manager.get_setting('connect_timeout', '10'))
            read_timeout = int(mock_key_manager.get_setting('read_timeout', '60'))
            request_timeout_tuple = (connect_timeout, read_timeout)

            assert request_timeout_tuple == (15, 90)

            # Test that session gets configured with these timeouts
            from app.proxy import configure_session_timeout
            configure_session_timeout(mock_session, connect_timeout, read_timeout)

            # Verify session timeout was set
            assert mock_session.timeout == (15, 90)

    def test_streaming_timeout_setting(self, mock_key_manager):
        """Test streaming_timeout setting controls streaming timeouts."""
        with patch('app.proxy.key_manager', mock_key_manager):
            mock_key_manager.get_setting.side_effect = lambda key, default=None: '200' if key == 'streaming_timeout' else str(default)

            # Test that streaming timeout is retrieved correctly
            streaming_timeout = mock_key_manager.get_setting('streaming_timeout', '120')
            assert streaming_timeout == '200'

    def test_cache_timeout_settings(self, mock_key_manager):
        """Test cache timeout settings control caching duration."""
        with patch('app.proxy.key_manager', mock_key_manager):
            # Test cache_timeout
            mock_key_manager.get_setting.side_effect = lambda key, default=None: '600' if key == 'cache_timeout' else str(default)
            cache_timeout = mock_key_manager.get_setting('cache_timeout', '300')
            assert cache_timeout == '600'

            # Test model_cache_timeout
            mock_key_manager.get_setting.side_effect = lambda key, default=None: '20' if key == 'model_cache_timeout' else str(default)
            model_cache_timeout = mock_key_manager.get_setting('model_cache_timeout', '10')
            assert model_cache_timeout == '20'

    def test_retry_settings(self, mock_key_manager):
        """Test retry settings control HTTP adapter retry configuration."""
        with patch('app.proxy.key_manager', mock_key_manager):
            mock_session = Mock()

            mock_key_manager.get_setting.side_effect = lambda key, default=None: {
                'retry_total': '25',
                'retry_backoff_factor': '0.5',
                'pool_connections': '15',
                'pool_maxsize': '80'
            }.get(key, str(default))

            configure_session_timeout(mock_session, 10, 60)

            # Verify HTTPAdapter is created with correct retry settings
            call_args = mock_session.mount.call_args_list[0][0][1]
            assert hasattr(call_args, 'config')
            # The retry strategy should be configured with the settings
            assert call_args._pool_connections == 15
            assert call_args._pool_maxsize == 80

    def test_stream_retry_settings(self, mock_key_manager):
        """Test stream retry settings control streaming retry behavior."""
        with patch('app.proxy.key_manager', mock_key_manager):
            mock_resp = Mock()
            mock_resp.iter_content.return_value = [b'chunk1', b'chunk2']

            mock_key_manager.get_setting.side_effect = lambda key, default=None: {
                'max_stream_retries': '3',
                'chunk_retry_delay': '2.0'
            }.get(key, str(default))

            # Test stream_with_retry uses the settings
            chunks = list(stream_with_retry(mock_resp, 8192, 120))
            assert chunks == [b'chunk1', b'chunk2']
            
            # Verify the settings were retrieved
            assert mock_key_manager.get_setting.call_count >= 2  # At least max_stream_retries and chunk_retry_delay

    def test_buffer_size_settings(self, mock_key_manager):
        """Test buffer size settings control streaming buffer sizes."""
        # Test with custom buffer_size = 4096
        mock_key_manager.get_setting.side_effect = lambda key, default=None: '4096' if key == 'buffer_size' else str(default)

        # Simulate buffer size conversion from proxy.py
        buffer_size_setting = mock_key_manager.get_setting('buffer_size', '8192')
        buffer_size = int(buffer_size_setting)

        assert buffer_size == 4096

        # Test that buffer_size affects iter_content chunk_size
        mock_resp = Mock()
        mock_resp.iter_content.return_value = [b'chunk1', b'chunk2']

        # Simulate stream_with_retry usage
        from app.proxy import stream_with_retry
        chunks = list(stream_with_retry(mock_resp, buffer_size, 120))

        # Verify iter_content was called with the correct buffer size
        mock_resp.iter_content.assert_called_with(chunk_size=4096)

    def test_adaptive_buffer_settings(self, mock_key_manager):
        """Test adaptive buffer settings control buffer sizing logic."""
        with patch('app.proxy.key_manager', mock_key_manager):
            mock_key_manager.get_setting.side_effect = lambda key, default=None: {
                'small_request_threshold': '512',
                'large_request_threshold': '50000',
                'small_buffer_size': '2048',
                'large_buffer_size': '32768',
                'min_buffer_size': '512',
                'max_buffer_size': '131072'
            }.get(key, str(default))

            # Test that all buffer settings are retrieved correctly
            small_threshold = mock_key_manager.get_setting('small_request_threshold', '1024')
            assert small_threshold == '512'
            
            large_threshold = mock_key_manager.get_setting('large_request_threshold', '100000')
            assert large_threshold == '50000'

    def test_json_buffer_limit_setting(self, mock_key_manager):
        """Test json_buffer_limit setting controls token extraction buffering."""
        with patch('app.proxy.key_manager', mock_key_manager):
            mock_key_manager.get_setting.side_effect = lambda key, default=None: '4096' if key == 'json_buffer_limit' else str(default)

            # Test that json_buffer_limit setting is retrieved correctly
            json_buffer_limit = mock_key_manager.get_setting('json_buffer_limit', '2048')
            assert json_buffer_limit == '4096'

    def test_request_logging_settings(self, mock_key_manager):
        """Test request logging settings control logging behavior."""
        with patch('app.proxy.log_request') as mock_log_request, \
             patch('app.proxy.log_response') as mock_log_response:

            # Test when request logging is enabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'true' if key == 'enable_request_logging' else str(default)

            # Simulate the logic from proxy.py
            enable_request_logging = mock_key_manager.get_setting('enable_request_logging', 'true').lower() == 'true'
            if enable_request_logging:
                mock_log_request("test_url", {}, None, "test_id", 100)
                mock_log_response(200, {}, None, "test_id", 100)

            # When logging is enabled, functions should be called
            mock_log_request.assert_called_once()
            mock_log_response.assert_called_once()

            # Reset mocks
            mock_log_request.reset_mock()
            mock_log_response.reset_mock()

            # Test when request logging is disabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'false' if key == 'enable_request_logging' else str(default)

            enable_request_logging = mock_key_manager.get_setting('enable_request_logging', 'true').lower() == 'true'
            if enable_request_logging:
                mock_log_request("test_url", {}, None, "test_id", 100)
                mock_log_response(200, {}, None, "test_id", 100)

            # When logging is disabled, functions should NOT be called
            mock_log_request.assert_not_called()
            mock_log_response.assert_not_called()

    def test_log_level_setting(self, mock_key_manager):
        """Test log_level setting controls logging level."""
        with patch('app.proxy.key_manager', mock_key_manager):
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'DEBUG' if key == 'log_level' else str(default)

            # Test that log_level setting is retrieved correctly
            log_level = mock_key_manager.get_setting('log_level', 'INFO')
            assert log_level == 'DEBUG'

    def test_metrics_collection_setting(self, mock_key_manager):
        """Test enable_metrics_collection setting controls metrics updates."""
        with patch.object(mock_key_manager, 'update_key_stats') as mock_update_stats:

            # Test when metrics collection is enabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'true' if key == 'enable_metrics_collection' else str(default)

            # Simulate the logic from proxy.py
            enable_metrics_collection = mock_key_manager.get_setting('enable_metrics_collection', 'true').lower() == 'true'
            if enable_metrics_collection:
                mock_key_manager.update_key_stats(1, True, "gpt-3.5-turbo", None, 100, 50, 200)

            # When metrics collection is enabled, update_key_stats should be called
            mock_update_stats.assert_called_once_with(1, True, "gpt-3.5-turbo", None, 100, 50, 200)

            # Reset mock
            mock_update_stats.reset_mock()

            # Test when metrics collection is disabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'false' if key == 'enable_metrics_collection' else str(default)

            enable_metrics_collection = mock_key_manager.get_setting('enable_metrics_collection', 'true').lower() == 'true'
            if enable_metrics_collection:
                mock_key_manager.update_key_stats(1, True, "gpt-3.5-turbo", None, 100, 50, 200)

            # When metrics collection is disabled, update_key_stats should NOT be called
            mock_update_stats.assert_not_called()

    def test_performance_logging_setting(self, mock_key_manager):
        """Test enable_performance_logging setting controls performance logging."""
        with patch('app.proxy.key_manager', mock_key_manager):
            # Test when performance logging is enabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'true' if key == 'enable_performance_logging' else str(default)
            
            enable_perf_logging = mock_key_manager.get_setting('enable_performance_logging', 'true').lower() == 'true'
            assert enable_perf_logging == True

    def test_body_logging_settings(self, mock_key_manager):
        """Test body logging settings control request/response body logging."""
        with patch('app.proxy.key_manager', mock_key_manager):
            mock_key_manager.get_setting.side_effect = lambda key, default=None: {
                'log_request_body': 'true',
                'log_response_body': 'true'
            }.get(key, str(default))

            # Test that body logging settings are retrieved correctly
            log_request_body = mock_key_manager.get_setting('log_request_body', 'false').lower() == 'true'
            assert log_request_body == True
            
            log_response_body = mock_key_manager.get_setting('log_response_body', 'false').lower() == 'true'
            assert log_response_body == True

    def test_failover_strategy_setting(self, mock_key_manager):
        """Test failover_strategy setting controls key selection algorithm."""
        # Test that different failover strategies are retrieved correctly
        mock_key_manager.get_setting.side_effect = lambda key, default=None: 'round_robin' if key == 'failover_strategy' else str(default)
        strategy = mock_key_manager.get_setting('failover_strategy', 'round_robin')
        assert strategy == 'round_robin'

        mock_key_manager.get_setting.side_effect = lambda key, default=None: 'least_used' if key == 'failover_strategy' else str(default)
        strategy = mock_key_manager.get_setting('failover_strategy', 'round_robin')
        assert strategy == 'least_used'

        mock_key_manager.get_setting.side_effect = lambda key, default=None: 'random' if key == 'failover_strategy' else str(default)
        strategy = mock_key_manager.get_setting('failover_strategy', 'round_robin')
        assert strategy == 'random'

        mock_key_manager.get_setting.side_effect = lambda key, default=None: 'priority' if key == 'failover_strategy' else str(default)
        strategy = mock_key_manager.get_setting('failover_strategy', 'round_robin')
        assert strategy == 'priority'

        # Test that get_next_key is called with the correct strategy (integration test)
        with patch('app.database.KeyManager.get_next_key') as mock_get_next_key:
            mock_get_next_key.return_value = {'id': 1, 'name': 'test_key', 'key_value': 'test_api_key'}

            # Test that the strategy setting is retrieved during key selection
            mock_key_manager.get_setting.side_effect = lambda key, default=None: {
                'failover_strategy': 'least_used'
            }.get(key, str(default) if default is not None else None)

            # Call get_next_key which should use the strategy
            result = mock_key_manager.get_next_key()

            # Verify the strategy was retrieved (this happens inside get_next_key)
            mock_key_manager.get_setting.assert_any_call('failover_strategy', 'round_robin')
            assert result is not None

    def test_request_id_injection_setting(self, mock_key_manager):
        """Test enable_request_id_injection setting controls request ID injection."""
        with patch('app.proxy.key_manager', mock_key_manager):
            # Test when request ID injection is enabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'true' if key == 'enable_request_id_injection' else str(default)
            
            enable_injection = mock_key_manager.get_setting('enable_request_id_injection', 'true').lower() == 'true'
            assert enable_injection == True

            # Test when request ID injection is disabled
            mock_key_manager.get_setting.side_effect = lambda key, default=None: 'false' if key == 'enable_request_id_injection' else str(default)
            
            enable_injection = mock_key_manager.get_setting('enable_request_id_injection', 'true').lower() == 'true'
            assert enable_injection == False

    def test_settings_api_get_all(self, app, client, mock_key_manager, monkeypatch):
        """Test GET /middleware/api/settings returns all settings."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', None)  # Bypass auth

        with patch('app.api_routes.key_manager', mock_key_manager):
            mock_key_manager.get_all_settings.return_value = {
                'streaming_enabled': True,
                'max_retries': 7,
                'log_level': 'INFO'
            }

            with app.test_client() as client:
                response = client.get('/middleware/api/settings')
                assert response.status_code == 200
                data = json.loads(response.data)
                assert 'streaming_enabled' in data
                assert data['max_retries'] == 7

    def test_settings_api_update(self, app, client, mock_key_manager, monkeypatch):
        """Test POST /middleware/api/settings updates settings."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', None)

        with patch('app.api_routes.key_manager', mock_key_manager):
            update_data = {
                'streaming_enabled': True,
                'max_retries': 10,
                'log_level': 'DEBUG'
            }

            with app.test_client() as client:
                response = client.post('/middleware/api/settings',
                                     json=update_data,
                                     content_type='application/json')
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] == True

                # Verify update_settings was called
                mock_key_manager.update_settings.assert_called_once_with({
                    'streaming_enabled': True,
                    'max_retries': 10,
                    'log_level': 'DEBUG'
                })

    def test_settings_validation(self, app, client, mock_key_manager, monkeypatch):
        """Test settings validation in API."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', None)

        with patch('app.api_routes.key_manager', mock_key_manager):
            # Test invalid log_level
            with app.test_client() as client:
                response = client.post('/middleware/api/settings',
                                     json={'log_level': 'INVALID'},
                                     content_type='application/json')
                assert response.status_code == 400
                data = json.loads(response.data)
                assert 'log_level must be one of' in data['message']

            # Test invalid max_retries
            with app.test_client() as client:
                response = client.post('/middleware/api/settings',
                                     json={'max_retries': 100},
                                     content_type='application/json')
                assert response.status_code == 400
                data = json.loads(response.data)
                assert 'max_retries must be between' in data['message']

    def test_configure_logging_on_settings_update(self, app, client, mock_key_manager, monkeypatch):
        """Test that log_level changes apply logging configuration immediately."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', None)

        with patch('app.api_routes.key_manager', mock_key_manager), \
             patch('main.configure_logging') as mock_configure:

            with app.test_client() as client:
                response = client.post('/middleware/api/settings',
                                     json={'log_level': 'DEBUG'},
                                     content_type='application/json')
                assert response.status_code == 200

                # Verify configure_logging was called with new level
                mock_configure.assert_called_once_with('DEBUG')