import os
import pytest
from app.config import SECRET_KEY, MIDDLEWARE_PASSWORD, DB_PATH

class TestConfig:
    """Test configuration constants."""

    def test_secret_key_is_bytes(self):
        """Test that SECRET_KEY is generated as bytes."""
        assert isinstance(SECRET_KEY, bytes)
        assert len(SECRET_KEY) == 24

    def test_middleware_password_from_env(self, monkeypatch):
        """Test MIDDLEWARE_PASSWORD reads from environment."""
        monkeypatch.setenv('MIDDLEWARE_PASSWORD', 'test_password')
        # Re-import to get updated value
        from importlib import reload
        import app.config
        reload(app.config)
        assert app.config.MIDDLEWARE_PASSWORD == 'test_password'

    def test_db_path_constant(self):
        """Test DB_PATH is set correctly."""
        assert DB_PATH == 'data/keys.db'