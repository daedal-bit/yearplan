#!/usr/bin/env bash
set -euo pipefail
/opt/certbot-venv/bin/certbot renew --quiet --deploy-hook "/bin/systemctl reload nginx"
