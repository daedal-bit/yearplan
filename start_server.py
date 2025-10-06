#!/usr/bin/env python3
"""
Stable YearPlan server for local testing
"""
import os
import sys
from pathlib import Path
import traceback

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment variables for MySQL
os.environ['MYSQL_HOST'] = 'localhost'
os.environ['MYSQL_USER'] = 'yearplan_dev'
os.environ['MYSQL_PASSWORD'] = 'dev_password_123' 
os.environ['MYSQL_DATABASE'] = 'yearplan_dev'
os.environ['HOST_LINK'] = 'http://localhost:8081'
os.environ['FLASK_SECRET_KEY'] = 'dev-secret-key-for-testing'

def main():
    print('='*60)
    print('🚀 YearPlan MySQL Server')
    print('='*60)
    
    # Test MySQL connection first
    try:
        from yearplan.mysql_storage import MySQLStorage
        storage = MySQLStorage()
        stats = storage.get_stats()
        print(f'✅ MySQL connected successfully!')
        print(f'📊 Current stats: {stats.get("total_users", 0)} users, {stats.get("total_goals", 0)} goals')
    except Exception as e:
        print(f'❌ MySQL connection failed: {e}')
        print(traceback.format_exc())
        return 1
    
    # Start Flask server
    try:
        from yearplan.app_mysql import app
        print(f'📍 Server URL: http://localhost:8081')
        print(f'🧪 Open in browser: http://localhost:8081/')
        print(f'⏹️  Stop with: Ctrl+C')
        print('='*60)
        
        print('About to call app.run...')
        app.run(
            host='127.0.0.1',
            port=8081, 
            debug=os.environ.get('YEARPLAN_FLASK_DEBUG', '0') in {'1','true','True','yes'},
            use_reloader=False,
            threaded=False
        )
        print('app.run returned!')
        
    except KeyboardInterrupt:
        print('\n👋 Server stopped by user')
        return 0
    except Exception as e:
        print(f'❌ Server error: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(main())