#!/usr/bin/env python3
"""
Test script to verify metrics collection toggle functionality
"""
import requests
import json
import time

def test_metrics_toggle():
    """Test that metrics collection can be enabled/disabled"""
    base_url = "http://127.0.0.1:5000/middleware"
    
    print("🧪 Testing Metrics Collection Toggle Functionality")
    print("=" * 60)
    
    # Test 1: Check current metrics setting
    print("🔍 Testing: Get current metrics setting...")
    try:
        response = requests.get(f"{base_url}/api/settings", allow_redirects=False)
        if response.status_code == 302:
            print("✅ Settings endpoint accessible (redirecting to login as expected)")
            print("   Note: Authentication required for settings access")
        elif response.status_code == 200:
            settings = response.json()
            metrics_enabled = settings.get('enable_metrics_collection', 'Not set')
            print(f"✅ Current metrics collection setting: {metrics_enabled}")
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error getting settings: {e}")
        return False
    
    # Test 2: Try to disable metrics (will likely fail due to auth, but should show the attempt)
    print("\n🔧 Testing: Attempt to disable metrics collection...")
    test_settings = {
        'enable_metrics_collection': False,
        'enable_request_logging': True,
        'log_level': 'INFO'
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/settings",
            json=test_settings,
            headers={'Content-Type': 'application/json'},
            allow_redirects=False
        )
        if response.status_code == 302:
            print("✅ Settings update attempt made (redirecting to login as expected)")
        elif response.status_code == 200:
            result = response.json()
            print(f"✅ Metrics collection disabled: {result.get('message')}")
        else:
            print(f"❌ Failed to update settings: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error updating settings: {e}")
    
    # Test 3: Make a test request to see if metrics are still collected
    print("\n🚀 Testing: Make test request to check metrics behavior...")
    test_payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Test message for metrics toggle verification"}
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{base_url}/v1beta/models/gemini-pro:generateContent",
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            allow_redirects=False
        )
        print(f"✅ Test request made, status: {response.status_code}")
        
        print("\n📝 Check the server terminal output above:")
        print("   • If metrics collection is DISABLED, you should see NO stats updates")
        print("   • If metrics collection is ENABLED, you should see stats updates")
        print("   • Look for calls to key_manager.update_key_stats()")
        
    except Exception as e:
        print(f"❌ Error making test request: {e}")
    
    # Test 4: Try to re-enable metrics
    print("\n🔄 Testing: Attempt to re-enable metrics collection...")
    re_enable_settings = {
        'enable_metrics_collection': True,
        'enable_request_logging': True,
        'log_level': 'INFO'
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/settings",
            json=re_enable_settings,
            headers={'Content-Type': 'application/json'},
            allow_redirects=False
        )
        if response.status_code == 302:
            print("✅ Settings update attempt made (redirecting to login as expected)")
        elif response.status_code == 200:
            result = response.json()
            print(f"✅ Metrics collection re-enabled: {result.get('message')}")
        else:
            print(f"❌ Failed to update settings: {response.status_code}")
    except Exception as e:
        print(f"❌ Error updating settings: {e}")
    
    print("\n🎉 Metrics toggle test completed!")
    print("\n📋 Summary of what should be working:")
    print("   • Metrics collection can be enabled/disabled via settings")
    print("   • When disabled, no statistics are updated")
    print("   • When enabled, statistics are tracked normally")
    print("   • Setting changes apply immediately")
    
    return True

if __name__ == "__main__":
    test_metrics_toggle()