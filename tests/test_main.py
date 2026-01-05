import pytest
from main import app, configure_logging
import logging

class TestMain:
    """Test main application setup."""

    def test_app_creation(self):
        """Test Flask app is created."""
        assert app is not None
        assert app.name == 'main'

    def test_dashboard_route_requires_login(self, client, monkeypatch):
        """Test dashboard requires login."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', 'test_pass')
        response = client.get('/middleware/')
        assert response.status_code == 302  # Redirect to login

    def test_settings_route_requires_login(self, client, monkeypatch):
        """Test settings requires login."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', 'test_pass')
        response = client.get('/middleware/settings')
        assert response.status_code == 302

    def test_keys_route_requires_login(self, client, monkeypatch):
        """Test keys requires login."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', 'test_pass')
        response = client.get('/middleware/keys')
        assert response.status_code == 302

    def test_logs_route_requires_login(self, client, monkeypatch):
        """Test logs requires login."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', 'test_pass')
        response = client.get('/middleware/logs')
        assert response.status_code == 302

    def test_swagger_config(self):
        """Test Swagger is configured."""
        # Swagger is added to the app, check if the swagger route exists
        with app.test_client() as client:
            response = client.get('/middleware/swagger/')
            assert response.status_code == 200