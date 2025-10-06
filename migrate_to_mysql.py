#!/usr/bin/env python3
"""
Migration script to convert JSON data to MySQL database
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yearplan.mysql_storage import MySQLStorage

def migrate_json_to_mysql(json_file_path=None):
    """Migrate data from JSON file to MySQL database"""
    
    if json_file_path is None:
        json_file_path = Path.home() / '.yearplan.json'
    
    print(f"Starting migration from {json_file_path}")
    
    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        print(f"JSON file not found: {json_file_path}")
        print("Starting with empty database")
        return True
    
    # Load JSON data
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return False
    
    # Initialize MySQL storage
    try:
        storage = MySQLStorage()
        print("Connected to MySQL database")
    except Exception as e:
        print(f"Error connecting to MySQL: {e}")
        return False
    
    # Migrate users
    users = data.get('users', [])
    users_migrated = 0
    users_failed = 0
    
    print(f"Migrating {len(users)} users...")
    
    for user in users:
        try:
            email = user.get('email', '').strip().lower()
            password = user.get('password', '')
            verification_token = user.get('verification_token', '')
            token_expires = user.get('token_expires', '')
            is_verified = user.get('is_verified', False)
            
            if not email or not password:
                print(f"Skipping user with missing email or password")
                users_failed += 1
                continue
            
            # Add user to MySQL
            success = storage.add_user(email, password, verification_token, token_expires)
            
            if success and is_verified:
                # If user was already verified, update the database
                storage.verify_user_email(verification_token)
            
            if success:
                users_migrated += 1
                print(f"✓ Migrated user: {email}")
            else:
                users_failed += 1
                print(f"✗ Failed to migrate user: {email} (might already exist)")
                
        except Exception as e:
            users_failed += 1
            print(f"✗ Error migrating user {user.get('email', 'unknown')}: {e}")
    
    # Migrate goals
    goals = data.get('goals', [])
    goals_migrated = 0
    goals_failed = 0
    
    print(f"Migrating {len(goals)} goals...")
    
    for goal in goals:
        try:
            user_email = goal.get('user_email', '').strip().lower()
            title = goal.get('title', '')
            description = goal.get('description', '')
            target_date = goal.get('target_date', '')
            
            if not user_email or not title:
                print(f"Skipping goal with missing user_email or title")
                goals_failed += 1
                continue
            
            # Add goal to MySQL
            created_goal = storage.add_goal(user_email, title, description, target_date)
            
            if created_goal:
                goals_migrated += 1
                print(f"✓ Migrated goal: {title} for {user_email}")
                
                # Update status if different from default
                goal_status = goal.get('status', 'active')
                if goal_status != 'active':
                    storage.update_goal_status(created_goal['id'], goal_status, user_email)
            else:
                goals_failed += 1
                print(f"✗ Failed to migrate goal: {title} for {user_email}")
                
        except Exception as e:
            goals_failed += 1
            print(f"✗ Error migrating goal {goal.get('title', 'unknown')}: {e}")
    
    # Migration summary
    print("\n" + "="*50)
    print("MIGRATION SUMMARY")
    print("="*50)
    print(f"Users: {users_migrated} migrated, {users_failed} failed")
    print(f"Goals: {goals_migrated} migrated, {goals_failed} failed")
    
    # Show database stats
    stats = storage.get_stats()
    print(f"\nDatabase after migration:")
    print(f"- Total users: {stats.get('total_users', 0)}")
    print(f"- Verified users: {stats.get('verified_users', 0)}")
    print(f"- Total goals: {stats.get('total_goals', 0)}")
    print(f"- Completed goals: {stats.get('completed_goals', 0)}")
    
    return True

if __name__ == '__main__':
    # Get JSON file path from command line argument or use default
    json_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    success = migrate_json_to_mysql(json_path)
    
    if success:
        print("\nMigration completed successfully!")
        exit(0)
    else:
        print("\nMigration failed!")
        exit(1)