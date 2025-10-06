import os
import json
import smtplib
from pathlib import Path
import uuid
from datetime import datetime, timedelta
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify

# Import MySQL storage instead of JSON storage
from yearplan.mysql_storage import MySQLStorage

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-change-this')
DEBUG_WEB = os.environ.get('YEARPLAN_DEBUG_WEB', '0') in {'1','true','True','yes'}
AUTO_APPROVE = os.environ.get('YEARPLAN_AUTO_APPROVE', '0') in {'1','true','True','yes'}

# -----------------------
# Site-wide config (PayPal/Base URL, etc.)
# -----------------------
SITE_CONFIG_FILE = Path.home() / '.yearplan_site_config.json'
SITE_CONFIG = {
    'paypal_link': os.environ.get('PAYPAL_LINK', ''),
    'base_url': os.environ.get('BASE_URL', ''),
    'host_link': os.environ.get('HOST_LINK', ''),
}

def load_site_config():
    if SITE_CONFIG_FILE.exists():
        try:
            with open(SITE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                SITE_CONFIG.update(json.load(f))
        except Exception as e:
            if DEBUG_WEB:
                print(f"[WEB] load_site_config error: {e}")

def save_site_config(data: dict) -> bool:
    try:
        with open(SITE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        SITE_CONFIG.update(data)
        # Also update process env for current runtime convenience
        if 'paypal_link' in data:
            os.environ['PAYPAL_LINK'] = data.get('paypal_link') or ''
        if 'base_url' in data and data.get('base_url'):
            os.environ['BASE_URL'] = data.get('base_url')
        if 'host_link' in data and data.get('host_link'):
            os.environ['HOST_LINK'] = data.get('host_link')
        return True
    except Exception as e:
        if DEBUG_WEB:
            print(f"[WEB] save_site_config error: {e}")
        return False

def get_host_link():
    """Get HOST_LINK with intelligent fallback"""
    # Try environment variable first
    host_link = os.environ.get('HOST_LINK') or (SITE_CONFIG.get('host_link') or SITE_CONFIG.get('base_url'))
    
    if host_link:
        return host_link.rstrip('/')
    
    # Fallback: construct from request context if available
    if request:
        try:
            scheme = request.scheme
            host = request.host
            return f"{scheme}://{host}"
        except Exception as e:
            if DEBUG_WEB:
                print(f"[WEB] get_host_link error: {e}\n{traceback.format_exc()}")
    
    # Final fallback: use BASE_URL or default
    base_url = (SITE_CONFIG.get('base_url') or os.environ.get('BASE_URL') or 'http://localhost:5000')
    return base_url.rstrip('/')

def get_paypal_link():
    """Get PayPal donation link from environment"""
    link = SITE_CONFIG.get('paypal_link') or os.environ.get('PAYPAL_LINK')
    return link if link else '#'

# Initialize MySQL storage
storage = MySQLStorage()
_REMINDER_PREFS = {}

@app.before_request
def _log_req():
    if DEBUG_WEB:
        try:
            print(f"[WEB] {request.method} {request.path} args={dict(request.args)}")
        except Exception:
            pass

# Email configuration (GUI support)
EMAIL_CONFIG_FILE = Path.home() / '.yearplan_email_config.json'
EMAIL_CONFIG = {
    'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.environ.get('SMTP_PORT', '587')),
    'email': os.environ.get('EMAIL_USER', ''),
    'password': os.environ.get('EMAIL_PASSWORD', ''),
    'from_name': os.environ.get('FROM_NAME', 'Year Plan App'),
}

def load_email_config():
    if EMAIL_CONFIG_FILE.exists():
        try:
            with open(EMAIL_CONFIG_FILE, 'r', encoding='utf-8') as f:
                EMAIL_CONFIG.update(json.load(f))
        except Exception as e:
            if DEBUG_WEB:
                print(f"[WEB] load_email_config error: {e}")

def save_email_config(data: dict) -> bool:
    try:
        with open(EMAIL_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        EMAIL_CONFIG.update(data)
        return True
    except Exception as e:
        if DEBUG_WEB:
            print(f"[WEB] save_email_config error: {e}")
        return False

def smtp_test_connect(cfg: dict):
    server = None
    try:
        port = int(cfg.get('smtp_port', 587))
        server = smtplib.SMTP(cfg.get('smtp_server', ''), port, timeout=10)
        if port == 587:
            server.starttls()
        if cfg.get('email') and cfg.get('password'):
            email_cred = cfg['email'].encode('ascii', 'ignore').decode('ascii')
            password_cred = cfg['password'].encode('ascii', 'ignore').decode('ascii')
            server.login(email_cred, password_cred)
        return None
    except Exception as e:
        return str(e)
    finally:
        try:
            if server:
                server.quit()
        except Exception:
            pass

def send_test_email(
    to_email: str,
    cfg: dict,
    subject: str = 'Year Plan Test Email',
    body_text: str = 'This is a test email from Year Plan.',
    body_html: str = None
):
    server = None
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{cfg.get('from_name','Year Plan App')} <{cfg.get('email','')}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        # Attach text alternative (always include)
        msg.attach(MIMEText(body_text or '', 'plain', 'utf-8'))
        # Attach HTML alternative if provided
        if body_html:
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        port = int(cfg.get('smtp_port', 587))
        smtp_server = cfg.get('smtp_server', '')
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=10)
        elif port == 587:
            server = smtplib.SMTP(smtp_server, port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_server, port, timeout=10)
        email_cred = cfg.get('email','').encode('ascii', 'ignore').decode('ascii')
        password_cred = cfg.get('password','').encode('ascii', 'ignore').decode('ascii')
        if email_cred and password_cred:
            server.login(email_cred, password_cred)
        server.send_message(msg)
        return None
    except Exception as e:
        return str(e)
    finally:
        try:
            if server:
                server.quit()
        except Exception:
            pass

load_site_config()
load_email_config()

@app.route('/email-config')
def email_config_page():
    email_configured = bool(EMAIL_CONFIG.get('email') and EMAIL_CONFIG.get('password'))
    return render_template('email_config.html', email_configured=email_configured, email_config=EMAIL_CONFIG)

@app.route('/email-config/save', methods=['POST'])
def email_config_save():
    data = request.get_json(force=True, silent=True) or {}
    try:
        data['smtp_port'] = int(data.get('smtp_port', 587))
    except Exception:
        data['smtp_port'] = 587
    if save_email_config(data):
        return jsonify({'ok': True})
    return jsonify({'error': 'Failed to save configuration'}), 500

@app.route('/email-config/test', methods=['POST'])
def email_config_test():
    data = request.get_json(force=True, silent=True) or {}
    cfg = {**EMAIL_CONFIG, **data}
    err = smtp_test_connect(cfg)
    if err:
        return jsonify({'error': err}), 400
    return jsonify({'ok': True})

@app.route('/email-config/clear', methods=['POST'])
def email_config_clear():
    try:
        if EMAIL_CONFIG_FILE.exists():
            EMAIL_CONFIG_FILE.unlink()
        EMAIL_CONFIG.update({'email': '', 'password': ''})
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/email-config/gmail-help', methods=['POST'])
def email_config_gmail_help():
    email = (request.get_json(silent=True) or {}).get('email', '')
    steps = [
        'Enable 2-Step Verification in your Google Account',
        'Create an App Password for "Mail" and your device',
        'Use smtp.gmail.com with port 587 and STARTTLS',
        'Use the 16-character App Password instead of your normal password',
    ]
    return jsonify({'email': email, 'troubleshooting_steps': steps})

@app.route('/email-test', methods=['GET', 'POST'])
def email_test_page():
    if request.method == 'GET':
        email_configured = bool(EMAIL_CONFIG.get('email') and EMAIL_CONFIG.get('password'))
        return render_template('email_test.html', email_configured=email_configured, email_config=EMAIL_CONFIG)
    to_email = request.form.get('to_email','').strip()
    if not to_email:
        flash('Please provide a recipient email address')
        email_configured = bool(EMAIL_CONFIG.get('email') and EMAIL_CONFIG.get('password'))
        return render_template('email_test.html', email_configured=email_configured, email_config=EMAIL_CONFIG)
    err = send_test_email(to_email, EMAIL_CONFIG)
    if err:
        flash(f'Failed to send email: {err}')
    else:
        flash('Test email sent successfully!')
    email_configured = bool(EMAIL_CONFIG.get('email') and EMAIL_CONFIG.get('password'))
    return render_template('email_test.html', email_configured=email_configured, email_config=EMAIL_CONFIG)

# JSON endpoints used by email_test.html front-end
@app.route('/email-test/send', methods=['POST'])
def email_test_send_json():
    data = request.get_json(silent=True) or {}
    to_email = (data.get('test_email') or '').strip()
    subject = data.get('test_subject') or 'Year Plan Email Test'
    message = data.get('test_message') or 'This is a test email from Year Plan.'
    if not to_email:
        return jsonify({'error': 'Missing test_email'}), 400
    err = send_test_email(to_email, EMAIL_CONFIG, subject=subject, body_text=message)
    if err:
        return jsonify({'error': err}), 400
    return jsonify({'message': 'Test email sent successfully'})

# -----------------------
# Site Config UI and APIs
# -----------------------
@app.route('/site-config', methods=['GET', 'POST'])
def site_config_page():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        cfg = {
            'paypal_link': (data.get('paypal_link') or '').strip(),
            'base_url': (data.get('base_url') or '').strip(),
            'host_link': (data.get('host_link') or '').strip(),
        }
        if save_site_config(cfg):
            return jsonify({'ok': True, 'config': cfg})
        return jsonify({'error': 'Failed to save site config'}), 500
    # GET: render page
    return render_template('site_config.html',
                           paypal_link=get_paypal_link(),
                           base_url=SITE_CONFIG.get('base_url') or os.environ.get('BASE_URL'),
                           host_link=get_host_link(),
                           email_config=EMAIL_CONFIG)

@app.route('/site-config/seed-user', methods=['POST'])
def site_config_seed_user():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    # Upsert verified user
    try:
        ok = False
        with storage.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET password=%s, is_verified=TRUE, verification_token=NULL, token_expires=NULL WHERE email=%s", (password, email))
            if cur.rowcount == 0:
                cur.execute("INSERT INTO users (email, password, is_verified) VALUES (%s, %s, TRUE)", (email, password))
            conn.commit()
            ok = True
        if ok:
            return jsonify({'ok': True, 'email': email})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Failed to seed user'}), 500

# Delete a specific seed/user by email
@app.route('/site-config/seed-user', methods=['DELETE'])
def site_config_delete_seed_user():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email required'}), 400
    try:
        with storage.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE email=%s", (email,))
            conn.commit()
            return jsonify({'ok': True, 'deleted': cur.rowcount})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Purge all known seed/admin users (safety for production)
@app.route('/site-config/seed-users/purge', methods=['DELETE'])
def site_config_purge_seed_users():
    try:
        host_link = get_host_link() or ''
        domain = host_link.split('//')[-1].split('/')[0]
        default_admin = f"admin@{domain}".lower() if domain and '@' not in domain else 'admin@yeargoal.6ray.com'
        seed_emails = {
            default_admin,
            'admin@yeargoal.6ray.com',
            'd@d.com',
            'd@daijiong.com',
        }
        with storage.get_connection() as conn:
            cur = conn.cursor()
            # Use IN clause for batch delete
            placeholders = ','.join(['%s'] * len(seed_emails))
            cur.execute(f"DELETE FROM users WHERE email IN ({placeholders})", tuple(seed_emails))
            conn.commit()
            return jsonify({'ok': True, 'deleted': cur.rowcount, 'emails': sorted(seed_emails)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def send_verification_email(to_email: str, name: str, verification_link: str, cfg: dict):
    server = None
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{cfg.get('from_name','Year Plan App')} <{cfg.get('email','')}>"
        msg['To'] = to_email
        msg['Subject'] = 'Verify Your Year Plan Account'
        body = f"Hello {name},\n\nPlease verify your email by clicking the link below:\n\n{verification_link}\n\nThis link will expire in 24 hours.\n\n"
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        port = int(cfg.get('smtp_port', 587))
        smtp_server = cfg.get('smtp_server', '')
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=10)
        elif port == 587:
            server = smtplib.SMTP(smtp_server, port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_server, port, timeout=10)
        email_cred = cfg.get('email','').encode('ascii', 'ignore').decode('ascii')
        password_cred = cfg.get('password','').encode('ascii', 'ignore').decode('ascii')
        if email_cred and password_cred:
            server.login(email_cred, password_cred)
        server.send_message(msg)
        return None
    except Exception as e:
        return str(e)
    finally:
        try:
            if server:
                server.quit()
        except Exception:
            pass

@app.route('/email-test/verification', methods=['POST'])
def email_test_verification_json():
    data = request.get_json(silent=True) or {}
    to_email = (data.get('verify_email') or '').strip()
    name = data.get('verify_name') or 'User'
    if not to_email:
        return jsonify({'error': 'Missing verify_email'}), 400
    # generate a dummy link for testing
    token = str(uuid.uuid4())
    host_link = get_host_link()
    verification_link = f"{host_link}/verify-email?token={token}"
    err = send_verification_email(to_email, name, verification_link, EMAIL_CONFIG)
    if err:
        return jsonify({'error': err}), 400
    return jsonify({'message': f'Verification email sent to {to_email}', 'verification_link': verification_link})

@app.route('/')
def index():
    # Optional: allow forcing a logout via query param to quickly see login UI
    try:
        if request.args.get('logout') in ('1', 'true', 'True', 'yes'):
            session.clear()
    except Exception:
        pass
    # Always serve the SPA shell; frontend will show login or main app based on /api/current-user
    # Prefer direct PayPal link when configured; otherwise use /donate redirect endpoint
    _pp = get_paypal_link()
    donation_url = _pp if (_pp and _pp != '#') else url_for('donate')
    return render_template('index.html', asset_version=int(datetime.utcnow().timestamp()), donation_url=donation_url)

@app.route('/force-logout')
def force_logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not email or not password:
            flash('Email and password are required')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('register.html')
        
        # Generate verification token (unless auto-approval)
        verification_token = str(uuid.uuid4())
        token_expires = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

        # Add user to database
        if storage.add_user(email, password, verification_token, token_expires):
            if AUTO_APPROVE:
                # Test-only: auto-verify the user immediately
                try:
                    with storage.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("UPDATE users SET is_verified=TRUE, verification_token=NULL, token_expires=NULL WHERE email=%s", (email,))
                        conn.commit()
                except Exception as e:
                    if DEBUG_WEB:
                        print('[WEB] AUTO_APPROVE update failed:', e)
                flash('Registration successful! (Auto-verified in test environment)')
                return redirect(url_for('login'))
            else:
                # Normal flow: send verification
                host_link = get_host_link()
                verification_link = f"{host_link}/verify-email?token={verification_token}"
                if EMAIL_CONFIG.get('email') and EMAIL_CONFIG.get('password'):
                    err = send_verification_email(email, email.split('@')[0], verification_link, EMAIL_CONFIG)
                    if err:
                        flash(f'Warning: could not send verification email ({err}). Link: {verification_link}')
                    else:
                        flash('Registration successful! Verification email sent.')
                else:
                    print(f"Verification link for {email}: {verification_link}")
                    flash(f'Registration successful! Please check your email for verification. (Dev: {verification_link})')
                return redirect(url_for('login'))
        else:
            flash('User already exists or registration failed')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        user = storage.authenticate_user(email, password)
        if user and (user.get('is_verified') or AUTO_APPROVE):
            # If auto-approve and not verified, mark verified in DB (test env)
            if AUTO_APPROVE and user and not user.get('is_verified'):
                try:
                    with storage.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("UPDATE users SET is_verified=TRUE, verification_token=NULL, token_expires=NULL WHERE email=%s", (email,))
                        conn.commit()
                except Exception as e:
                    if DEBUG_WEB:
                        print('[WEB] AUTO_APPROVE verify on login failed:', e)
            session['user_email'] = email
            session['user_id'] = user.get('id')
            flash('Login successful!')
            return redirect(url_for('dashboard'))
        elif user and not user.get('is_verified'):
            flash('Please verify your email before logging in')
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/verify-email')
def verify_email():
    token = request.args.get('token')
    if not token:
        return render_template('verify.html', success=False, message='Invalid verification link')

    if storage.verify_user_email(token):
        return render_template('verify.html', success=True, message='Your email has been verified. You can now log in.')
    else:
        return render_template('verify.html', success=False, message='Invalid or expired verification token')

@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    user_goals = storage.get_user_goals(session['user_email'])
    stats = storage.get_stats()
    
    return render_template('dashboard.html', 
                         user_email=session['user_email'], 
                         goals=user_goals,
                         stats=stats)

@app.route('/create-goal', methods=['GET', 'POST'])
def create_goal():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        target_date = request.form.get('target_date', '')
        
        if not title:
            flash('Goal title is required')
            return render_template('create_goal.html')
        
        goal = storage.add_goal(session['user_email'], title, description, target_date)
        if goal:
            flash('Goal created successfully!')
            return redirect(url_for('dashboard'))
        else:
            flash('Failed to create goal')
    
    return render_template('create_goal.html')

@app.route('/update-goal/<int:goal_id>/<status>')
def update_goal_status(goal_id, status):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    valid_statuses = ['active', 'completed', 'paused', 'cancelled']
    if status not in valid_statuses:
        flash('Invalid status')
        return redirect(url_for('dashboard'))
    
    if storage.update_goal_status(goal_id, status, session['user_email']):
        flash(f'Goal marked as {status}!')
    else:
        flash('Failed to update goal')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out')
    return redirect(url_for('index'))

@app.route('/donate')
def donate():
    """Redirect to PayPal donation page"""
    paypal_link = get_paypal_link()
    if paypal_link != '#':
        return redirect(paypal_link)
    else:
        flash('Donation link not configured')
        return redirect(url_for('index'))

@app.route('/stats')
def stats():
    """Show application statistics"""
    stats = storage.get_stats()
    return render_template('stats.html', stats=stats)

@app.route('/debug-config')
def debug_config():
    """Debug endpoint to show configuration"""
    return {
        'HOST_LINK_env': os.environ.get('HOST_LINK'),
        'HOST_LINK_computed': get_host_link(),
        'PAYPAL_LINK_env': os.environ.get('PAYPAL_LINK'),
        'PAYPAL_LINK_computed': get_paypal_link(),
        'MYSQL_HOST': os.environ.get('MYSQL_HOST', 'localhost'),
        'MYSQL_DATABASE': os.environ.get('MYSQL_DATABASE', 'yearplan_db'),
        'MYSQL_USER': os.environ.get('MYSQL_USER', 'yearplan_user'),
        'BASE_URL_env': os.environ.get('BASE_URL'),
        'BASE_URL_config': SITE_CONFIG.get('base_url'),
        'request_host': request.host if request else None,
        'request_scheme': request.scheme if request else None
    }

# Make configuration available to all templates
@app.context_processor
def inject_config():
    """Make configuration available to all templates"""
    return {
        'paypal_link': get_paypal_link(),
        'host_link': get_host_link()
    }

# -----------------------
# Minimal API endpoints to support existing frontend JS
# -----------------------

@app.route('/api/current-user')
def api_current_user():
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    email = session['user_email']
    name = session.get('user_name') or (email.split('@')[0] or 'User').strip().title()
    session['user_name'] = name
    return jsonify({'user': {'email': email, 'name': name}})

@app.route('/api/goals')
def api_goals():
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    raw = storage.get_user_goals(session['user_email'])
    out = []
    for g in raw:
        # parse description JSON if available
        extras = {}
        try:
            if g.get('description'):
                import json as _json
                extras = _json.loads(g['description']) if isinstance(g['description'], str) else (g['description'] or {})
        except Exception:
            extras = {}
        # compute progress from logs
        start_val = extras.get('start_value', 0) or 0
        target_val = extras.get('target')
        task_type = extras.get('task_type', 'increment')
        logs = []
        try:
            logs = storage.get_goal_logs(g.get('id'), session['user_email'])
        except Exception:
            logs = []
        current = start_val
        for l in reversed(logs):  # apply oldest to newest
            act = (l.get('action') or '').lower()
            val = float(l.get('value') or 0)
            if act == 'increment':
                current += val
            elif act == 'decrement':
                current -= val
            elif act == 'update':
                current = val
        percent = 0
        if task_type == 'percentage':
            percent = max(0, min(100, float(current)))
        elif target_val is not None:
            try:
                denom = abs(float(target_val) - float(start_val))
                if denom > 0:
                    percent = max(0, min(100, (abs(float(current) - float(start_val)) / denom) * 100))
                else:
                    percent = 100
            except Exception:
                percent = 0

        # compute expected progress based on calendar days between start_date and end_date
        # For percentage tasks: expected is a percent [0-100].
        # For numeric tasks: expected is an absolute value in the same units as progress (frontend converts to percent).
        expected = None
        try:
            # prefer start_date from extras or created_at as fallback
            sd = extras.get('start_date')
            ed = g.get('target_date')
            from datetime import datetime as _dt, date as _date
            fmt = '%Y-%m-%d'
            # Parse dates (date-only)
            if sd and isinstance(sd, str) and len(sd) >= 10:
                start_d = _dt.strptime(sd[:10], fmt).date()
            else:
                cad = str(g.get('created_at'))[:10]
                start_d = _dt.strptime(cad, fmt).date()
            end_d = _dt.strptime(str(ed)[:10], fmt).date() if ed else None
            if end_d:
                today = _date.today()
                total_days = (end_d - start_d).days
                if total_days <= 0:
                    time_ratio = 1.0
                else:
                    if today < start_d:
                        time_ratio = 0.0
                    else:
                        # Inclusive progress by day: first day counts as 1 day progress
                        done_days = (today - start_d).days + 1
                        done_days = max(0, min(total_days, done_days))
                        time_ratio = done_days / float(total_days)
                if task_type == 'percentage':
                    expected = round(time_ratio * 100.0, 4)
                elif target_val is not None:
                    try:
                        expected = float(start_val) + (float(target_val) - float(start_val)) * float(time_ratio)
                    except Exception:
                        expected = None
        except Exception:
            expected = None

        out.append({
            'id': g.get('id'),
            'text': g.get('title') or 'Untitled',
            'created_at': g.get('created_at'),
            'end_date': g.get('target_date'),
            'target': target_val,
            'status': {
                'percent': percent,
                'progress': current,
                'start': start_val,
                'task_type': task_type,
                'expected': expected
            }
        })
    return jsonify(out)

@app.route('/api/goals', methods=['POST'])
def api_goals_create():
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Missing text'}), 400
    extras = {
        'task_type': data.get('task_type'),
        'target': data.get('target'),
        'start_date': data.get('start_date'),
        'end_date': data.get('end_date'),
        'start_value': data.get('start_value'),
    }
    import json as _json
    description = _json.dumps(extras)
    target_date = data.get('end_date') or None
    goal = storage.add_goal(session['user_email'], text, description, target_date)
    if not goal:
        return jsonify({'error': 'Failed to create goal'}), 500
    return jsonify({'id': goal.get('id'), 'text': text})

@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
def api_goal_update(goal_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip().lower()
    # For now we don't persist logs/progress in DB, but we support basic actions to avoid network errors
    # Future: add a goal_logs table and compute progress from logs
    if action in {'increment','decrement','update'}:
        val = data.get('value')
        try:
            val = float(val)
        except Exception:
            val = 0.0
        # add log
        storage.add_goal_log(goal_id, session['user_email'], action, val)
        return jsonify({'ok': True})
    return jsonify({'error': 'unsupported action'}), 400

@app.route('/api/goals/<int:goal_id>/name', methods=['PUT'])
def api_goal_update_name(goal_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Missing text'}), 400
    ok = storage.update_goal_title(goal_id, session['user_email'], text)
    if not ok:
        return jsonify({'error': 'Update failed'}), 400
    return jsonify({'ok': True})

@app.route('/api/goals/<int:goal_id>/target', methods=['PUT'])
def api_goal_update_target(goal_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    target = data.get('target')
    # Update description JSON with new target
    goal = storage.get_goal_for_user(goal_id, session['user_email'])
    if not goal:
        return jsonify({'error': 'Not found'}), 404
    try:
        extras = {}
        if goal.get('description'):
            extras = json.loads(goal['description']) if isinstance(goal['description'], str) else (goal['description'] or {})
        extras['target'] = target
        new_desc = json.dumps(extras)
    except Exception as e:
        return jsonify({'error': f'Invalid description JSON: {e}'}), 500
    ok = storage.update_goal_description(goal_id, session['user_email'], new_desc)
    if not ok:
        return jsonify({'error': 'Update failed'}), 400
    return jsonify({'ok': True})

@app.route('/api/goals/<int:goal_id>', methods=['DELETE'])
def api_goal_delete(goal_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    ok = storage.delete_goal(goal_id, session['user_email'])
    return (jsonify({'ok': True}) if ok else (jsonify({'error': 'not found'}), 404))

# Compatibility routes for older/cached frontends calling increment/decrement as POSTs
@app.route('/api/goals/<int:goal_id>/increment', methods=['POST'])
def api_goal_increment(goal_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    try:
        val = float(data.get('value', 1))
    except Exception:
        val = 1.0
    storage.add_goal_log(goal_id, session['user_email'], 'increment', val)
    return jsonify({'ok': True})

@app.route('/api/goals/<int:goal_id>/decrement', methods=['POST'])
def api_goal_decrement(goal_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    try:
        val = float(data.get('value', 1))
    except Exception:
        val = 1.0
    storage.add_goal_log(goal_id, session['user_email'], 'decrement', val)
    return jsonify({'ok': True})

@app.route('/api/register', methods=['POST'])
def api_register():
    # accept form or JSON
    data = request.get_json(silent=True) or request.form
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '')
    confirm_password = (data.get('confirm_password') or password)
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password are required'}), 400
    if password != confirm_password:
        return jsonify({'success': False, 'error': 'Passwords do not match'}), 400

    verification_token = str(uuid.uuid4())
    token_expires = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

    ok = storage.add_user(email, password, verification_token, token_expires)
    if ok:
        host_link = get_host_link()
        verification_link = f"{host_link}/verify-email?token={verification_token}"
        print(f"[API] Verification link for {email}: {verification_link}")
        # Attempt to send if configured, otherwise just report success
        if EMAIL_CONFIG.get('email') and EMAIL_CONFIG.get('password'):
            err = send_verification_email(email, name or (email.split('@')[0] or 'User'), verification_link, EMAIL_CONFIG)
            if err:
                return jsonify({'success': True, 'email': email, 'name': name or email, 'message': f'Registered, but email sending failed: {err}', 'verification_link': verification_link})
            else:
                return jsonify({'success': True, 'email': email, 'name': name or email, 'message': 'Registration successful! Verification email sent.', 'verification_link': verification_link})
        # No email configured; still success with link provided
        return jsonify({'success': True, 'email': email, 'name': name or email, 'message': 'Registration successful! (Dev) Use the verification link shown.', 'verification_link': verification_link})
    return jsonify({'success': False, 'error': 'User already exists or registration failed'}), 400

@app.route('/api/resend-verification', methods=['POST'])
def api_resend_verification():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Missing email'}), 400
    user = storage.get_user_by_email(email)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.get('is_verified'):
        return jsonify({'error': 'User already verified'}), 400
    # Issue a new token
    token = str(uuid.uuid4())
    token_expires = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    storage.update_verification_token(email, token, token_expires)
    link = f"{get_host_link()}/verify-email?token={token}"
    # Try sending if configured
    if EMAIL_CONFIG.get('email') and EMAIL_CONFIG.get('password'):
        err = send_verification_email(email, (email.split('@')[0] or 'User').strip().title(), link, EMAIL_CONFIG)
        if err:
            return jsonify({'error': f'Failed to send verification email: {err}', 'verification_link': link}), 500
        return jsonify({'ok': True, 'message': 'Verification email sent', 'verification_link': link})
    # Not configured; return the link so user can proceed
    return jsonify({'ok': True, 'message': 'Email not configured; use verification link.', 'verification_link': link})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '')
    user = storage.authenticate_user(email, password)
    if user and user.get('is_verified'):
        session['user_email'] = email
        session['user_id'] = user.get('id')
        # set display name
        session['user_name'] = (email.split('@')[0] or 'User').strip().title()
        return jsonify({'success': True, 'user': {'email': email, 'name': session['user_name']}})
    elif user and not user.get('is_verified'):
        return jsonify({'success': False, 'error': 'Email not verified'}), 401
    else:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST', 'GET'])
def api_logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/completed-goals')
def api_completed_goals():
    """Return a flat array of completed goals in the shape expected by the SPA.
    A goal is considered completed when its computed percent >= 100.
    Each item fields used by frontend: id, text, start_date, end_date (or completed_at), start_value, completed_value/target.
    """
    # If not logged in, return empty array to avoid noisy errors
    if 'user_email' not in session:
        return jsonify([])
    raw = storage.get_user_goals(session['user_email'])
    out = []
    for g in raw:
        # Parse extras
        extras = {}
        try:
            if g.get('description'):
                extras = json.loads(g['description']) if isinstance(g['description'], str) else (g['description'] or {})
        except Exception:
            extras = {}
        start_val = extras.get('start_value', 0) or 0
        target_val = extras.get('target')
        task_type = extras.get('task_type', 'increment')
        # compute current via logs
        logs = []
        try:
            logs = storage.get_goal_logs(g.get('id'), session['user_email'])
        except Exception:
            logs = []
        current = start_val
        for l in reversed(logs):
            act = (l.get('action') or '').lower()
            val = float(l.get('value') or 0)
            if act == 'increment':
                current += val
            elif act == 'decrement':
                current -= val
            elif act == 'update':
                current = val
        # compute percent
        percent = 0
        try:
            if task_type == 'percentage':
                percent = max(0, min(100, float(current)))
            elif target_val is not None:
                denom = abs(float(target_val) - float(start_val))
                if denom > 0:
                    percent = max(0, min(100, (abs(float(current) - float(start_val)) / denom) * 100))
                else:
                    percent = 100
        except Exception:
            percent = 0
        if percent >= 100:
            out.append({
                'id': g.get('id'),
                'text': g.get('title') or 'Untitled',
                'start_date': extras.get('start_date') or None,
                'end_date': extras.get('end_date') or (str(g.get('target_date'))[:10] if g.get('target_date') else None),
                'start_value': start_val,
                'completed_value': current,
                'target': target_val,
            })
    return jsonify(out)

@app.route('/api/completed-goals/<int:goal_id>', methods=['DELETE'])
def api_completed_goals_delete(goal_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    ok = storage.delete_goal(goal_id, session['user_email'])
    return (jsonify({'ok': True}) if ok else (jsonify({'error': 'not found'}), 404))

# --- Additional minimal endpoints to prevent UI 404s and network errors ---
@app.route('/api/goals/<int:goal_id>/logs')
def api_goal_logs(goal_id: int):
    if 'user_email' not in session:
        return jsonify([])
    logs = storage.get_goal_logs(goal_id, session['user_email'])
    # shape to frontend expectations {id, timestamp, value}
    shaped = [
        {
            'id': l['id'],
            'timestamp': l['created_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(l['created_at'], 'strftime') else str(l['created_at']),
            'value': l['value'] if l['action'] == 'update' else (l['value'] if l['action'] == 'increment' else -l['value'])
        }
        for l in logs
    ]
    return jsonify(shaped)

@app.route('/api/logs')
def api_all_logs():
    if 'user_email' not in session:
        return jsonify([])
    logs = storage.get_all_logs_for_user(session['user_email'])
    return jsonify([
        {
            'id': l['id'],
            'goal_id': l['goal_id'],
            'timestamp': l['created_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(l['created_at'], 'strftime') else str(l['created_at']),
            'value': l['value'] if l['action'] == 'update' else (l['value'] if l['action'] == 'increment' else -l['value'])
        }
        for l in logs
    ])

@app.route('/api/logs/<int:log_id>', methods=['DELETE'])
def api_delete_log(log_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    ok = storage.delete_log(log_id, session['user_email'])
    return (jsonify({'ok': True}) if ok else (jsonify({'error': 'not found'}), 404))

@app.route('/api/logs/<int:log_id>/rollback', methods=['POST'])
def api_rollback_log(log_id: int):
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    # Simplified rollback: delete the last log (only safe for newest; frontend restricts)
    ok = storage.delete_log(log_id, session['user_email'])
    return (jsonify({'ok': True}) if ok else (jsonify({'error': 'not found'}), 404))

@app.route('/api/reminder-preferences', methods=['GET'])
def api_get_reminder_prefs():
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    prefs = _REMINDER_PREFS.get(session['user_email']) or {
        'enabled': False,
        'frequency': 'weekly',
    }
    return jsonify({'preferences': prefs})

@app.route('/api/reminder-preferences', methods=['POST'])
def api_set_reminder_prefs():
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    _REMINDER_PREFS[session['user_email']] = {
        'enabled': bool(data.get('enabled', False)),
        'frequency': data.get('frequency', 'weekly')
    }
    return jsonify({'ok': True})

@app.route('/api/send-reminder', methods=['POST'])
def api_send_reminder():
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    # Build a simple summary of current goals for this user and email it to them
    try:
        user_email = session['user_email']
        # Fetch goals and compute summary
        raw = storage.get_user_goals(user_email) or []
        lines = []
        from datetime import datetime as _dt, date as _date
        html_rows = []

        for g in raw:
            title = g.get('title') or 'Untitled'
            # parse extras from description JSON
            extras = {}
            try:
                if g.get('description'):
                    import json as _json
                    extras = _json.loads(g['description']) if isinstance(g['description'], str) else (g['description'] or {})
            except Exception:
                extras = {}

            start_val = float(extras.get('start_value') or 0)
            target_val = extras.get('target')
            target_val_f = float(target_val) if target_val is not None else None
            task_type = (extras.get('task_type') or 'increment').lower()

            # accumulate logs to compute current
            current = start_val
            try:
                logs = storage.get_goal_logs(g.get('id'), user_email) or []
            except Exception:
                logs = []
            for l in reversed(logs):
                act = (l.get('action') or '').lower()
                try:
                    val = float(l.get('value') or 0)
                except Exception:
                    val = 0.0
                if act == 'increment':
                    current += val
                elif act == 'decrement':
                    current -= val
                elif act == 'update':
                    current = val

            # compute percent
            percent = 0.0
            if task_type == 'percentage':
                try:
                    percent = max(0.0, min(100.0, float(current)))
                except Exception:
                    percent = 0.0
            elif target_val_f is not None:
                try:
                    denom = abs(target_val_f - start_val)
                    percent = 100.0 if denom == 0 else max(0.0, min(100.0, (abs(current - start_val) / denom) * 100.0))
                except Exception:
                    percent = 0.0

            # Expected percent based on time (inclusive days) like UI summary table
            expected_pct = None
            try:
                sd = extras.get('start_date')
                ed = g.get('target_date')
                fmt = '%Y-%m-%d'
                if sd and isinstance(sd, str) and len(sd) >= 10:
                    start_d = _dt.strptime(sd[:10], fmt).date()
                else:
                    cad = str(g.get('created_at'))[:10]
                    start_d = _dt.strptime(cad, fmt).date()
                end_d = _dt.strptime(str(ed)[:10], fmt).date() if ed else None
                if end_d:
                    today = _date.today()
                    total_days = max(1, (end_d - start_d).days + 1)
                    if today < start_d:
                        elapsed = 0
                    elif today > end_d:
                        elapsed = total_days
                    else:
                        elapsed = (today - start_d).days + 1
                    elapsed = max(1, min(total_days, elapsed))
                    expected_pct = (elapsed / float(total_days)) * 100.0
            except Exception:
                expected_pct = None

            end_date = g.get('target_date')
            end_s = str(end_date)[:10] if end_date else '-'
            if task_type == 'percentage':
                line = f"- {title}: {percent:.1f}% (target 100%) due {end_s}"
            else:
                if target_val_f is not None:
                    tgt_s = f"{int(target_val_f)}" if float(target_val_f).is_integer() else f"{target_val_f}"
                else:
                    tgt_s = "?"
                cur_s = f"{int(current)}" if float(current).is_integer() else f"{current}"
                line = f"- {title}: {percent:.1f}% ({cur_s}/{tgt_s}) due {end_s}"
            lines.append(line)

            # Status like UI
            status = 'Pending'
            if percent >= 100.0:
                status = '🏁 Completed'
            elif expected_pct is not None and expected_pct > 0:
                ratio = percent / expected_pct
                if ratio >= 1.3:
                    status = '🚀 Ahead'
                elif ratio <= 0.7:
                    status = '🔴 Behind'
                else:
                    status = '✅ On Track'
            else:
                status = '⏳ In Progress' if percent > 0 else 'Pending'

            # Build HTML row (inline styles for email compatibility)
            prog_color = '#ff4444' if status == '🔴 Behind' else '#4CAF50'
            target_display = f"{int(target_val_f)}" if (target_val_f is not None and float(target_val_f).is_integer()) else (f"{target_val_f}" if target_val_f is not None else '-')
            current_display = f"{int(current)}" if float(current).is_integer() else f"{current}"
            html_rows.append(f"""
                <tr>
                  <td style='padding:8px;border-bottom:1px solid #eee;'>
                    <div style='font-weight:600;color:#222'>{title}</div>
                    <div style='color:#666;font-size:12px'>{current_display} of {target_display} completed</div>
                  </td>
                  <td style='padding:8px;border-bottom:1px solid #eee;'>
                    <div style='width:140px;max-width:100%;height:8px;background:#eee;border-radius:4px;overflow:hidden;'>
                      <div style='width:{percent:.1f}%;height:8px;background:{prog_color};'></div>
                    </div>
                  </td>
                  <td style='padding:8px;border-bottom:1px solid #eee;text-align:right;white-space:nowrap;'>{percent:.1f}%</td>
                  <td style='padding:8px;border-bottom:1px solid #eee;'>
                    <span style='display:inline-block;padding:2px 8px;border-radius:12px;background:{"#ffd6d6" if status=="🔴 Behind" else "#e7f7ec"};color:{"#c00000" if status=="🔴 Behind" else "#1b5e20"};font-size:12px;'>{status}</span>
                  </td>
                </tr>
            """)

        if not lines:
            lines.append("(No active goals yet)")

        name = session.get('user_name') or (user_email.split('@')[0] or 'User').strip().title()
        subject = 'Your Year Plan reminder'
        body = (
            f"Hello {name},\n\n"
            "Here is your current goals summary:\n\n"
            + "\n".join(lines) +
            "\n\nKeep going!\n"
        )

        # Build HTML email content mirroring the Summary Table
        table_rows_html = "".join(html_rows) if html_rows else "<tr><td colspan='4' style='padding:12px;color:#666;'>No goals yet</td></tr>"
        body_html = f"""
        <div style='font-family:Arial,Helvetica,sans-serif;color:#222;line-height:1.5;'>
          <p>Hello {name},</p>
          <p>Here is your current goals summary:</p>
          <table role='presentation' cellspacing='0' cellpadding='0' border='0' width='100%' style='border-collapse:collapse;min-width:320px;'>
            <thead>
              <tr>
                <th align='left' style='padding:8px;border-bottom:2px solid #ddd;font-size:13px;color:#555;'>Project Name</th>
                <th align='left' style='padding:8px;border-bottom:2px solid #ddd;font-size:13px;color:#555;'>Progress</th>
                <th align='right' style='padding:8px;border-bottom:2px solid #ddd;font-size:13px;color:#555;'>Complete</th>
                <th align='left' style='padding:8px;border-bottom:2px solid #ddd;font-size:13px;color:#555;'>Status</th>
              </tr>
            </thead>
            <tbody>
              {table_rows_html}
            </tbody>
          </table>
          <p style='margin-top:16px;'>Keep going!</p>
        </div>
        """

        # If email config is present, send; otherwise return preview without failing hard
        if EMAIL_CONFIG.get('email') and EMAIL_CONFIG.get('password') and EMAIL_CONFIG.get('smtp_server'):
            err = send_test_email(user_email, EMAIL_CONFIG, subject=subject, body_text=body, body_html=body_html)
            if err:
                return jsonify({'error': f'Failed to send reminder: {err}', 'preview': body, 'preview_html': body_html}), 500
            return jsonify({'ok': True, 'message': f'Reminder sent to {user_email}'})
        else:
            return jsonify({'ok': True, 'message': f'Email not configured; would send to {user_email}', 'preview': body, 'preview_html': body_html})
    except Exception as e:
        if DEBUG_WEB:
            print('[WEB] api_send_reminder error:', e)
        return jsonify({'error': 'internal error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
