# Year Plan - Annual Goals Tracker

A clean web app to plan and track your yearly goals with smart progress, ahead/behind status, and simple email reminders.

## Highlights

- Goal types: increment, decrement, and percentage
- Start/Target baseline with distance-based percent (|current-start| / |target-start|)
- Expected percent from inclusive day counting (start→end)
- Cards with inline percent, +1/+5, -1/-5, reset to Start, edit target/name
- Completed goals auto-detected, moved to a separate section and stored with real completed value
- Missed goals section (past end date, <100%)
- Goals Summary modal with normalized status (🚀 Ahead / ✅ On Track / ⚠️ Behind / 🏁 Completed)
- Empty-state CTA for first-time users: “Create your first GOAL”
- Email reminders (weekly by default) and congrats email on completion
- Optional Donate button (PayPal/PayPal.me)

## Setup

```bash
# Create/activate venv (optional)
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r yearplan/requirements.txt
```

## Run

```bash
# Default: 127.0.0.1:8080
python /Users/$(whoami)/workspace1/yearplan/yearplan/app.py

# Or specify a custom port, e.g., 8081
PORT=8081 python /Users/$(whoami)/workspace1/yearplan/yearplan/app.py
```

Then open http://127.0.0.1:8080

## Email configuration (optional)

Use the in-app page to set SMTP:

- Visit /email-config in your browser
- Fill SMTP server, port, email, password (use App Passwords for Gmail), and From name
- Save and test

Alternatively set env vars (used for verification and reminders):

- SMTP_SERVER, SMTP_PORT, EMAIL_USER, EMAIL_PASSWORD, FROM_NAME

## Donate button (optional)

Set one of the following, then restart the app:

- PAYPAL_DONATION_URL (preferred), e.g. `https://paypal.me/yourname`
- DONATION_URL (any donation page)

## Backups

Create a timestamped archive of the app directory and update the latest pointer:

```bash
cd /Users/$(whoami)/workspace1
ts=$(date +%Y%m%d-%H%M%S)
tar -czf yearplan_backups/yearplan-stage1-${ts}.tar.gz yearplan
ln -sf yearplan-stage1-${ts}.tar.gz yearplan_backups/yearplan-stage1-latest.tar.gz
```

## Notes

- Data is stored at `~/.yearplan.json`
- Users are email-verified on registration (verification link shown/logged in dev)
- Congrats email is sent once when a goal crosses to 100%

---

CLI (legacy quick helper)

```bash
python -m yearplan add "Finish book"
python -m yearplan list
```
