import os
import uuid
from datetime import datetime, timedelta
import json
import traceback
from flask import Flask, request, redirect, url_for, flash, session, jsonify

# Import MySQL storage instead of JSON storage
from yearplan.mysql_storage import MySQLStorage

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-change-this')
DEBUG_API = os.environ.get('YEARPLAN_DEBUG_API', '0') in {'1', 'true', 'True', 'yes'}

def get_host_link():
    """Get HOST_LINK with intelligent fallback"""
    # Try environment variable first
    host_link = os.environ.get('HOST_LINK')
    
    if host_link:
        return host_link.rstrip('/')
    
    # Fallback: construct from request context if available
    if request:
        try:
            scheme = request.scheme
            host = request.host
            return f"{scheme}://{host}"
        except Exception as e:
            if DEBUG_API:
                print(f"[API] get_host_link request context error: {e}\n{traceback.format_exc()}")
    
    # Final fallback: use BASE_URL or default
    base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
    return base_url.rstrip('/')

def get_paypal_link():
    """Get PayPal donation link from environment"""
    return os.environ.get('PAYPAL_LINK', '#')

# Initialize MySQL storage
storage = MySQLStorage()

@app.before_request
def _log_request():
    if DEBUG_API:
        try:
            print(f"[API] {request.method} {request.path} args={dict(request.args)} form={dict(request.form)}")
        except Exception:
            pass

@app.errorhandler(Exception)
def _handle_exception(e):
    # Centralized error logging to surface root cause instead of silent retries
    print(f"[API] Unhandled exception: {e}\n{traceback.format_exc()}")
    return jsonify({'error': 'Internal Server Error', 'detail': str(e)}), 500

@app.route('/health')
def health():
    try:
        stats = storage.get_stats()
        return jsonify({'status': 'ok', 'db': 'ok', 'stats': stats})
    except Exception as e:
        print(f"[API] /health error: {e}\n{traceback.format_exc()}")
        return jsonify({'status': 'error', 'detail': str(e)}), 500

@app.route('/')
def index():
    # if 'user_email' in session:
    #     user_goals = storage.get_user_goals(session['user_email'])
    #     stats = storage.get_stats()
    #     return jsonify({
    #         'status': 'logged_in',
    #         'user_email': session['user_email'],
    #         'goals': user_goals,
    #         'stats': stats
    #     })
    stats = storage.get_stats()
    return jsonify({
        'status': 'api_running',
        'stats': stats
    })
    return jsonify({
        'status': 'logged_out',
        'message': 'Welcome to YearPlan API',
        'endpoints': {
            'register': 'POST /register',
            'login': 'POST /login',
            'verify': 'GET /verify-email?token=...',
            'dashboard': 'GET /',
            'create_goal': 'POST /create-goal',
            'logout': 'GET /logout'
        }
    })

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return jsonify({'message': 'POST email, password, confirm_password to register'})
    
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    if password != confirm_password:
        return jsonify({'error': 'Passwords do not match'}), 400
    
    # Generate verification token
    verification_token = str(uuid.uuid4())
    token_expires = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Add user to database
    if storage.add_user(email, password, verification_token, token_expires):
        # Get dynamic host link
        host_link = get_host_link()
        verification_link = f"{host_link}/verify-email?token={verification_token}"
        
        # In a real application, you would send this via email
        print(f"Verification link for {email}: {verification_link}")
        
        return jsonify({
            'success': True,
            'message': 'Registration successful! Please check your email for verification.',
            'verification_link': verification_link  # For testing only
        })
    else:
        return jsonify({'error': 'User already exists or registration failed'}), 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return jsonify({'message': 'POST email and password to login'})
    
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    
    user = storage.authenticate_user(email, password)
    if user and user.get('is_verified'):
        session['user_email'] = email
        session['user_id'] = user.get('id')
        return jsonify({
            'success': True,
            'message': 'Login successful!',
            'user_email': email,
            'redirect': '/'
        })
    elif user and not user.get('is_verified'):
        return jsonify({'error': 'Please verify your email before logging in'}), 401
    else:
        return jsonify({'error': 'Invalid email or password'}), 401

@app.route('/verify-email')
def verify_email():
    token = request.args.get('token')
    if not token:
        return jsonify({'error': 'Invalid verification link'}), 400
    
    if storage.verify_user_email(token):
        return jsonify({
            'success': True,
            'message': 'Email verified successfully! You can now log in.'
        })
    else:
        return jsonify({'error': 'Invalid or expired verification token'}), 400

@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    user_goals = storage.get_user_goals(session['user_email'])
    stats = storage.get_stats()
    
    return jsonify({
        'user_email': session['user_email'],
        'goals': user_goals,
        'stats': stats
    })

@app.route('/create-goal', methods=['GET', 'POST'])
def create_goal():
    if 'user_email' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    if request.method == 'GET':
        return jsonify({'message': 'POST title, description, target_date to create goal'})
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    target_date = request.form.get('target_date', '')
    
    if not title:
        return jsonify({'error': 'Goal title is required'}), 400
    
    goal = storage.add_goal(session['user_email'], title, description, target_date)
    if goal:
        return jsonify({
            'success': True,
            'message': 'Goal created successfully!',
            'goal': goal
        })
    else:
        return jsonify({'error': 'Failed to create goal'}), 500

@app.route('/update-goal/<int:goal_id>/<status>')
def update_goal_status(goal_id, status):
    if 'user_email' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    valid_statuses = ['active', 'completed', 'paused', 'cancelled']
    if status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Valid options: {valid_statuses}'}), 400
    
    if storage.update_goal_status(goal_id, status, session['user_email']):
        return jsonify({
            'success': True,
            'message': f'Goal marked as {status}!'
        })
    else:
        return jsonify({'error': 'Failed to update goal'}), 500

@app.route('/logout')
def logout():
    session.clear()
    return jsonify({
        'success': True,
        'message': 'You have been logged out'
    })

@app.route('/donate')
def donate():
    """Redirect to PayPal donation page"""
    paypal_link = get_paypal_link()
    if paypal_link != '#':
        return redirect(paypal_link)
    else:
        return jsonify({'error': 'Donation link not configured'}), 500

@app.route('/stats')
def stats():
    """Show application statistics"""
    stats = storage.get_stats()
    return jsonify(stats)

@app.route('/debug-config')
def debug_config():
    """Debug endpoint to show configuration"""
    return {
        'status': 'ok',
        'MYSQL_HOST': os.environ.get('MYSQL_HOST', 'localhost'),
    }

# Make configuration available to all templates
# @app.context_processor
# def inject_config():
#     """Make configuration available to all templates"""
#     return {
#         'paypal_link': get_paypal_link(),
#         'host_link': get_host_link()
#     }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))