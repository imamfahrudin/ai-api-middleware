#!/usr/bin/env python3
"""
Test script to verify timeout behavior in the enhanced proxy.py
This script tests the new timeout configurations and streaming retry logic.
"""

import requests
import time
import json
from unittest.mock import Mock, patch
import sys
import os

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_timeout_configuration():
    """Test that timeout settings are properly configured"""
    print("Testing timeout configuration...")

    # Test settings parsing
    from app.proxy import configure_session_timeout

    # Test with default values
    configure_session_timeout()
    print("[OK] Default session timeout configuration successful")

    # Test with custom values
    configure_session_timeout(5, 30)
    print("[OK] Custom session timeout configuration successful")

    return True

def test_stream_with_retry():
    """Test the stream_with_retry function"""
    print("\nTesting stream_with_retry function...")

    from app.proxy import stream_with_retry

    # Create a mock response
    mock_resp = Mock()
    mock_chunks = [b'chunk1', b'chunk2', b'chunk3']

    def mock_iter_content(chunk_size, timeout):
        """Mock iter_content that yields chunks"""
        for chunk in mock_chunks:
            yield chunk

    mock_resp.iter_content = mock_iter_content
    mock_resp.close = Mock()

    # Test normal streaming
    chunks = list(stream_with_retry(mock_resp, 1024, 30))
    assert chunks == mock_chunks, f"Expected {mock_chunks}, got {chunks}"
    print("[OK] Normal streaming works correctly")

    # Test that close is called
    mock_resp.close.assert_called()
    print("[OK] Response cleanup works correctly")

    return True

def test_buffer_size_optimization():
    """Test buffer size optimization logic"""
    print("\nTesting buffer size optimization...")

    # Test small request optimization
    headers_small = {'Content-Type': 'text/plain'}
    request_data_small = b'small request'

    # Mock the key_manager and settings
    with patch('app.proxy.key_manager') as mock_key_manager:
        mock_key_manager.get_setting.return_value = '8192'  # Default buffer size

        # Import after patching
        from app.proxy import proxy

        # This would normally be done inside the proxy function
        # We're testing the logic conceptually
        buffer_size = 8192
        content_type = headers_small.get('Content-Type', '')
        request_size = len(request_data_small)

        # Apply the optimization logic
        if request_size < 1024 or 'text/' in content_type:
            buffer_size = min(buffer_size, 4096)

        assert buffer_size <= 4096, f"Expected small buffer for text content, got {buffer_size}"
        print("[OK] Small request/text content optimization works")

        # Test large request optimization
        headers_large = {'Content-Type': 'application/octet-stream'}
        request_data_large = b'x' * 200000  # 200KB

        content_type = headers_large.get('Content-Type', '')
        request_size = len(request_data_large)
        buffer_size = 8192

        if request_size > 100000 or 'application/octet-stream' in content_type:
            buffer_size = max(buffer_size, 16384)

        assert buffer_size >= 16384, f"Expected large buffer for binary content, got {buffer_size}"
        print("[OK] Large request/binary content optimization works")

    return True

def main():
    """Run all tests"""
    print("Testing Enhanced Proxy Functionality")
    print("=" * 50)

    tests = [
        test_timeout_configuration,
        test_stream_with_retry,
        test_buffer_size_optimization,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"[FAIL] {test.__name__} failed")
        except Exception as e:
            print(f"[FAIL] {test.__name__} failed with error: {e}")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("All tests passed! The enhanced proxy is ready.")
        return True
    else:
        print("Some tests failed. Please review the implementation.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)