import pytest
from main import app as flask_app
from unittest.mock import patch

@pytest.fixture
def app():
    """Flask app fixture."""
    return flask_app

@pytest.fixture
def client(app):
    """Test client fixture."""
    return app.test_client()

@pytest.fixture
def test_app():
    """Test app fixture for auth tests."""
    from flask import Flask
    app = Flask(__name__)
    app.secret_key = 'test'
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)
    # Mock render_template to return simple HTML
    with patch('app.auth.render_template') as mock_render, \
         patch('app.auth.url_for') as mock_url:
        mock_render.return_value = '<html>Login</html>'
        mock_url.return_value = '/middleware/'
        yield app