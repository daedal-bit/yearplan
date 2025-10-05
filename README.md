# Year Plan — Annual Goals Tracker

A clean Flask web app to plan and track yearly goals with smart progress, friendly status labels, reminders, and a simple UI.

## Features

- Three goal types: increment, decrement, percentage
- Correct progress math: percent = |current − start| / |target − start| × 100
- Expected progress from inclusive dates (Start→End) for fair “On Track” judgment
- Cards with inline percent, +1/+5 and -1/-5 steppers, reset-to-Start, edit target/name
- Completed goals stored with real completed_value; Missed section for past-due < 100%
- Goals Summary modal with normalized labels: 🚀 Ahead / ✅ On Track / ⚠️ Behind / 🏁 Completed
- Empty-state CTA for new users: “Create your first GOAL”
- Email reminders (weekly default) and a “Congrats” email when you complete a goal
- Optional Donate button (PayPal or any URL)

## Requirements

- Python 3.10+ recommended
- Install Python packages from `yearplan/requirements.txt`

## Setup

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r yearplan/requirements.txt
```

## Run locally

Option A (recommended): run as a module to satisfy package imports
```bash
python -m yearplan.yearplan.app
```

Option B: direct script (works when PYTHONPATH includes repo root)
```bash
PYTHONPATH=. python yearplan/yearplan/app.py
```

Environment
- PORT: change server port (default 8080)
- BASE_URL: absolute base used in email links (e.g. https://your.domain)

Then open: http://127.0.0.1:8080

## Email configuration (optional but recommended)

In-app setup:
1) Open /email-config
2) Enter SMTP server, port, email, password (use App Passwords for Gmail), from name
3) Save and test

Environment variables (override or bootstrap config):
- SMTP_SERVER, SMTP_PORT, EMAIL_USER, EMAIL_PASSWORD, FROM_NAME

Verification links use BASE_URL; make sure it matches your public URL in production.

## Donate button (optional)

Configure one of:
- PAYPAL_DONATION_URL (preferred), e.g. https://paypal.me/yourname
- DONATION_URL (any donation/donate page)

## Data & storage

- App data: `~/.yearplan.json`
- Email settings file: `~/.yearplan_email_config.json`

## Backups

Create a timestamped archive and keep a convenient “latest” pointer:
```bash
cd /Users/$(whoami)/workspace1
ts=$(date +%Y%m%d-%H%M%S)
tar --exclude "yearplan/.venv" --exclude "yearplan/__pycache__" --exclude "yearplan/.pytest_cache" --exclude "yearplan/.git" \
	-czf yearplan_backup_${ts}.tar.gz yearplan
ln -sf yearplan_backup_${ts}.tar.gz yearplan_backup_latest.tar.gz
```

## Tests

```bash
PYTHONPATH=. pytest -q yearplan/tests
```

## Production (brief)

- Run with Gunicorn behind Nginx (systemd service recommended)
- Ensure environment and paths are set for the service user (BASE_URL, email config path)
- Use Let’s Encrypt (certbot) for TLS; on RHEL use EPEL certbot

## Notes

- New users must verify via email; verification is robust to token case/whitespace and clears token on success
- Summary status compares actual% to expected% with 0.7/1.3 thresholds
- “Completed” appears at 100%; not labeled “Ahead”
