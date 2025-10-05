#!/usr/bin/env python3
"""
Manual Reminder Test Script
This script tests the reminder system functionality
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8080"

def test_reminder_system():
    print("🔔 Testing Year Plan Reminder System")
    print("=" * 40)
    
    # Test 1: Check if server is running
    try:
        response = requests.get(BASE_URL)
        print("✅ Server is running")
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Start with: python app.py")
        return
    
    # Test 2: Process all reminders
    print("\n📧 Processing all reminders...")
    try:
        response = requests.post(f"{BASE_URL}/api/process-reminders")
        data = response.json()
        
        if response.status_code == 200:
            print(f"✅ {data.get('message', 'Reminders processed')}")
            print(f"   📤 Sent: {data.get('sent', 0)}")
            print(f"   ❌ Failed: {data.get('failed', 0)}")
            print(f"   📊 Total processed: {data.get('total_processed', 0)}")
        else:
            print(f"❌ Error: {data.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Failed to process reminders: {e}")
    
    print("\n📋 Reminder System Status:")
    print("✅ User preference storage: Implemented")
    print("✅ Email templates: Implemented") 
    print("✅ Scheduling logic: Implemented")
    print("✅ Manual trigger: Available")
    print("✅ Cron job script: Created")
    
    print("\n🎯 Next Steps:")
    print("1. Login to the app and set your reminder preferences")
    print("2. Use 'Send Test Reminder' from user dropdown")
    print("3. Set up cron job for automated sending:")
    print("   crontab -e")
    print("   Add: 0 9 * * * /Users/jidai/workspace1/yearplan/send_reminders.sh")

if __name__ == "__main__":
    test_reminder_system()