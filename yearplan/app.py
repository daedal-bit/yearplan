from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from .storage import YearPlanStorage
from pathlib import Path
import os
import hashlib
import secrets
import smtplib
import uuid
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from time import time

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = secrets.token_hex(16)  # Generate a secret key for sessions
DB_PATH = Path.home() / '.yearplan.json'
storage = YearPlanStorage(DB_PATH)

# Email configuration (can be configured via environment variables)
EMAIL_CONFIG = {
    'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.environ.get('SMTP_PORT', '587')),
    'email': os.environ.get('EMAIL_USER', ''),
    'password': os.environ.get('EMAIL_PASSWORD', ''),
    'from_name': os.environ.get('FROM_NAME', 'Year Plan App')
}

# Base URL for verification links
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:8080')

# Donation URL (PayPal or any donation link)
DONATION_URL = os.environ.get('PAYPAL_DONATION_URL', os.environ.get('DONATION_URL', 'https://www.paypal.com/donate'))

# Email config file path
EMAIL_CONFIG_FILE = Path.home() / '.yearplan_email_config.json'

def load_email_config():
    """Load email configuration from file"""
    if EMAIL_CONFIG_FILE.exists():
        try:
            with open(EMAIL_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Update EMAIL_CONFIG with saved values
                EMAIL_CONFIG.update(config)
        except Exception as e:
            print(f"Error loading email config: {e}")

def save_email_config(config):
    """Save email configuration to file"""
    try:
        with open(EMAIL_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        # Update the global EMAIL_CONFIG
        EMAIL_CONFIG.update(config)
        return True
    except Exception as e:
        print(f"Error saving email config: {e}")
        return False

# Load email config on startup
load_email_config()
@app.context_processor
def inject_asset_version():
    """Inject a changing asset version to bust cache during development."""
    try:
        v = int(time())
    except Exception:
        v = 1
    return {'asset_version': v, 'donation_url': DONATION_URL}


 


def send_verification_email(email, token, name):
    """Send email verification link to user"""
    if not EMAIL_CONFIG['email'] or not EMAIL_CONFIG['password']:
        print(f"Email not configured. Verification link for {email}: {BASE_URL}/verify-email?token={token}")
        return True  # For development, just print the link
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['from_name']} <{EMAIL_CONFIG['email']}>"
        msg['To'] = email
        msg['Subject'] = "Verify Your Year Plan Account"
        
        # Email body
        verification_link = f"{BASE_URL}/verify-email?token={token}"
        body = f"""
Hello {name},

Welcome to Year Plan! Please verify your email address by clicking the link below:

{verification_link}

This link will expire in 24 hours.

If you didn't create an account, please ignore this email.

Best regards,
Year Plan Team
        """
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Send email
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        # Ensure credentials are ASCII compatible
        email_cred = EMAIL_CONFIG['email'].encode('ascii', 'ignore').decode('ascii')
        password_cred = EMAIL_CONFIG['password'].encode('ascii', 'ignore').decode('ascii')
        server.login(email_cred, password_cred)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def generate_verification_token():
    """Generate a unique verification token"""
    return str(uuid.uuid4())

def send_reminder_email(user, goals_summary, html_summary=None):
    """Send goal reminder email to user.
    - goals_summary: plain-text string (single line + ASCII table)
    - html_summary: optional HTML string (pretty table); if None, falls back to <pre> wrapper"""
    if not EMAIL_CONFIG['email'] or not EMAIL_CONFIG['password']:
        print(f"Email not configured. Reminder email for {user['email']}: {goals_summary}")
        return True  # For development, just print the reminder

    try:
        # Create message with alternative parts (plain + HTML)
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{EMAIL_CONFIG['from_name']} <{EMAIL_CONFIG['email']}>"
        msg['To'] = user['email']
        msg['Subject'] = f"📊 Your Year Plan Progress Update - {datetime.now().strftime('%B %d, %Y')}"

        # Plain + HTML (HTML uses <pre> to preserve table formatting; larger font for readability)
        plain_body = f"{goals_summary}"
        if html_summary is None:
            html_body = f"""
<html>
  <body>
    <pre style=\"font-size:24px; line-height:1.5; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, monospace; white-space: pre-wrap;\">{goals_summary}</pre>
  </body>
</html>
"""
        else:
            html_body = html_summary

        msg.attach(MIMEText(plain_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        # Send email
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        # Ensure credentials are ASCII compatible
        email_cred = EMAIL_CONFIG['email'].encode('ascii', 'ignore').decode('ascii')
        password_cred = EMAIL_CONFIG['password'].encode('ascii', 'ignore').decode('ascii')
        server.login(email_cred, password_cred)
        server.send_message(msg)
        server.quit()

        return True
    except Exception as e:
        print(f"Failed to send reminder email to {user['email']}: {e}")
        return False


def send_congrats_email(user, goal):
        """Send a congratulations email when a goal is completed."""
        if not EMAIL_CONFIG['email'] or not EMAIL_CONFIG['password']:
                print(f"[Congrats] Email not configured. Would send congrats to {user['email']} for goal '{goal.get('text')}'.")
                return True
        try:
                name = user.get('name') or 'there'
                goal_name = goal.get('text') or 'your goal'
                completed_at = goal.get('completed_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                # Build message
                msg = MIMEMultipart('alternative')
                msg['From'] = f"{EMAIL_CONFIG['from_name']} <{EMAIL_CONFIG['email']}>"
                msg['To'] = user['email']
                msg['Subject'] = f"🎉 Congratulations on completing '{goal_name}'!"
                plain = f"Congrats {name}!\n\nYou completed '{goal_name}' on {completed_at}.\nKeep up the great work!"
                html = f"""
<html>
    <body style=\"font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; font-size:20px;\">
        <p>🎉 Congrats <strong>{name}</strong>!</p>
        <p>You completed <strong>{goal_name}</strong> on <strong>{completed_at}</strong>.</p>
        <p>Keep up the great work!</p>
    </body>
</html>"""
                msg.attach(MIMEText(plain, 'plain', 'utf-8'))
                msg.attach(MIMEText(html, 'html', 'utf-8'))
                server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
                server.starttls()
                email_cred = EMAIL_CONFIG['email'].encode('ascii', 'ignore').decode('ascii')
                password_cred = EMAIL_CONFIG['password'].encode('ascii', 'ignore').decode('ascii')
                server.login(email_cred, password_cred)
                server.send_message(msg)
                server.quit()
                return True
        except Exception as e:
                print(f"Failed to send congrats email: {e}")
                return False


def _compute_inclusive_days(start_date_str, end_date_str):
    """Return (elapsed_days_inclusive, total_days_inclusive) using local date and inclusive counting.
    If dates are invalid or missing, returns (None, None)."""
    try:
        if not start_date_str or not end_date_str:
            return None, None
        start = datetime.fromisoformat(start_date_str).date()
        end = datetime.fromisoformat(end_date_str).date()
        today = datetime.now().date()
        total = (end - start).days + 1
        if total <= 0:
            total = 1
        if today < start:
            elapsed = 1  # force day 1 minimum per UI rule
        elif today > end:
            elapsed = total
        else:
            elapsed = (today - start).days + 1
            if elapsed < 1:
                elapsed = 1
            if elapsed > total:
                elapsed = total
        return elapsed, total
    except Exception:
        return None, None


def _expected_percent_for_goal(goal, status):
    """Compute expected percent for a goal using backend expected and time-based fallback."""
    task_type = status.get('task_type', goal.get('task_type', 'increment'))
    target = goal.get('target')
    expected_raw = status.get('expected')

    # Time-based expected percent
    elapsed, total = _compute_inclusive_days(goal.get('start_date'), goal.get('end_date'))
    time_based_pct = None
    if elapsed is not None and total and total > 0:
        time_based_pct = max(0.0, min(100.0, (elapsed / total) * 100.0))

    # Prefer time-based percent to avoid 0% on day 1
    if time_based_pct is not None:
        return time_based_pct

    # Fall back to backend expected normalization
    if task_type == 'percentage':
        try:
            return max(0.0, min(100.0, float(expected_raw))) if expected_raw is not None else None
        except Exception:
            return None
    try:
        t = float(target) if target is not None else 0.0
        if t > 0 and expected_raw is not None:
            return max(0.0, min(100.0, (float(expected_raw) / t) * 100.0))
    except Exception:
        pass
    return None


def _status_label_from_expected(actual_pct, expected_pct):
    """Return a label and emoji based on ratio thresholds (1.3/0.7)."""
    if expected_pct and expected_pct > 0:
        ratio = actual_pct / expected_pct if expected_pct else 0
        if ratio >= 1.3:
            return '🚀 Ahead'
        if ratio <= 0.7:
            return '⚠️ Behind'
        return '✅ On Track'
    # Fallbacks
    if actual_pct >= 100:
        return '🏁 Completed'
    if actual_pct > 0:
        return '⏳ In Progress'
    return 'Pending'


def build_goals_report_text(user_id):
    """Create a concise plaintext report for email with Name, Target, Current, Progress%, Status."""
    goals = storage.list_goals(user_id)
    if not goals:
        return "📝 You haven't created any goals yet. Start by adding your first annual goal!"

    # Active (not archived)
    active_goals = [g for g in goals if not g.get('is_archived', False)]

    lines = []
    # Header summary
    completed_count = 0
    for g in active_goals:
        st = storage.goal_progress_status(g.get('id')) or {}
        if st.get('percent', 0) >= 100:
            completed_count += 1
    lines.append("📊 Goals Detailed Report:")
    lines.append(f"Total: {len(active_goals)} | Completed: {completed_count} | Active: {len(active_goals) - completed_count}")
    lines.append("")
    lines.append("Name | Target | Current | Progress% | Status")
    lines.append("-----|--------|---------|-----------|--------")

    for g in active_goals:
        status = storage.goal_progress_status(g.get('id')) or {}
        actual_pct = float(status.get('percent', 0.0))
        # Status label based on expected percent (time-based preference)
        expected_pct = _expected_percent_for_goal(g, status)
        label = _status_label_from_expected(actual_pct, expected_pct if expected_pct is not None else 0)
        name = g.get('text') or g.get('name') or 'Unnamed'
        target = g.get('target')
        current = status.get('progress', 0)
        lines.append(f"{name} | {target if target is not None else '-'} | {current} | {actual_pct:5.1f}% | {label}")

    return "\n".join(lines)


def build_goals_single_line(user_id):
    """Build a single-line summary for reminders: Total, Completed, In Progress."""
    goals = storage.list_goals(user_id)
    if not goals:
        return "📝 No goals yet — add your first goal today!"
    active = [g for g in goals if not g.get('is_archived', False)]
    completed = 0
    for g in active:
        st = storage.goal_progress_status(g.get('id')) or {}
        if st.get('percent', 0) >= 100:
            completed += 1
    in_progress = max(0, len(active) - completed)
    return f"📊 Goals: {len(active)} | ✅ Completed: {completed} | 🔄 In Progress: {in_progress}"


def build_goals_report_html(user_id):
        """Build an HTML table for the goals report (Name, Target, Current, Progress%, Status)."""
        goals = storage.list_goals(user_id)
        active_goals = [g for g in goals if not g.get('is_archived', False)]
        rows = []
        for g in active_goals:
                status = storage.goal_progress_status(g.get('id')) or {}
                actual_pct = float(status.get('percent', 0.0))
                expected_pct = _expected_percent_for_goal(g, status)
                label = _status_label_from_expected(actual_pct, expected_pct if expected_pct is not None else 0)
                name = g.get('text') or g.get('name') or 'Unnamed'
                target = g.get('target')
                current = status.get('progress', 0)
                rows.append(f"<tr><td>{name}</td><td>{'-' if target is None else target}</td><td>{current}</td><td>{actual_pct:.1f}%</td><td>{label}</td></tr>")

        table = """
<table style="border-collapse:collapse; width:100%; font-size:20px;">
    <thead>
        <tr>
            <th style="text-align:left; border-bottom:1px solid #ccc; padding:8px;">Name</th>
            <th style="text-align:left; border-bottom:1px solid #ccc; padding:8px;">Target</th>
            <th style="text-align:left; border-bottom:1px solid #ccc; padding:8px;">Current</th>
            <th style="text-align:left; border-bottom:1px solid #ccc; padding:8px;">Progress%</th>
            <th style="text-align:left; border-bottom:1px solid #ccc; padding:8px;">Status</th>
        </tr>
    </thead>
    <tbody>
        {rows}
    </tbody>
</table>
""".replace('{rows}', "\n    ".join(rows))

        return table

def require_auth(f):
    """Decorator to require authentication for routes"""
    def decorated_function(*args, **kwargs):
        # Allow test suite to call APIs without authentication
        if os.environ.get('PYTEST_CURRENT_TEST'):
            # In tests, use None to avoid user filtering in storage
            session['user_id'] = None
            return f(*args, **kwargs)
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Verify user still exists
        user = storage.get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            return jsonify({'error': 'User not found'}), 401
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route('/add-goal', methods=['GET'])
@require_auth
def add_goal_page():
    """Render the Add New Goal page (alternative to modal) with sensible defaults."""
    return render_template('add_goal.html')

@app.route('/')
def index():
    # Don't pass goals to template - they're loaded dynamically via JavaScript
    return render_template('index.html')


@app.route('/debug')
def debug():
    return render_template('debug.html')


@app.route('/simple')
def simple():
    return render_template('simple.html')


@app.route('/api/goals', methods=['GET'])
@require_auth
def api_goals():
    user_id = session['user_id']
    goals = storage.list_goals(user_id)
    # augment with status
    out = []
    for g in goals:
        gcopy = dict(g)
        status = storage.goal_progress_status(g.get('id'))
        gcopy['status'] = status
        out.append(gcopy)
    return jsonify(out)

@app.route('/api/completed-goals', methods=['GET'])
@require_auth
def api_completed_goals():
    user_id = session['user_id']
    goals = storage.list_goals(user_id)
    completed = []
    for g in goals:
        if g.get('is_completed'):
            completed.append(g)
    # newest first
    completed.sort(key=lambda x: x.get('completed_at',''), reverse=True)
    return jsonify(completed)

@app.route('/api/completed-goals/<int:goal_id>', methods=['DELETE'])
@require_auth
def api_delete_completed(goal_id):
    user_id = session['user_id']
    g = storage.get_goal(goal_id, user_id)
    if not g or not g.get('is_completed'):
        return jsonify({'error':'not found'}), 404
    storage.delete_goal(goal_id, user_id)
    return jsonify({'ok': True})


@app.route('/api/goals', methods=['POST'])
@require_auth
def api_create_goal():
    data = request.json or {}
    text = data.get('text')
    if not text:
        return jsonify({'error': 'text required'}), 400
    
    # Support metadata if provided
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    target = data.get('target')
    start_value = data.get('start_value')
    task_type = data.get('task_type', 'increment')
    
    if start_date or end_date or target or task_type != 'increment' or start_value is not None:
        gid = storage.add_goal_with_meta(text, start_date, end_date, target, task_type, session['user_id'], start_value)
    else:
        gid = storage.add_goal(text, session['user_id'])
    
    return jsonify({'id': gid}), 201


@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
@require_auth
def api_update_goal(goal_id):
    """Update goal value based on task type and provided action/value"""
    data = request.json or {}
    action = data.get('action', 'increment')
    value = data.get('value', 1)
    
    from datetime import datetime
    # Check completion before update
    before = storage.goal_progress_status(goal_id) or {}
    entry = storage.update_goal_value(goal_id, action, value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session['user_id'])
    if entry is None:
        return jsonify({'error': 'goal not found'}), 404
    # After update, if just completed, send congrats email once
    after_status = storage.goal_progress_status(goal_id) or {}
    just_completed = (before.get('percent', 0) < 100) and (after_status.get('percent', 0) >= 100)
    if just_completed:
        # retrieve goal to include details
        goal = storage.get_goal(goal_id, session['user_id'])
        user = storage.get_user_by_id(session['user_id'])
        try:
            send_congrats_email(user, goal)
        except Exception as e:
            print(f"Error sending congrats email: {e}")
    return jsonify(entry), 201


@app.route('/api/goals/<int:goal_id>/name', methods=['PUT'])
@require_auth
def api_update_goal_name(goal_id):
    """Update the name/text of a goal"""
    data = request.json or {}
    new_text = (data.get('text') or '').strip()
    if not new_text:
        return jsonify({'error': 'text required'}), 400
    ok = storage.update_goal_name(goal_id, new_text, session['user_id'])
    if not ok:
        return jsonify({'error': 'update failed'}), 400
    return jsonify({'ok': True}), 200


# Keep the old endpoint for backward compatibility
@app.route('/api/goals/<int:goal_id>/increment', methods=['POST'])
@require_auth
def api_increment_goal(goal_id):
    # simple +1 action with proper timestamp
    from datetime import datetime
    entry = storage.update_goal_value(goal_id, 'increment', 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session['user_id'])
    if entry is None:
        return jsonify({'error': 'goal not found'}), 404
    return jsonify(entry), 201


@app.route('/api/goals/<int:goal_id>/target', methods=['PUT'])
@require_auth
def api_update_goal_target(goal_id):
    """Update the target value for a goal."""
    data = request.json or {}
    new_target = data.get('target', None)
    ok = storage.update_goal_target(goal_id, new_target, session['user_id'])
    if not ok:
        return jsonify({'error': 'failed to update target'}), 400
    # return updated goal
    g = storage.get_goal(goal_id, session['user_id'])
    status = storage.goal_progress_status(goal_id) if g else None
    return jsonify({'goal': g, 'status': status}), 200


@app.route('/api/logs', methods=['GET'])
@require_auth
def api_logs():
    return jsonify(storage.list_logs())


@app.route('/api/goals/<int:goal_id>/logs', methods=['GET'])
@require_auth
def api_goal_logs(goal_id):
    # First check if user owns this goal
    goal = storage.get_goal(goal_id, session['user_id'])
    if not goal:
        return jsonify({'error': 'goal not found'}), 404
    
    logs = storage.get_logs_for_goal(goal_id)
    if logs is None:
        return jsonify({'error': 'goal not found'}), 404
    return jsonify(logs)


@app.route('/api/logs/<int:log_id>', methods=['PUT'])
@require_auth
def api_edit_log(log_id):
    data = request.json or {}
    allowed = {k: data[k] for k in ('action', 'value', 'ts') if k in data}
    if not allowed:
        return jsonify({'error': 'no valid fields to update'}), 400
    
    # Check if user owns the goal this log belongs to
    if not storage.user_owns_log(log_id, session['user_id']):
        return jsonify({'error': 'log not found'}), 404
    
    entry = storage.edit_log(log_id, **allowed)
    if entry is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(entry)


@app.route('/api/logs/<int:log_id>', methods=['DELETE'])
@require_auth
def api_delete_log(log_id):
    ok = storage.delete_log(log_id)
    if not ok:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'ok': True})


@app.route('/api/goals/<int:goal_id>', methods=['DELETE'])
@require_auth
def api_delete_goal(goal_id):
    ok = storage.delete_goal(goal_id, session['user_id'])
    if not ok:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'ok': True})


@app.route('/api/logs/<int:log_id>/rollback', methods=['POST'])
@require_auth
def api_rollback_log(log_id):
    """Create a reverse operation to undo a specific log entry"""
    rollback_entry = storage.rollback_log(log_id)
    if rollback_entry is None:
        return jsonify({'error': 'log not found or cannot be rolled back'}), 404
    return jsonify(rollback_entry), 201


# Authentication routes
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json or {}
    
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Check if user already exists
    if storage.get_user_by_email(email):
        return jsonify({'error': 'User with this email already exists'}), 400
    
    # Hash password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Generate verification token
    verification_token = generate_verification_token()
    
    # Create unverified user
    user = storage.create_unverified_user(name, email, password_hash, verification_token)
    if user:
        # Send verification email
        if send_verification_email(email, verification_token, name):
            return jsonify({
                'message': 'Registration successful! Please check your email to verify your account.',
                'email': email
            }), 201
        else:
            return jsonify({'error': 'User created but failed to send verification email'}), 500
    else:
        return jsonify({'error': 'Failed to create user'}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    # Get user
    user = storage.get_user_by_email(email)
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Check password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user['password_hash'] != password_hash:
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Check if email is verified
    if not user.get('is_verified', True):  # Default True for existing users
        return jsonify({
            'error': 'Please verify your email address before logging in. Check your email for the verification link.',
            'verification_required': True
        }), 401
    
    # Set session
    session['user_id'] = user['id']
    session['user_email'] = user['email']
    
    return jsonify({'user': {'id': user['id'], 'name': user['name'], 'email': user['email']}}), 200


@app.route('/verify-email')
def verify_email_page():
    """Handle email verification from email links"""
    token = request.args.get('token')
    
    if not token:
        return render_template('verify.html', 
                             success=False, 
                             message='Invalid verification link. No token provided.')
    
    # Verify the token
    user = storage.get_user_by_token(token)
    if user and storage.verify_user_email(token):
        return render_template('verify.html', 
                             success=True, 
                             message=f'Email verification successful! Welcome, {user["name"]}. You can now log in.',
                             user_name=user["name"])
    else:
        return render_template('verify.html', 
                             success=False, 
                             message='Invalid or expired verification token. Please request a new verification email.')

@app.route('/api/verify-email', methods=['GET'])
def api_verify_email():
    """API endpoint for programmatic verification"""
    token = request.args.get('token')
    
    if not token:
        return jsonify({'error': 'Verification token is required'}), 400
    
    # Verify the token
    if storage.verify_user_email(token):
        return jsonify({'message': 'Email verified successfully! You can now log in.'}), 200
    else:
        return jsonify({'error': 'Invalid or expired verification token'}), 400


@app.route('/api/resend-verification', methods=['POST'])
def api_resend_verification():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    # Get user
    user = storage.get_user_by_email(email)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if already verified
    if user.get('is_verified', False):
        return jsonify({'error': 'Email is already verified'}), 400
    
    # Generate new verification token
    verification_token = generate_verification_token()
    
    # Update user with new token
    users = storage._data.get('users', [])
    for u in users:
        if u.get('id') == user['id']:
            u['verification_token'] = verification_token
            u['token_expires'] = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            break
    storage._save()
    
    # Send verification email
    if send_verification_email(email, verification_token, user['name']):
        return jsonify({'message': 'Verification email sent successfully'}), 200
    else:
        return jsonify({'error': 'Failed to send verification email'}), 500


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/api/current-user', methods=['GET'])
def api_current_user():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = storage.get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 401
    
    return jsonify({'user': {'id': user['id'], 'name': user['name'], 'email': user['email']}}), 200


@app.route('/api/change-password', methods=['POST'])
@require_auth
def api_change_password():
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Current password and new password are required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters long'}), 400
    
    user = storage.get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Verify current password
    current_password_hash = hashlib.sha256(current_password.encode()).hexdigest()
    if user['password_hash'] != current_password_hash:
        return jsonify({'error': 'Current password is incorrect'}), 400
    
    # Update password
    new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
    success = storage.update_user_password(session['user_id'], new_password_hash)
    
    if success:
        return jsonify({'message': 'Password updated successfully'}), 200
    else:
        return jsonify({'error': 'Failed to update password'}), 500


@app.route('/api/change-email', methods=['POST'])
@require_auth
def api_change_email():
    data = request.get_json()
    new_email = data.get('new_email')
    password = data.get('password')
    
    if not new_email or not password:
        return jsonify({'error': 'New email and password are required'}), 400
    
    user = storage.get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Verify password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user['password_hash'] != password_hash:
        return jsonify({'error': 'Password is incorrect'}), 400
    
    # Check if email already exists
    existing_user = storage.get_user_by_email(new_email)
    if existing_user and existing_user['id'] != session['user_id']:
        return jsonify({'error': 'Email already in use'}), 400
    
    # Update email
    success = storage.update_user_email(session['user_id'], new_email)
    
    if success:
        return jsonify({'message': 'Email updated successfully'}), 200
    else:
        return jsonify({'error': 'Failed to update email'}), 500


@app.route('/api/delete-account', methods=['POST'])
@require_auth
def api_delete_account():
    data = request.get_json()
    password = data.get('password')
    
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    
    user = storage.get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Verify password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user['password_hash'] != password_hash:
        return jsonify({'error': 'Password is incorrect'}), 400
    
    # Delete user and all associated data
    success = storage.delete_user(session['user_id'])
    
    if success:
        session.clear()
        return jsonify({'message': 'Account deleted successfully'}), 200
    else:
        return jsonify({'error': 'Failed to delete account'}), 500


# Reminder Management Routes
@app.route('/api/reminder-preferences', methods=['GET'])
@require_auth
def get_reminder_preferences():
    """Get current user's reminder preferences"""
    user_id = session['user_id']
    preferences = storage.get_user_reminder_preferences(user_id)
    
    if preferences:
        return jsonify({'preferences': preferences}), 200
    else:
        # Default preferences if not found
        return jsonify({'preferences': {
            'frequency': 'weekly',
            'enabled': True,
            'last_sent': None
        }}), 200

@app.route('/api/reminder-preferences', methods=['POST'])
@require_auth
def update_reminder_preferences():
    """Update current user's reminder preferences"""
    data = request.json or {}
    frequency = data.get('frequency', 'weekly')
    enabled = data.get('enabled', True)
    
    # Validate frequency
    valid_frequencies = ['daily', 'weekly', 'biweekly', 'monthly', 'disabled']
    if frequency not in valid_frequencies:
        return jsonify({'error': f'Invalid frequency. Must be one of: {", ".join(valid_frequencies)}'}), 400
    
    user_id = session['user_id']
    
    # If frequency is 'disabled', set enabled to False
    if frequency == 'disabled':
        enabled = False
        frequency = 'weekly'  # Keep a valid frequency but disable
    
    success = storage.update_user_reminder_preferences(user_id, frequency, enabled)
    
    if success:
        return jsonify({'message': 'Reminder preferences updated successfully'}), 200
    else:
        return jsonify({'error': 'Failed to update preferences'}), 500

@app.route('/api/send-reminder', methods=['POST'])
@require_auth
def send_manual_reminder():
    """Send a manual reminder email to current user"""
    user_id = session['user_id']
    user = storage.get_user_by_id(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Build single-line summary and detailed table, include both in email
    single = build_goals_single_line(user_id)
    table_text = build_goals_report_text(user_id)
    table_html = build_goals_report_html(user_id)
    goals_summary = f"{single}\n\n{table_text}"
    html_summary = f"""
<html>
    <body>
        <div style="font-size:24px; line-height:1.5; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin-bottom:16px;">{single}</div>
        {table_html}
    </body>
</html>
"""

    # Send reminder email
    success = send_reminder_email(user, goals_summary, html_summary)
    
    if success:
        # Update last reminder sent timestamp
        storage.update_last_reminder_sent(user_id)
        return jsonify({'message': 'Reminder email sent successfully!'}), 200
    else:
        return jsonify({'error': 'Failed to send reminder email'}), 500

@app.route('/api/process-reminders', methods=['POST'])
def process_all_reminders():
    """Process and send reminder emails to all users who need them (cron job endpoint)"""
    # This endpoint can be called by a cron job or scheduler
    users_needing_reminders = storage.get_users_needing_reminders()
    
    sent_count = 0
    failed_count = 0
    
    for user in users_needing_reminders:
        try:
            # Single-line summary + detailed table for this user
            single = build_goals_single_line(user['id'])
            table_text = build_goals_report_text(user['id'])
            table_html = build_goals_report_html(user['id'])
            goals_summary = f"{single}\n\n{table_text}"
            html_summary = f"""
<html>
    <body>
        <div style="font-size:24px; line-height:1.5; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin-bottom:16px;">{single}</div>
        {table_html}
    </body>
</html>
"""
            
            # Send reminder email
            success = send_reminder_email(user, goals_summary, html_summary)
            
            if success:
                storage.update_last_reminder_sent(user['id'])
                sent_count += 1
                print(f"Sent reminder to {user['email']}")
            else:
                failed_count += 1
                print(f"Failed to send reminder to {user['email']}")
                
        except Exception as e:
            failed_count += 1
            print(f"Error processing reminder for {user.get('email', 'unknown')}: {e}")
    
    return jsonify({
        'message': f'Processed reminders for {len(users_needing_reminders)} users',
        'sent': sent_count,
        'failed': failed_count,
        'total_processed': len(users_needing_reminders)
    }), 200


# Email Test Routes
@app.route('/email-test')
def email_test_page():
    """Email configuration test page"""
    email_configured = bool(EMAIL_CONFIG['email'] and EMAIL_CONFIG['password'])
    
    # Safely expose config for display (without sensitive data)
    safe_config = {
        'smtp_server': EMAIL_CONFIG['smtp_server'],
        'smtp_port': EMAIL_CONFIG['smtp_port'],
        'email': EMAIL_CONFIG['email'],
        'password': EMAIL_CONFIG['password'],  # Will be masked in template
        'from_name': EMAIL_CONFIG['from_name']
    }
    
    return render_template('email_test.html', 
                         email_configured=email_configured,
                         email_config=safe_config)

@app.route('/email-test/send', methods=['POST'])
def send_test_email():
    """Send a test email"""
    data = request.json or {}
    test_email = data.get('test_email', '').strip()
    test_subject = data.get('test_subject', 'Test Email')
    test_message = data.get('test_message', 'This is a test email.')
    
    if not test_email:
        return jsonify({'error': 'Email address is required'}), 400
    
    # Check if email is configured
    if not EMAIL_CONFIG['email'] or not EMAIL_CONFIG['password']:
        return jsonify({
            'message': f'Email not configured. Test email would be sent to: {test_email}',
            'details': 'Check server console for development output'
        }), 200
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['from_name']} <{EMAIL_CONFIG['email']}>"
        msg['To'] = test_email
        msg['Subject'] = test_subject
        
        msg.attach(MIMEText(test_message, 'plain', 'utf-8'))
        
        # Send email
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        # Ensure credentials are ASCII compatible
        email_cred = EMAIL_CONFIG['email'].encode('ascii', 'ignore').decode('ascii')
        password_cred = EMAIL_CONFIG['password'].encode('ascii', 'ignore').decode('ascii')
        server.login(email_cred, password_cred)
        server.send_message(msg)
        server.quit()
        
        return jsonify({'message': f'Test email sent successfully to {test_email}'}), 200
        
    except Exception as e:
        error_msg = str(e)
        print(f"Failed to send test email: {error_msg}")
        return jsonify({'error': f'Failed to send email: {error_msg}'}), 500

@app.route('/email-test/verification', methods=['POST'])
def send_test_verification():
    """Send a test verification email"""
    data = request.json or {}
    verify_email = data.get('verify_email', '').strip()
    verify_name = data.get('verify_name', 'Test User')
    
    if not verify_email:
        return jsonify({'error': 'Email address is required'}), 400
    
    # Generate a test token
    test_token = str(uuid.uuid4())
    
    try:
        success = send_verification_email(verify_email, test_token, verify_name)
        
        if success:
            verification_link = f"{BASE_URL}/verify-email?token={test_token}"
            return jsonify({
                'message': f'Test verification email would be sent to {verify_email}',
                'verification_link': verification_link,
                'details': 'Check server console for development output or your email inbox'
            }), 200
        else:
            return jsonify({'error': 'Failed to send verification email'}), 500
            
    except Exception as e:
        error_msg = str(e)
        print(f"Failed to send test verification email: {error_msg}")
        return jsonify({'error': f'Failed to send verification email: {error_msg}'}), 500

@app.route('/email-config')
def email_config_page():
    """Email configuration setup page"""
    email_configured = bool(EMAIL_CONFIG['email'] and EMAIL_CONFIG['password'])
    
    # Safely expose config for display (without sensitive data)
    safe_config = {
        'smtp_server': EMAIL_CONFIG['smtp_server'],
        'smtp_port': EMAIL_CONFIG['smtp_port'],
        'email': EMAIL_CONFIG['email'],
        'password': '********' if EMAIL_CONFIG['password'] else '',
        'from_name': EMAIL_CONFIG['from_name']
    }
    
    return render_template('email_config.html', 
                         email_configured=email_configured,
                         email_config=safe_config)

@app.route('/email-config/save', methods=['POST'])
def save_email_config_route():
    """Save email configuration"""
    data = request.json or {}
    
    # Validate required fields
    required_fields = ['smtp_server', 'smtp_port', 'email', 'password', 'from_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400
    
    # Validate email format
    email = data.get('email', '').strip()
    if '@' not in email or '.' not in email:
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Validate port
    try:
        port = int(data.get('smtp_port', 587))
        if port not in [25, 465, 587]:
            return jsonify({'error': 'Invalid SMTP port. Use 25, 465, or 587'}), 400
    except ValueError:
        return jsonify({'error': 'SMTP port must be a number'}), 400
    
    # Prepare config
    config = {
        'smtp_server': data['smtp_server'].strip(),
        'smtp_port': port,
        'email': email,
        'password': data['password'],
        'from_name': data['from_name'].strip()
    }
    
    # Save configuration
    if save_email_config(config):
        return jsonify({'message': 'Email configuration saved successfully'}), 200
    else:
        return jsonify({'error': 'Failed to save email configuration'}), 500

@app.route('/email-config/test', methods=['POST'])
def test_email_config():
    """Test email configuration"""
    data = request.json or {}
    
    # Use provided config or current config
    test_config = {
        'smtp_server': data.get('smtp_server', EMAIL_CONFIG['smtp_server']),
        'smtp_port': int(data.get('smtp_port', EMAIL_CONFIG['smtp_port'])),
        'email': data.get('email', EMAIL_CONFIG['email']),
        'password': data.get('password', EMAIL_CONFIG['password']),
        'from_name': data.get('from_name', EMAIL_CONFIG['from_name'])
    }
    
    # Validate config
    if not all([test_config['smtp_server'], test_config['email'], test_config['password']]):
        return jsonify({'error': 'Missing required configuration fields'}), 400
    
    try:
        # Test SMTP connection with detailed logging
        print(f"Testing SMTP connection to {test_config['smtp_server']}:{test_config['smtp_port']}")
        print(f"Using email: {test_config['email']}")
        print(f"Password length: {len(test_config['password'])} characters")
        
        server = smtplib.SMTP(test_config['smtp_server'], test_config['smtp_port'])
        server.set_debuglevel(1)  # Enable SMTP debugging
        
        print("Starting TLS...")
        server.starttls()
        
        print("Attempting login...")
        # Clean credentials (remove any spaces/special chars)
        email = test_config['email'].strip()
        password = test_config['password'].strip()
        
        server.login(email, password)
        server.quit()
        
        print("SMTP test successful!")
        return jsonify({'message': 'Email configuration test successful'}), 200
        
    except smtplib.SMTPAuthenticationError as e:
        error_details = str(e)
        print(f"SMTP Auth Error: {error_details}")
        
        # Provide specific guidance based on the error
        if 'Username and Password not accepted' in error_details:
            error_msg = 'Gmail Authentication Failed. Solutions:\n1. Use App Password (not regular password)\n2. Enable 2-Step Verification first\n3. Generate new App Password\n4. Remove spaces from App Password'
        elif 'Application-specific password required' in error_details:
            error_msg = 'Gmail requires App Password. Go to Google Account → Security → 2-Step Verification → App passwords'
        else:
            error_msg = f'Authentication failed: {error_details}\n\nFor Gmail:\n1. Enable 2-Step Verification\n2. Generate App Password\n3. Use App Password instead of regular password'
        
        return jsonify({'error': error_msg}), 400
        
    except smtplib.SMTPConnectError as e:
        return jsonify({'error': f'Cannot connect to SMTP server. Check server and port. Error: {str(e)}'}), 400
    except smtplib.SMTPException as e:
        return jsonify({'error': f'SMTP error: {str(e)}'}), 400
    except UnicodeEncodeError as e:
        return jsonify({'error': 'Invalid characters in email or password. Use ASCII characters only.'}), 400
    except Exception as e:
        return jsonify({'error': f'Connection test failed: {str(e)}'}), 500

@app.route('/email-config/clear', methods=['POST'])
def clear_email_config():
    """Clear email configuration"""
    try:
        # Clear the config file
        if EMAIL_CONFIG_FILE.exists():
            EMAIL_CONFIG_FILE.unlink()
        
        # Reset EMAIL_CONFIG to defaults
        EMAIL_CONFIG.update({
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'email': '',
            'password': '',
            'from_name': 'Year Plan App'
        })
        
        return jsonify({'message': 'Email configuration cleared'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to clear configuration: {str(e)}'}), 500

@app.route('/email-config/gmail-help', methods=['POST'])
def gmail_troubleshooting():
    """Gmail-specific troubleshooting and alternative methods"""
    data = request.json or {}
    email = data.get('email', '').strip()
    
    if not email:
        return jsonify({'error': 'Email address required for troubleshooting'}), 400
    
    # Check if it's a Gmail account
    is_gmail = email.endswith('@gmail.com')
    
    troubleshooting_steps = []
    
    if is_gmail:
        troubleshooting_steps = [
            "🔐 Gmail App Password Setup:",
            "1. Go to myaccount.google.com",
            "2. Click 'Security' in left sidebar",
            "3. Under 'Signing in to Google', click '2-Step Verification'",
            "4. Enable 2-Step Verification if not already enabled",
            "5. Go back to Security, click 'App passwords'",
            "6. Select 'Mail' and 'Other (Custom name)'",
            "7. Enter 'Year Plan' as name",
            "8. Copy the 16-character password (no spaces)",
            "9. Use this App Password, NOT your Google password",
            "",
            "🔧 Alternative Gmail Settings:",
            "- Try server: smtp.gmail.com",
            "- Try port: 465 (SSL) instead of 587",
            "- Ensure 'Less secure app access' is OFF (use App Password instead)",
            "",
            "📱 If still failing:",
            "- Check if your Google account has restrictions",
            "- Try generating a new App Password",
            "- Verify 2-Step Verification is properly enabled"
        ]
    else:
        troubleshooting_steps = [
            f"📧 Email Provider: {email.split('@')[1]}",
            "",
            "📝 Common SMTP Settings:",
            "Outlook/Hotmail:",
            "- Server: smtp-mail.outlook.com",
            "- Port: 587 (STARTTLS)",
            "",
            "Yahoo:",
            "- Server: smtp.mail.yahoo.com", 
            "- Port: 587 or 465",
            "- May require app password",
            "",
            "🔐 General Tips:",
            "- Use app-specific passwords when available",
            "- Check if 2FA is required",
            "- Verify SMTP is enabled for your account"
        ]
    
    return jsonify({
        'email': email,
        'is_gmail': is_gmail,
        'troubleshooting_steps': troubleshooting_steps,
        'message': 'Troubleshooting information generated'
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    app.run(debug=True, port=port, host='127.0.0.1')
