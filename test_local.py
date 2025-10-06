#!/usr/bin/env python3
"""
Comprehensive test script for YearPlan with MySQL locally
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8080"

def test_endpoint(method, endpoint, data=None, cookies=None, expected_status=200):
    """Test an endpoint and return response"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, cookies=cookies)
        elif method.upper() == 'POST':
            response = requests.post(url, data=data, cookies=cookies)
        
        print(f"{'✓' if response.status_code == expected_status else '✗'} {method} {endpoint} - Status: {response.status_code}")
        
        if response.status_code != expected_status:
            print(f"  Expected: {expected_status}, Got: {response.status_code}")
            if response.text:
                print(f"  Response: {response.text[:200]}...")
        
        return response
    except Exception as e:
        print(f"✗ {method} {endpoint} - Error: {e}")
        return None

def main():
    print("="*60)
    print("YearPlan MySQL Local Testing")
    print("="*60)
    
    # Test 1: Debug Configuration
    print("\n1. Testing Configuration...")
    response = test_endpoint('GET', '/debug-config')
    if response and response.status_code == 200:
        config = response.json()
        print(f"   MySQL Database: {config.get('MYSQL_DATABASE')}")
        print(f"   Host Link: {config.get('HOST_LINK_computed')}")
        print(f"   PayPal Link: {config.get('PAYPAL_LINK')}")
    
    # Test 2: Home Page
    print("\n2. Testing Home Page...")
    test_endpoint('GET', '/')
    
    # Test 3: User Registration
    print("\n3. Testing User Registration...")
    timestamp = int(time.time())
    test_email = f"test{timestamp}@example.com"
    test_password = "testpass123"
    
    reg_data = {
        'email': test_email,
        'password': test_password,
        'confirm_password': test_password
    }
    
    response = test_endpoint('POST', '/register', data=reg_data, expected_status=302)
    
    # Extract verification token from server logs (this is just for testing)
    # In production, this would be sent via email
    
    # Test 4: User Login (should fail - not verified yet)
    print("\n4. Testing Login (before verification)...")
    login_data = {
        'email': test_email,
        'password': test_password
    }
    
    response = test_endpoint('POST', '/login', data=login_data, expected_status=200)
    
    # Test 5: Get a verification token from database
    print("\n5. Getting verification token from database...")
    try:
        import os
        import sys
        sys.path.append('/Users/jidai/workspace1/yearplan')
        
        os.environ['MYSQL_HOST'] = 'localhost'
        os.environ['MYSQL_USER'] = 'yearplan_dev'
        os.environ['MYSQL_PASSWORD'] = 'dev_password_123'
        os.environ['MYSQL_DATABASE'] = 'yearplan_dev'
        
        from yearplan.mysql_storage import MySQLStorage
        storage = MySQLStorage()
        
        with storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT verification_token FROM users WHERE email = %s ORDER BY created_at DESC LIMIT 1", (test_email,))
            result = cursor.fetchone()
            if result:
                verification_token = result[0]
                print(f"   Found verification token: {verification_token[:20]}...")
                
                # Test 6: Email Verification
                print("\n6. Testing Email Verification...")
                response = test_endpoint('GET', f'/verify-email?token={verification_token}', expected_status=302)
                
                # Test 7: Login after verification
                print("\n7. Testing Login (after verification)...")
                response = test_endpoint('POST', '/login', data=login_data, expected_status=302)
                
                if response and response.status_code == 302:
                    # Extract session cookies
                    cookies = response.cookies
                    print(f"   Login successful! Session cookie: {cookies.get('session')[:20] if cookies.get('session') else 'None'}...")
                    
                    # Test 8: Dashboard Access
                    print("\n8. Testing Dashboard Access...")
                    response = test_endpoint('GET', '/dashboard', cookies=cookies)
                    
                    # Test 9: Goal Creation
                    print("\n9. Testing Goal Creation...")
                    goal_data = {
                        'title': f'Test Goal {timestamp}',
                        'description': 'This is a test goal created by the testing script',
                        'target_date': '2025-12-31'
                    }
                    
                    response = test_endpoint('POST', '/create-goal', data=goal_data, cookies=cookies, expected_status=302)
                    
                    # Test 10: Goal Status Update
                    print("\n10. Testing Goal Status Update...")
                    # First, get the goal ID from database
                    with storage.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT id FROM goals WHERE user_email = %s ORDER BY created_at DESC LIMIT 1", (test_email,))
                        result = cursor.fetchone()
                        if result:
                            goal_id = result[0]
                            response = test_endpoint('GET', f'/update-goal/{goal_id}/completed', cookies=cookies, expected_status=302)
                    
                    # Test 11: Database Stats
                    print("\n11. Testing Database Stats...")
                    stats = storage.get_stats()
                    print(f"   Total users: {stats['total_users']}")
                    print(f"   Verified users: {stats['verified_users']}")
                    print(f"   Total goals: {stats['total_goals']}")
                    print(f"   Completed goals: {stats['completed_goals']}")
                    
                    # Test 12: Logout
                    print("\n12. Testing Logout...")
                    response = test_endpoint('GET', '/logout', cookies=cookies, expected_status=302)
                    
            else:
                print("   No verification token found for user")
                
    except Exception as e:
        print(f"   Error accessing database: {e}")
    
    # Test 13: PayPal Donation Redirect
    print("\n13. Testing PayPal Donation Redirect...")
    response = test_endpoint('GET', '/donate', expected_status=302)
    
    print("\n" + "="*60)
    print("Testing Complete!")
    print("="*60)
    
    # Final summary
    print("\nTo manually test the web interface:")
    print(f"1. Open http://localhost:8080 in your browser")
    print(f"2. Register a new account")
    print(f"3. Check the terminal where Flask is running for verification links")
    print(f"4. Click the verification link to verify your email")
    print(f"5. Login and create goals")
    print(f"6. Test updating goal status")
    
    print(f"\nTest user created: {test_email}")
    print(f"Test password: {test_password}")

if __name__ == '__main__':
    main()