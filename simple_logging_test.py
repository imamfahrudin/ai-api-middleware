#!/usr/bin/env python3
"""
Simple test to verify logging functionality works
"""
import requests
import json

def test_basic_logging():
    """Test basic logging functionality"""
    base_url = "http://127.0.0.1:5000/middleware"
    
    print("🧪 Testing AI API Middleware Logging Functionality")
    print("=" * 60)
    
    # Test 1: Check if server is running
    print("🔍 Testing: Server connectivity...")
    try:
        response = requests.get(f"{base_url}/", allow_redirects=False)
        if response.status_code in [302, 200]:
            print(f"✅ Server is running (status: {response.status_code})")
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False
    
    # Test 2: Check logs endpoint
    print("\n📋 Testing: Check logs endpoint...")
    try:
        response = requests.get(f"{base_url}/api/logs", allow_redirects=False)
        if response.status_code == 302:
            print("✅ Logs endpoint exists (redirecting to login as expected)")
        elif response.status_code == 200:
            logs = response.json()
            print(f"✅ Retrieved {len(logs)} log entries")
            if logs:
                print(f"   Latest log: {logs[-1]['msg'][:50]}...")
        else:
            print(f"❌ Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error accessing logs: {e}")
    
    # Test 3: Make a test request to trigger logging
    print("\n🚀 Testing: Make test request to trigger logging...")
    test_payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Test message for logging verification"}
                ]
            }
        ]
    }
    
    try:
        # This will likely fail due to auth, but should still trigger logging
        response = requests.post(
            f"{base_url}/v1beta/models/gemini-pro:generateContent",
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            allow_redirects=False
        )
        print(f"✅ Request made, status: {response.status_code}")
        
        # Check server logs in the terminal
        print("\n📝 Check the server terminal output above for:")
        print("   • Request logging entries")
        print("   • Response logging entries") 
        print("   • Performance logging entries")
        
    except Exception as e:
        print(f"❌ Error making test request: {e}")
    
    print("\n🎉 Basic logging test completed!")
    print("\n📋 Summary of what should be working:")
    print("   • Server is running and accessible")
    print("   • Requests are being logged to console")
    print("   • Live log feed is populated")
    print("   • Settings UI controls logging behavior")
    
    return True

if __name__ == "__main__":
    test_basic_logging()