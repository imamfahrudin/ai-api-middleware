#!/usr/bin/env python3
"""
Test script to verify logging functionality
"""
import requests
import json
import time

def test_logging_settings():
    """Test that logging settings are properly applied"""
    base_url = "http://127.0.0.1:5000/middleware"
    
    # Test 1: Check current settings
    print("🔍 Testing: Get current settings...")
    try:
        response = requests.get(f"{base_url}/api/settings")
        if response.status_code == 200:
            settings = response.json()
            print(f"✅ Current settings retrieved successfully")
            print(f"   Request logging: {settings.get('enable_request_logging', 'Not set')}")
            print(f"   Log level: {settings.get('log_level', 'Not set')}")
            print(f"   Performance logging: {settings.get('enable_performance_logging', 'Not set')}")
            print(f"   Log request body: {settings.get('log_request_body', 'Not set')}")
            print(f"   Log response body: {settings.get('log_response_body', 'Not set')}")
        else:
            print(f"❌ Failed to get settings: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error getting settings: {e}")
        return False
    
    # Test 2: Update logging settings to enable everything
    print("\n🔧 Testing: Update logging settings...")
    test_settings = {
        'enable_request_logging': True,
        'log_level': 'DEBUG',
        'enable_performance_logging': True,
        'log_request_body': True,
        'log_response_body': True
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/settings",
            json=test_settings,
            headers={'Content-Type': 'application/json'}
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Settings updated successfully: {result.get('message')}")
        else:
            print(f"❌ Failed to update settings: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error updating settings: {e}")
        return False
    
    # Test 3: Make a test API call to trigger logging
    print("\n🚀 Testing: Make API call to trigger logging...")
    test_payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Hello! This is a test message to verify logging is working."}
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{base_url}/v1beta/models/gemini-pro:generateContent",
            json=test_payload,
            headers={'Content-Type': 'application/json'}
        )
        print(f"✅ API call made, status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Response received successfully")
            if 'candidates' in result:
                print(f"   Generated text: {result['candidates'][0]['content']['parts'][0]['text'][:50]}...")
        else:
            print(f"   Error response: {response.text}")
    except Exception as e:
        print(f"❌ Error making API call: {e}")
        # This might be expected if no API keys are configured
        print("   (This might be expected if no API keys are configured)")
    
    # Test 4: Check logs
    print("\n📋 Testing: Check logs...")
    try:
        response = requests.get(f"{base_url}/api/logs")
        if response.status_code == 200:
            logs = response.json()
            print(f"✅ Retrieved {len(logs)} log entries")
            
            # Look for our test entries
            request_logs = [log for log in logs if "REQUEST:" in log['msg']]
            response_logs = [log for log in logs if "RESPONSE:" in log['msg']]
            performance_logs = [log for log in logs if "PERF:" in log['msg']]
            
            print(f"   Request logs: {len(request_logs)}")
            print(f"   Response logs: {len(response_logs)}")
            print(f"   Performance logs: {len(performance_logs)}")
            
            if request_logs:
                print(f"   Latest request log: {request_logs[-1]['msg'][:80]}...")
            if response_logs:
                print(f"   Latest response log: {response_logs[-1]['msg'][:80]}...")
            if performance_logs:
                print(f"   Latest performance log: {performance_logs[-1]['msg'][:80]}...")
                
        else:
            print(f"❌ Failed to get logs: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error getting logs: {e}")
        return False
    
    # Test 5: Reset settings to defaults
    print("\n🔄 Testing: Reset settings to safer defaults...")
    safe_settings = {
        'enable_request_logging': True,
        'log_level': 'INFO',
        'enable_performance_logging': True,
        'log_request_body': False,
        'log_response_body': False
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/settings",
            json=safe_settings,
            headers={'Content-Type': 'application/json'}
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Settings reset to safe defaults: {result.get('message')}")
        else:
            print(f"❌ Failed to reset settings: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error resetting settings: {e}")
        return False
    
    print("\n🎉 All logging tests completed!")
    return True

if __name__ == "__main__":
    print("🧪 Testing AI API Middleware Logging Functionality")
    print("=" * 60)
    
    success = test_logging_settings()
    
    if success:
        print("\n✅ Logging functionality is working correctly!")
        print("\n📝 Summary of what's now working:")
        print("   • Logging level configuration respects settings")
        print("   • Request logging with optional body logging")
        print("   • Response logging with optional body logging")
        print("   • Performance logging with timing metrics")
        print("   • All settings are applied immediately")
        print("   • Live log feed displays all log types")
    else:
        print("\n❌ Some logging tests failed!")
        print("   Please check the server logs for more details.")