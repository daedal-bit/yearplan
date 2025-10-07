#!/usr/bin/env bash
set -euo pipefail

# Configuration (defaults)
DOMAIN=""
REPO_URL="https://github.com/daedal-bit/yearplan"
BRANCH="main"
ADMIN_EMAIL=""
NO_GIT=0
WITH_MYSQL=0
MYSQL_ROOT_PASSWORD=""
MYSQL_DATABASE="yearplan"
MYSQL_USER="yearplan"
MYSQL_PASSWORD="change-me"
START_STEP=1
MYSQL_NOGPGCHECK=0

usage() {
  echo "Usage: $0 --domain yeargoal.6ray.com --email you@example.com [--repo <url>] [--branch <name>] [--no-git] [-s <step>] [--with-mysql [--mysql-root-password <pwd>] [--mysql-db <db>] [--mysql-user <user>] [--mysql-pass <pwd>]]"
  echo
  echo "Steps for -s (start from this step):"
  echo " 1) Base packages     2) User/dirs       3) Repo setup      4) Python venv"
  echo " 5) Env file          6) SELinux         7) Nginx vhost     8) Certbot venv"
  echo " 9) App service      10) Certbot timer  11) Firewall       12) Nginx start"
  echo "13) MySQL (optional) 14) Restart app     15) Health check"
  echo
  echo "MySQL options (when using --with-mysql):"
  echo "  --mysql-root-password <pwd>  Root password used for DB creation"
  echo "  --mysql-db <db>               App database name (default: yearplan)"
  echo "  --mysql-user <user>           App DB user (default: yearplan)"
  echo "  --mysql-pass <pwd>            App DB password (default: change-me)"
  echo "  --mysql-no-gpg-check          Bypass GPG checks when installing MySQL repo/packages"
}

# Argument parsing
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --email) ADMIN_EMAIL="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    -s|--start-step) START_STEP="$2"; shift 2 ;;
    --no-git) NO_GIT=1; shift 1 ;;
    --with-mysql) WITH_MYSQL=1; shift 1 ;;
    --mysql-root-password) MYSQL_ROOT_PASSWORD="$2"; shift 2 ;;
    --mysql-db) MYSQL_DATABASE="$2"; shift 2 ;;
    --mysql-user) MYSQL_USER="$2"; shift 2 ;;
    --mysql-pass) MYSQL_PASSWORD="$2"; shift 2 ;;
    --mysql-no-gpg-check) MYSQL_NOGPGCHECK=1; shift 1 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "$DOMAIN" || -z "$ADMIN_EMAIL" ]]; then
  usage; exit 1
fi

# Ensure root
if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)."; exit 1
fi

# Debug: print parsed args (excluding secrets)
echo "[ARGS] DOMAIN=$DOMAIN"
echo "[ARGS] ADMIN_EMAIL=$ADMIN_EMAIL NO_GIT=$NO_GIT WITH_MYSQL=$WITH_MYSQL START_STEP=$START_STEP"
echo "[ARGS] MYSQL_DATABASE=$MYSQL_DATABASE MYSQL_USER=$MYSQL_USER MYSQL_PASSWORD=$MYSQL_PASSWORD"
if [[ -n "$MYSQL_ROOT_PASSWORD" ]]; then
  echo "[ARGS] MYSQL_ROOT_PASSWORD=****"
else
  echo "[ARGS] MYSQL_ROOT_PASSWORD=<empty>"
fi
echo "[ARGS] MYSQL_NOGPGCHECK=$MYSQL_NOGPGCHECK"

prompt_continue() {
  local stepmsg="$1"
  echo
  echo "[PAUSE] $stepmsg"
  read -r -p "Type 'yes' to continue: " ans
  if [[ "$ans" != "yes" ]]; then
    echo "Aborting as requested."; exit 1
  fi
}

# STEP 1: Base packages
if (( START_STEP <= 1 )); then
  echo "[STEP 1] Installing base packages (python3, pip, git, nginx, firewalld, SELinux utils)"
  if command -v dnf >/dev/null 2>&1; then
    dnf -y install python3 python3-pip git nginx firewalld policycoreutils-python-utils || true
  else
    yum -y install python3 python3-pip git nginx firewalld policycoreutils-python || true
  fi
  echo "[STEP 1] Done."
  prompt_continue "Base packages installed."
else
  echo "[STEP 1] Skipped (start-step=$START_STEP)"
fi

# STEP 2: User and directories
if (( START_STEP <= 2 )); then
  echo "[STEP 2] Creating user and directories under /opt/yearplan/yearplan"
  id -u yearplan >/dev/null 2>&1 || useradd -r -s /sbin/nologin -d /opt/yearplan yearplan
  install -d -o yearplan -g yearplan /opt/yearplan /opt/yearplan/venv /opt/yearplan/yearplan
  install -d -o root -g root -m 0755 /var/www/letsencrypt
  echo "[STEP 2] Done."
  prompt_continue "User and directories created."
else
  echo "[STEP 2] Skipped (start-step=$START_STEP)"
fi

# STEP 3: Repo setup
if (( START_STEP <= 3 )); then
  echo "[STEP 3] Repository setup at /opt/yearplan/yearplan"
  if [[ $NO_GIT -eq 0 ]]; then
    if [[ ! -d /opt/yearplan/yearplan/.git ]]; then
      sudo -u yearplan git clone "$REPO_URL" /opt/yearplan/yearplan
    fi
    pushd /opt/yearplan/yearplan >/dev/null
    sudo -u yearplan git fetch --all || true
    sudo -u yearplan git checkout "$BRANCH" || true
    sudo -u yearplan git pull || true
    popd >/dev/null
  else
    echo "[INFO] --no-git provided; ensure /opt/yearplan/yearplan contains your app"
  fi
  if [[ ! -f /opt/yearplan/yearplan/requirements.txt ]]; then
    echo "[WARN] /opt/yearplan/yearplan/requirements.txt not found."
  fi
  echo "[STEP 3] Done."
  prompt_continue "Repo in place."
else
  echo "[STEP 3] Skipped (start-step=$START_STEP)"
fi

# STEP 4: Python venv and dependencies
if (( START_STEP <= 4 )); then
  echo "[STEP 4] Creating Python venv and installing requirements"
  # Try stdlib venv first
  if ! python3 -m venv /opt/yearplan/venv 2>/dev/null; then
    echo "[STEP 4] python3 -m venv failed; bootstrapping ensurepip and retrying"
    python3 -m ensurepip --upgrade || true
    if ! python3 -m venv /opt/yearplan/venv 2>/dev/null; then
      echo "[STEP 4] venv still unavailable; falling back to virtualenv via pip"
      python3 -m pip install --upgrade pip setuptools wheel || true
      python3 -m pip install virtualenv || true
      python3 -m virtualenv -p python3 /opt/yearplan/venv
    fi
  fi

  # Upgrade tooling inside venv and install deps
  /opt/yearplan/venv/bin/pip install --upgrade pip setuptools wheel
  if [[ -f /opt/yearplan/yearplan/requirements.txt ]]; then
    /opt/yearplan/venv/bin/pip install -r /opt/yearplan/yearplan/requirements.txt
  else
    echo "[STEP 4][WARN] requirements.txt not found at /opt/yearplan/yearplan/requirements.txt"
  fi
  echo "[STEP 4] Done."
  prompt_continue "Python dependencies installed."
else
  echo "[STEP 4] Skipped (start-step=$START_STEP)"
fi

# STEP 5: Environment file
if (( START_STEP <= 5 )); then
  echo "[STEP 5] Creating /etc/yearplan.env (if missing)"
  if [[ ! -f /etc/yearplan.env ]]; then
    install -m 0640 -o root -g root /opt/yearplan/yearplan/deploy/env.example /etc/yearplan.env || true
    sed -i "s#HOST_LINK=.*#HOST_LINK=https://$DOMAIN#g" /etc/yearplan.env
    sed -i "s#MYSQL_DATABASE=.*#MYSQL_DATABASE=$MYSQL_DATABASE#g" /etc/yearplan.env
    sed -i "s#MYSQL_USER=.*#MYSQL_USER=$MYSQL_USER#g" /etc/yearplan.env
    sed -i "s#MYSQL_PASSWORD=.*#MYSQL_PASSWORD=$MYSQL_PASSWORD#g" /etc/yearplan.env
  fi
  echo "[STEP 5] Done."
  prompt_continue "Environment ready."
else
  echo "[STEP 5] Skipped (start-step=$START_STEP)"
fi

# STEP 6: SELinux boolean
if (( START_STEP <= 6 )); then
  echo "[STEP 6] Configuring SELinux to allow Nginx proxy"
  if command -v setsebool >/dev/null 2>&1; then
    setsebool -P httpd_can_network_connect 1 || true
  fi
  echo "[STEP 6] Done."
  prompt_continue "SELinux configured."
else
  echo "[STEP 6] Skipped (start-step=$START_STEP)"
fi

# STEP 7: Nginx vhost (HTTP bootstrap)
if (( START_STEP <= 7 )); then
  echo "[STEP 7] Installing temporary HTTP-only Nginx vhost for $DOMAIN"
  install -d /etc/nginx/conf.d
  # Remove any old HTTPS vhost that could reference missing certs
  rm -f /etc/nginx/conf.d/yeargoal.6ray.com.conf /etc/nginx/conf.d/yeargoal.https.conf || true
  install -m 0644 /opt/yearplan/yearplan/deploy/nginx/yeargoal.http.conf /etc/nginx/conf.d/yeargoal.http.conf
  sed -i "s#yeargoal.6ray.com#$DOMAIN#g" /etc/nginx/conf.d/yeargoal.http.conf
  echo "[STEP 7] Done."
  prompt_continue "HTTP vhost installed."
else
  echo "[STEP 7] Skipped (start-step=$START_STEP)"
fi

# STEP 8: Certbot venv (prepare for issuance later)
if (( START_STEP <= 8 )); then
  echo "[STEP 8] Installing Certbot (pip venv)"
  python3 -m venv /opt/certbot-venv
  /opt/certbot-venv/bin/pip install --upgrade pip
  /opt/certbot-venv/bin/pip install certbot
  install -d -m 0755 -o nginx -g nginx /var/www/letsencrypt
  echo "[STEP 8] Done."
  prompt_continue "Certbot venv ready (certificate will be requested after Nginx is up)."
else
  echo "[STEP 8] Skipped (start-step=$START_STEP)"
fi

# PRE: MySQL bootstrap early (if requested) so app can start
if (( WITH_MYSQL == 1 )) && (( START_STEP <= 9 )); then
  echo "[PRE] Ensuring MySQL is installed and running before starting app"
  if ! systemctl is-active --quiet mysqld; then
    if ! rpm -q mysql-community-server >/dev/null 2>&1; then
      if (( MYSQL_NOGPGCHECK == 1 )); then
        rpm -Uvh --nosignature https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm || true
        dnf -y --nogpgcheck install mysql-community-server || yum -y --nogpgcheck install mysql-community-server || true
      else
        rpm -Uvh https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm || true
        dnf -y install mysql-community-server || yum -y install mysql-community-server
      fi
    fi
    systemctl enable --now mysqld || true
  fi
  if [[ -n "$MYSQL_ROOT_PASSWORD" ]]; then
    echo "[PRE] Creating database and app user if needed"
    MYSQL_CMD=(mysql -uroot)
    if [[ -n "$MYSQL_ROOT_PASSWORD" ]]; then
      MYSQL_CMD=(mysql -uroot -p"$MYSQL_ROOT_PASSWORD")
    fi
    "${MYSQL_CMD[@]}" <<SQL || true
CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$MYSQL_USER'@'127.0.0.1' IDENTIFIED BY '$MYSQL_PASSWORD';
GRANT ALL PRIVILEGES ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
  else
    echo "[PRE][INFO] MYSQL_ROOT_PASSWORD not supplied; skipping DB/user creation"
  fi
fi

# STEP 9: App service
if (( START_STEP <= 9 )); then
  echo "[STEP 9] Installing systemd service for YearPlan"
  install -m 0644 /opt/yearplan/yearplan/deploy/yearplan.service /etc/systemd/system/yearplan.service
  systemctl daemon-reload
  systemctl enable --now yearplan || true
  # Brief wait and check port 8000
  sleep 1
  if ! ss -ltn '( sport = :8000 )' | grep -q 8000; then
    echo "[STEP 9][WARN] Gunicorn not listening on 127.0.0.1:8000 yet; check 'journalctl -u yearplan -e' if issues persist."
  fi
  echo "[STEP 9] Done."
  prompt_continue "Service installed."
else
  echo "[STEP 9] Skipped (start-step=$START_STEP)"
fi

# STEP 10: Certbot timer
if (( START_STEP <= 10 )); then
  echo "[STEP 10] Installing certbot renew service & timer"
  cat >/etc/systemd/system/certbot-renew.service <<EOF
[Unit]
Description=Certbot Renew (pip venv)

[Service]
Type=oneshot
ExecStart=/opt/certbot-venv/bin/certbot renew --quiet --deploy-hook "/bin/systemctl reload nginx"
EOF
  cat >/etc/systemd/system/certbot-renew.timer <<EOF
[Unit]
Description=Run certbot renew twice daily

[Timer]
OnCalendar=*-*-* 00,12:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now certbot-renew.timer || true
  echo "[STEP 10] Done."
  prompt_continue "Timer enabled."
else
  echo "[STEP 10] Skipped (start-step=$START_STEP)"
fi

# STEP 11: Firewall
if (( START_STEP <= 11 )); then
  echo "[STEP 11] Opening firewall for HTTP/HTTPS"
  systemctl enable --now firewalld || true
  firewall-cmd --permanent --add-service=http || true
  firewall-cmd --permanent --add-service=https || true
  firewall-cmd --reload || true
  echo "[STEP 11] Done."
  prompt_continue "Firewall configured."
else
  echo "[STEP 11] Skipped (start-step=$START_STEP)"
fi

# STEP 12: Nginx start
if (( START_STEP <= 12 )); then
  echo "[STEP 12] Starting Nginx"
  # Ensure no stale HTTPS vhost is present before first start
  rm -f /etc/nginx/conf.d/yeargoal.6ray.com.conf /etc/nginx/conf.d/yeargoal.https.conf || true
  # Validate configuration before starting
  if ! nginx -t; then
    echo "[STEP 12][ERROR] nginx configuration test failed. Current conf.d listing:" >&2
    ls -la /etc/nginx/conf.d >&2 || true
  fi
  systemctl enable --now nginx || true
  systemctl reload nginx || true
  # Verify ACME webroot reachability before attempting issuance
  echo "[STEP 12] Verifying ACME webroot reachability via http://$DOMAIN/.well-known/acme-challenge/"
  ACME_DIR="/var/www/letsencrypt/.well-known/acme-challenge"
  mkdir -p "$ACME_DIR"
  PROBE_FILE="probe_$(date +%s)"
  PROBE_VALUE="ok-$(date +%s)"
  echo "$PROBE_VALUE" > "$ACME_DIR/$PROBE_FILE"
  REACHABLE=0
  for i in 1 2 3; do
    RESP=$(curl -fsS --max-time 5 "http://$DOMAIN/.well-known/acme-challenge/$PROBE_FILE" || true)
    if [[ "$RESP" == "$PROBE_VALUE" ]]; then
      REACHABLE=1; break
    fi
    echo "[STEP 12] ACME probe attempt $i failed (got='${RESP:-<empty>}'), retrying..."
    sleep 2
  done
  rm -f "$ACME_DIR/$PROBE_FILE" || true

  if (( REACHABLE == 0 )); then
    echo "[STEP 12][WARN] ACME webroot not reachable from the Internet. Skipping certificate issuance."
    echo "               Check DNS (A record), Security Groups, firewall-cmd, and Nginx mapping, then rerun with '-s 12'."
  else
    # Attempt certificate issuance now that HTTP is serving ACME webroot
    echo "[STEP 12] Attempting certificate issuance for $DOMAIN"
    if /opt/certbot-venv/bin/certbot certonly --non-interactive --agree-tos --email "$ADMIN_EMAIL" --webroot -w /var/www/letsencrypt -d "$DOMAIN"; then
    echo "[STEP 12] Certificate obtained successfully. Switching to HTTPS vhost."
    # Standardize on filename matching the domain template
    install -m 0644 /opt/yearplan/yearplan/deploy/nginx/yeargoal.6ray.com.conf /etc/nginx/conf.d/yeargoal.6ray.com.conf
    sed -i "s#yeargoal.6ray.com#$DOMAIN#g" /etc/nginx/conf.d/yeargoal.6ray.com.conf
    rm -f /etc/nginx/conf.d/yeargoal.http.conf /etc/nginx/conf.d/yeargoal.https.conf || true
    systemctl reload nginx || systemctl restart nginx || true
    else
      echo "[STEP 12][WARN] Certificate issuance failed; staying on HTTP-only vhost for now."
    fi
  fi
  echo "[STEP 12] Done."
  prompt_continue "Nginx is up (and HTTPS configured if issuance succeeded)."
else
  echo "[STEP 12] Skipped (start-step=$START_STEP)"
fi

# STEP 13: Optional MySQL setup
if (( START_STEP <= 13 )); then
  if [[ $WITH_MYSQL -eq 1 ]]; then
    echo "[STEP 13] Installing MySQL Server (community)"
    if ! rpm -q mysql-community-server >/dev/null 2>&1; then
      if (( MYSQL_NOGPGCHECK == 1 )); then
        rpm -Uvh --nosignature https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm || true
        dnf -y --nogpgcheck install mysql-community-server || yum -y --nogpgcheck install mysql-community-server || true
      else
        rpm -Uvh https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm || true
        dnf -y install mysql-community-server || yum -y install mysql-community-server
      fi
    fi
    systemctl enable --now mysqld
    if [[ -n "$MYSQL_ROOT_PASSWORD" ]]; then
      echo "[STEP 13] Creating database and user (best-effort)"
      mysql --connect-timeout=5 -uroot -e 'SELECT 1' >/dev/null 2>&1 || true
      MYSQL_CMD=(mysql -uroot)
      if [[ -n "$MYSQL_ROOT_PASSWORD" ]]; then
        MYSQL_CMD=(mysql -uroot -p"$MYSQL_ROOT_PASSWORD")
      fi
      "${MYSQL_CMD[@]}" <<SQL || true
CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$MYSQL_USER'@'127.0.0.1' IDENTIFIED BY '$MYSQL_PASSWORD';
GRANT ALL PRIVILEGES ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
    fi
    echo "[STEP 13] Done."
    prompt_continue "MySQL step completed (if enabled)."
  else
    echo "[STEP 13] Skipped (WITH_MYSQL=0)"
  fi
else
  echo "[STEP 13] Skipped (start-step=$START_STEP)"
fi

# STEP 14: Restart app and ensure HTTPS vhost (if certs present)
if (( START_STEP <= 14 )); then
  echo "[STEP 14] Restarting yearplan"
  systemctl restart yearplan || true
  # If certificate exists, switch Nginx to HTTPS vhost
  if [[ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" && -f "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ]]; then
    echo "[STEP 14] Ensuring HTTPS vhost for $DOMAIN"
    if [[ ! -f /etc/nginx/conf.d/yeargoal.6ray.com.conf ]]; then
      install -m 0644 /opt/yearplan/yearplan/deploy/nginx/yeargoal.6ray.com.conf /etc/nginx/conf.d/yeargoal.6ray.com.conf
      sed -i "s#yeargoal.6ray.com#$DOMAIN#g" /etc/nginx/conf.d/yeargoal.6ray.com.conf
    fi
    # remove temporary HTTP vhost
    rm -f /etc/nginx/conf.d/yeargoal.http.conf /etc/nginx/conf.d/yeargoal.https.conf || true
    # validate and reload nginx
    if nginx -t; then
      systemctl reload nginx || systemctl restart nginx || true
    else
      echo "[STEP 14][WARN] nginx -t failed; not reloading"
    fi
  else
    echo "[STEP 14][INFO] SSL certs not present; staying on HTTP-only vhost."
  fi
  echo "[STEP 14] Done."
else
  echo "[STEP 14] Skipped (start-step=$START_STEP)"
fi

# STEP 15: Health check (gunicorn on 127.0.0.1:8000)
if (( START_STEP <= 15 )); then
  echo "[STEP 15] Checking app health at http://127.0.0.1:8000/health"
  sleep 2
  if curl -fsS --max-time 8 http://127.0.0.1:8000/health >/dev/null; then
    echo "[STEP 15] Health check OK"
  else
    echo "[STEP 15][WARN] Health check failed; check 'journalctl -u yearplan -e'"
  fi
else
  echo "[STEP 15] Skipped (start-step=$START_STEP)"
fi

echo
echo "✅ Provisioning complete. Visit: https://$DOMAIN/"
