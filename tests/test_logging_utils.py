import pytest
from collections import deque
from app.logging_utils import live_log, add_log_entry, log_request, log_response, log_performance

class TestLoggingUtils:
    """Test logging utilities."""

    def test_live_log_is_deque(self):
        """Test live_log is a deque with maxlen 50."""
        assert isinstance(live_log, deque)
        assert live_log.maxlen == 50

    def test_add_log_entry(self):
        """Test adding log entry."""
        initial_len = len(live_log)
        add_log_entry("Test message", "text-green-400")
        assert len(live_log) == initial_len + 1
        entry = live_log[-1]
        assert "time" in entry
        assert entry["msg"] == "Test message"
        assert entry["color"] == "text-green-400"

    def test_log_request_basic(self, caplog):
        """Test logging request."""
        log_request("GET", "/test")
        assert "GET /test" in caplog.text

    def test_log_request_with_headers(self, caplog):
        """Test logging request with headers."""
        headers = {"Content-Type": "application/json", "Authorization": "secret"}
        log_request("POST", "/api", headers=headers)
        assert "Headers:" in caplog.text
        assert "Content-Type" in caplog.text
        assert "Authorization" not in caplog.text  # Should be filtered

    def test_log_response(self, caplog):
        """Test logging response."""
        log_response(200)
        assert "Response 200" in caplog.text

    def test_log_response_with_headers(self, caplog):
        """Test logging response with headers."""
        headers = {"Content-Type": "application/json", "Set-Cookie": "secret"}
        log_response(200, headers=headers)
        assert "Headers:" in caplog.text
        assert "Content-Type" in caplog.text
        assert "Set-Cookie" not in caplog.text  # Should be filtered

    def test_log_response_with_body(self, caplog):
        """Test logging response with body."""
        body = {"result": "success"}
        log_response(200, body=body)
        assert "Body:" in caplog.text

    def test_log_response_with_large_body(self, caplog):
        """Test logging response with large body gets truncated."""
        body = "x" * 600
        log_response(200, body=body)
        assert "...[truncated]" in caplog.text

    def test_log_performance_fast(self, caplog):
        """Test logging fast performance."""
        log_performance("fast_op", 50)
        assert "text-green-400" in str(live_log[-1])

    def test_log_performance_slow(self, caplog):
        """Test logging slow performance."""
        log_performance("slow_op", 1000)
        assert "text-red-500" in str(live_log[-1])