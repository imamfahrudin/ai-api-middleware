import pytest
from flask import Flask
from app.auth import login_required, auth_bp

@pytest.fixture
def test_app():
    """Create a test app."""
    app = Flask(__name__)
    app.secret_key = 'test'
    app.register_blueprint(auth_bp)
    return app

class TestAuth:
    """Test authentication blueprint."""

    def test_login_required_no_password(self, test_app):
        """Test login_required bypasses when no password set."""
        from app import config
        original_password = config.MIDDLEWARE_PASSWORD
        config.MIDDLEWARE_PASSWORD = None

        @test_app.route('/test')
        @login_required
        def test_route():
            return 'success'

        with test_app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 200
            assert b'success' in response.data

        config.MIDDLEWARE_PASSWORD = original_password

    def test_login_required_with_password_not_logged_in(self, test_app, monkeypatch):
        """Test login_required redirects when password set and not logged in."""
        monkeypatch.setattr('app.auth.MIDDLEWARE_PASSWORD', 'test_pass')

        @test_app.route('/test')
        @login_required
        def test_route():
            return 'success'

        with test_app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 302  # Redirect to login