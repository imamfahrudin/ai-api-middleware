import pytest
import os
from flask import json
from app.api_routes import api_bp
from app import auth

class TestApiRoutes:
    """Test API routes blueprint."""

    def test_get_keys(self, app, client, mocker, monkeypatch):
        """Test getting keys."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)  # Bypass auth

        mock_keys = [{'id': 1, 'name': 'Test Key'}]
        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.get_all_keys_with_kpi.return_value = mock_keys

        with app.test_client() as client:
            response = client.get('/middleware/api/keys')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == mock_keys

    def test_get_logs(self, app, client, monkeypatch):
        """Test getting logs."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        with app.test_client() as client:
            response = client.get('/middleware/api/logs')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)

    def test_get_key_details(self, app, client, mocker, monkeypatch):
        """Test getting key details."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_key = {'id': 1, 'name': 'Test Key'}
        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.get_key_details.return_value = mock_key

        with app.test_client() as client:
            response = client.get('/middleware/api/keys/1')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == mock_key

    def test_add_key(self, app, client, mocker, monkeypatch):
        """Test adding a key."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.add_key.return_value = (True, "Key added.")

        with app.test_client() as client:
            response = client.post('/middleware/api/keys',
                                 json={'key_value': 'test_key', 'name': 'Test'})
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['message'] == "Key added."

    def test_update_key(self, app, client, mocker, monkeypatch):
        """Test updating a key."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.update_key.return_value = (True, "Key updated.")

        with app.test_client() as client:
            response = client.put('/middleware/api/keys/1',
                                json={'name': 'Updated Name'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['message'] == "Key updated."

    def test_delete_key(self, app, client, mocker, monkeypatch):
        """Test deleting a key."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.remove_key.return_value = True

        with app.test_client() as client:
            response = client.delete('/middleware/api/keys/1')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] == True

    def test_get_settings(self, app, client, mocker, monkeypatch):
        """Test getting settings."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_settings = {'key': 'value'}
        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.get_all_settings.return_value = mock_settings

        with app.test_client() as client:
            response = client.get('/middleware/api/settings')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == mock_settings

    def test_set_setting(self, app, client, mocker, monkeypatch):
        """Test setting a setting."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.set_setting.return_value = True

        with app.test_client() as client:
            response = client.post('/middleware/api/settings',
                                 json={'key': 'test_key', 'value': 'test_value'})
            assert response.status_code == 200

    def test_get_key_stats(self, app, client, mocker, monkeypatch):
        """Test getting key statistics."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_stats = {'requests': 10, 'success': 8}
        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.get_key_aggregated_stats.return_value = mock_stats

        with app.test_client() as client:
            response = client.get('/middleware/api/keys/1/stats')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == mock_stats

    def test_get_global_stats(self, app, client, mocker, monkeypatch):
        """Test getting global statistics."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_stats = {'total_requests': 100}
        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.get_global_stats.return_value = mock_stats

        with app.test_client() as client:
            response = client.get('/middleware/api/global-stats')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == mock_stats

    def test_bulk_action(self, app, client, mocker, monkeypatch):
        """Test bulk action on keys."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.bulk_update_status.return_value = (True, "Bulk action completed")

        with app.test_client() as client:
            response = client.post('/middleware/api/keys/bulk-action',
                                 json={'action': 'disable', 'key_ids': [1, 2]})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] == True

    def test_export_keys(self, app, client, mocker, monkeypatch):
        """Test exporting keys."""
        monkeypatch.setattr(auth, 'MIDDLEWARE_PASSWORD', None)

        mock_export = [{'id': 1, 'name': 'Key1'}]
        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.get_all_keys_for_export.return_value = mock_export

        with app.test_client() as client:
            response = client.get('/middleware/api/keys/export')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == mock_export

    def test_import_keys(self, app, client, mocker, monkeypatch):
        """Test importing keys."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.bulk_import_keys.return_value = (2, 0, "Import successful")

        with app.test_client() as client:
            response = client.post('/middleware/api/keys/import',
                                 json=[{'name': 'Key1', 'key': 'val1'}])
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] == True

    def test_get_single_setting(self, app, client, mocker, monkeypatch):
        """Test getting a single setting."""
        monkeypatch.setattr('app.config.MIDDLEWARE_PASSWORD', None)

        mock_km = mocker.patch('app.api_routes.key_manager')
        mock_km.get_setting.return_value = 'test_value'

        with app.test_client() as client:
            response = client.get('/middleware/api/settings/test_key')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['value'] == 'test_value'