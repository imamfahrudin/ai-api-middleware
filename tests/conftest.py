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
    import os
    from flask import Flask
    import app.auth as auth
    template_folder = os.path.join(os.path.dirname(__file__), '..', 'app', 'templates')
    app = Flask(__name__, template_folder=template_folder)
    app.root_path = os.path.dirname(template_folder)
    app.secret_key = 'test'
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)
    # Mock url_for
    with patch('flask.url_for') as mock_url:
        mock_url.return_value = '/middleware/'
        yield app