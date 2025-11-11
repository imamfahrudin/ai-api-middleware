# Tests Directory

This directory contains test scripts for the AI API Middleware application.

## Available Tests

### test_proxy_enhancements.py
Tests the enhanced proxy functionality including:
- Timeout configuration and behavior
- Streaming retry logic with exponential backoff
- Buffer size optimization based on request characteristics
- Resource cleanup and connection management

## Running Tests

### Individual Test Files
```bash
# Run specific test file
python tests/test_proxy_enhancements.py

# Run from project root
python tests/test_proxy_enhancements.py

# Run from tests directory
python test_proxy_enhancements.py
```

### All Tests (Future)
When more test files are added, you can run all tests:
```bash
# Discover and run all tests (if using pytest)
pytest tests/

# Or run individual test files
python tests/test_proxy_enhancements.py
python tests/test_another_feature.py
```

## Test Structure

### Import Path Handling
Tests automatically add the parent directory to Python path to import app modules:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
```

### Mocking Strategy
Tests use unittest.mock to isolate components:
- Mock external API calls
- Mock database connections
- Mock HTTP requests/responses

### Assertion Style
Tests use simple boolean assertions with descriptive success/failure messages.

## Adding New Tests

### File Naming Convention
- Test files should be named `test_<feature_name>.py`
- Example: `test_auth.py`, `test_database.py`, `test_api_routes.py`

### Test Function Naming
- Test functions should be named `test_<specific_behavior>()`
- Example: `test_authentication_success()`, `test_key_rotation_logic()`

### Basic Test Template
```python
#!/usr/bin/env python3
"""
Test script for <feature description>
"""

import sys
import os
from unittest.mock import Mock, patch

# Add parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_feature_name():
    """Test that <specific behavior> works correctly"""
    print("Testing <feature name>...")

    # Test implementation
    # ...

    print("[OK] <specific test> works correctly")
    return True

def main():
    """Run all tests in this file"""
    print("Testing <Feature Name>")
    print("=" * 50)

    tests = [test_feature_name]  # Add all test functions

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

    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
```

## Test Coverage Goals

### Current Coverage
- ✅ Proxy timeout configuration
- ✅ Streaming retry logic
- ✅ Buffer size optimization
- ✅ Resource cleanup

### Planned Coverage
- 🔄 Authentication flows
- 🔄 Database operations
- 🔄 API key management
- 🔄 Error handling
- 🔄 Performance optimizations
- 🔄 Security features

## Test Environment

### Dependencies
Tests use only Python standard library modules:
- `unittest.mock` for mocking
- `sys`, `os` for path handling
- `json` for data serialization
- `time` for timing-related tests

### No External Dependencies
Tests do not require any external test frameworks or internet connectivity.

## Continuous Integration

When setting up CI/CD, tests can be run with:
```bash
# Simple test run
python tests/test_proxy_enhancements.py

# Check exit code
python tests/test_proxy_enhancements.py && echo "Tests passed" || echo "Tests failed"
```

## Troubleshooting

### Import Errors
If you get "No module named 'app'" errors:
1. Ensure you're running from the project root directory
2. Check that the test file has the correct sys.path setup
3. Verify the app directory exists with __init__.py

### Test Failures
1. Check test output for specific error messages
2. Verify that the app modules are being imported correctly
3. Check that any required mock objects are properly configured

### Environment Issues
Tests should run in any Python environment with standard library modules. No virtual environment required.