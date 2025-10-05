#!/usr/bin/env python3
"""
Gmail SMTP Test Script
This script helps debug Gmail SMTP connection issues independently.
"""

import smtplib
import getpass
from email.mime.text import MIMEText

def test_gmail_smtp():
    print("🔧 Gmail SMTP Connection Test")
    print("=" * 40)
    
    # Get user input
    email = input("Enter your Gmail address: ").strip()
    print("\n📝 For Gmail, you MUST use an App Password:")
    print("1. Go to myaccount.google.com")
    print("2. Security → 2-Step Verification (enable if needed)")  
    print("3. Security → App passwords")
    print("4. Generate password for 'Mail'")
    print("5. Use that 16-character password below\n")
    
    password = getpass.getpass("Enter your App Password (hidden): ").strip()
    
    # Test different configurations
    configs = [
        {"server": "smtp.gmail.com", "port": 587, "name": "Gmail TLS (Recommended)"},
        {"server": "smtp.gmail.com", "port": 465, "name": "Gmail SSL (Alternative)"},
    ]
    
    for config in configs:
        print(f"\n🔄 Testing {config['name']}...")
        print(f"   Server: {config['server']}:{config['port']}")
        
        try:
            if config['port'] == 587:
                # STARTTLS method
                server = smtplib.SMTP(config['server'], config['port'])
                server.set_debuglevel(1)  # Show SMTP conversation
                print("   Starting TLS...")
                server.starttls()
            else:
                # SSL method  
                server = smtplib.SMTP_SSL(config['server'], config['port'])
                server.set_debuglevel(1)
            
            print("   Attempting login...")
            server.login(email, password)
            
            print("   ✅ SUCCESS! SMTP connection works!")
            print(f"   Use: {config['server']}:{config['port']}")
            
            server.quit()
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"   ❌ Authentication failed: {e}")
            print("   → Check if you're using App Password (not regular password)")
            print("   → Verify 2-Step Verification is enabled")
            
        except smtplib.SMTPConnectError as e:
            print(f"   ❌ Connection failed: {e}")
            print("   → Check internet connection")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n❌ All configurations failed!")
    print("\n🆘 Troubleshooting Steps:")
    print("1. Verify your Gmail address is correct")
    print("2. Ensure 2-Step Verification is enabled on your Google account")
    print("3. Generate a new App Password specifically for 'Mail'")
    print("4. Use the App Password, not your regular Google password")
    print("5. Check if your account has security restrictions")
    print("6. Try signing in to Gmail on a web browser first")
    
    return False

if __name__ == "__main__":
    test_gmail_smtp()