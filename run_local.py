#!/usr/bin/env python3
"""
Local development runner for YearPlan with MySQL
"""

import os
import sys
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_dir))

# Load environment variables from .env.local
env_file = project_dir / '.env.local'
if env_file.exists():
    print(f"Loading environment from {env_file}")
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value
                print(f"Set {key} = {value}")

# Import and run the MySQL-based Flask app
from yearplan.app_mysql import app

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Starting YearPlan with MySQL locally")
    print("="*50)
    print(f"MySQL Host: {os.environ.get('MYSQL_HOST')}")
    print(f"MySQL Database: {os.environ.get('MYSQL_DATABASE')}")
    print(f"Host Link: {os.environ.get('HOST_LINK')}")
    print(f"PayPal Link: {os.environ.get('PAYPAL_LINK')}")
    print("="*50)
    print("Access the app at: http://localhost:8080")
    print("Debug config at: http://localhost:8080/debug-config")
    print("="*50)
    
    # Run Flask app
    app.run(
        debug=True,
        host='127.0.0.1',
        port=8080,
        use_reloader=True
    )