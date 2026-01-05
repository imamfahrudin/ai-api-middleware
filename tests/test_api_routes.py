import pytest
from flask import json
from app.api_routes import api_bp

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