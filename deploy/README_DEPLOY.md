# YearPlan Deployment (AWS EC2 - RHEL 10)

This guide provisions and deploys the YearPlan app to an AWS EC2 instance running Red Hat Enterprise Linux 10. It installs Python, Nginx, sets up a dedicated virtualenv for the app, configures Gunicorn + Nginx reverse proxy, and issues an SSL certificate using a pip-installed Certbot in its own virtualenv.

- Domain: yeargoal.6ray.com
- Repo: https://github.com/daedal-bit/yearplan

## Prerequisites
- A RHEL 10 EC2 instance with a public IP
- DNS A record pointing yeargoal.6ray.com to your EC2 public IP
- SSH access with a sudo-capable user
- MySQL database reachable from the EC2 instance, and credentials ready

## What gets installed/configured
- System packages: python3, python3-venv, nginx, git, firewalld, policycoreutils-python-utils
- App directories: /opt/yearplan/yearplan (code) and /opt/yearplan/venv (venv)
- Repo/working copy at /opt/yearplan/yearplan (no git required if you copy files manually)
- Python deps installed into /opt/yearplan/venv
- Nginx as reverse proxy with HTTP->HTTPS redirect and static file serving
- Gunicorn running the Flask app on 127.0.0.1:8000 (systemd-managed)
- Certbot installed via pip in /opt/certbot-venv with webroot authentication
- Systemd timer for certificate renewals

## Quick start
1) Create environment file and set secrets:
```
sudo install -m 0640 -o root -g root deploy/env.example /etc/yearplan.env
sudo vi /etc/yearplan.env
```

2) Provision the server (adjust email and domain as needed):
```
sudo bash deploy/provision_rhel10.sh --domain yeargoal.6ray.com --email you@example.com --no-git
# Optional flags:
#   -s <step>         # resume from step number if re-running
#   --with-mysql      # install local MySQL (use with the flags below)
#   --mysql-root-password 'rootpwd' --mysql-db yearplan --mysql-user yearplan --mysql-pass 'strongpass'
```

3) Issue the initial certificate (only if the script didn’t request it automatically):
```
sudo /opt/certbot-venv/bin/certbot certonly --webroot -w /var/www/letsencrypt -d yeargoal.6ray.com --email you@example.com --agree-tos --no-eff-email
sudo systemctl reload nginx
```

4) Enable and start services:
```
sudo systemctl enable --now yearplan
sudo systemctl enable --now certbot-renew.timer
```

5) Deploy updates later:
```
cd /opt/yearplan/yearplan && sudo -u yearplan git fetch --all && sudo -u yearplan git checkout main && sudo -u yearplan git pull
sudo /opt/yearplan/venv/bin/pip install -r /opt/yearplan/yearplan/requirements.txt
sudo systemctl restart yearplan
```

## Files in deploy/
- provision_rhel10.sh: One-shot provisioning script (interactive; supports --no-git and -s resume)
- yearplan.service: systemd unit for Gunicorn (reference; script writes final unit)
- nginx/yeargoal.6ray.com.conf: Example Nginx vhost (reference; script writes final conf)
- certbot-renew.service, certbot-renew.timer: Renewal via systemd (reference; script writes final unit)
- renew_certs.sh: Manual renewal helper
- env.example: Environment file template

## Notes
- Certbot is installed via pip in /opt/certbot-venv as requested. The webroot method avoids extra OS plugins.
- SELinux boolean httpd_can_network_connect is enabled to allow Nginx proxying.
- Adjust Gunicorn worker count in the systemd unit based on instance size.

Admin/seeding note
- The --email flag is for Certbot contact only (not a seed user).
- Seed users can be created from the Site Config page (Seed Verified User). Default suggestion is admin@<your-host>.
