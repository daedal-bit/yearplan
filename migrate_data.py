#!/usr/bin/env python3
"""
Data migration script to fix user separation issues in Year Plan app.
This script will:
1. Fix duplicate user IDs
2. Assign existing goals to users based on creation pattern
3. Clean up the data structure
"""

import json
from pathlib import Path

def migrate_data():
    data_path = Path.home() / ".yearplan.json"
    
    if not data_path.exists():
        print("No data file found")
        return
    
    with open(data_path, 'r') as f:
        data = json.load(f)
    
    print("Before migration:")
    print(f"Goals: {len(data.get('goals', []))}")
    print(f"Users: {len(data.get('users', []))}")
    print(f"Logs: {len(data.get('logs', []))}")
    
    # Fix duplicate user IDs - both users currently have ID 203
    users = data.get('users', [])
    if len(users) >= 2:
        # Assign proper unique IDs
        users[0]['id'] = 1  # First user (jiong)
        users[1]['id'] = 2  # Second user (test)
        
        print(f"Fixed user IDs: {users[0]['name']} -> ID 1, {users[1]['name']} -> ID 2")
    
    # Process goals - assign based on their current user_id or lack thereof
    goals = data.get('goals', [])
    goals_assigned_to_user1 = 0
    goals_assigned_to_user2 = 0
    
    for goal in goals:
        current_user_id = goal.get('user_id')
        
        if current_user_id == 203:
            # This goal belonged to old user 203, need to figure out which user it should go to
            # The goal with id 204 ('ddd') was created after user separation, assign to user 2
            if goal.get('id') == 204:
                goal['user_id'] = 2
                goals_assigned_to_user2 += 1
                print(f"Assigned goal '{goal['text']}' (id: {goal['id']}) to user 2")
            else:
                goal['user_id'] = 1
                goals_assigned_to_user1 += 1
                print(f"Assigned goal '{goal['text']}' (id: {goal['id']}) to user 1")
        elif current_user_id is None or 'user_id' not in goal:
            # Goals without user_id - assign to user 1 (the first user)
            goal['user_id'] = 1
            goals_assigned_to_user1 += 1
            print(f"Assigned goal '{goal['text']}' (id: {goal['id']}) to user 1")
        else:
            print(f"Goal '{goal['text']}' already has user_id: {current_user_id}")
    
    print(f"Total goals assigned to user 1: {goals_assigned_to_user1}")
    print(f"Total goals assigned to user 2: {goals_assigned_to_user2}")
    
    # Save the migrated data
    with open(data_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print("\nAfter migration:")
    user1_goals = [g for g in goals if g.get('user_id') == 1]
    user2_goals = [g for g in goals if g.get('user_id') == 2]
    print(f"User 1 ({users[0]['name'] if users else 'Unknown'}) has {len(user1_goals)} goals")
    print(f"User 2 ({users[1]['name'] if len(users) > 1 else 'Unknown'}) has {len(user2_goals)} goals")
    
    # Verify the results
    print("\nDetailed goal assignments:")
    for goal in goals:
        print(f"  Goal {goal['id']}: '{goal['text']}' -> user_id: {goal.get('user_id')}")
    
    print("\nMigration completed successfully!")

if __name__ == "__main__":
    migrate_data()