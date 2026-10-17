#!/usr/bin/env bash
# TLS bootstrap for the DMS production host (spec 30).
#
#   sudo scripts/tls/install_tls.sh
#
# Idempotent: safe to re-run. Installs certbot if missing, obtains (or
# renews) the Let's Encrypt certificate for the DMS domain, installs the
# renewal deploy hook that reloads nginx, and verifies nginx -t.
#
# Requirements:
#   * dms.conf deployed to nginx (server_name must match DOMAIN) and
#     listening on port 80 for the ACME http-01 challenge.
#   * Run as root.
set -euo pipefail

DOMAIN="dms.xpertfintech.com"
EMAIL=""   # optional: set a Let's Encrypt contact email; empty = --register-unsafely-without-email
WEBROOT="/var/www/dms/dms-app/dist"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "error: run as root (sudo $0)" >&2
    exit 1
fi

if [[ ! -d "$WEBROOT" ]]; then
    echo "error: webroot $WEBROOT does not exist — deploy the frontend first" >&2
    exit 1
fi

# ── 1. certbot ────────────────────────────────────────────────────────
if ! command -v certbot >/dev/null 2>&1; then
    echo "certbot not found — installing..."
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update && apt-get install -y certbot
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y certbot
    elif command -v yum >/dev/null 2>&1; then
        yum install -y certbot
    else
        echo "error: no supported package manager found — install certbot manually and re-run" >&2
        exit 1
    fi
fi

# ── 2. obtain / renew the certificate ─────────────────────────────────
email_args=(--register-unsafely-without-email)
if [[ -n "$EMAIL" ]]; then
    email_args=(--email "$EMAIL")
fi

echo "Requesting certificate for $DOMAIN (webroot: $WEBROOT)..."
certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" \
    --non-interactive --agree-tos "${email_args[@]}" \
    --keep-until-expiring

# ── 3. install the renewal deploy hook ────────────────────────────────
HOOK_DIR="/etc/letsencrypt/renewal-hooks/deploy"
mkdir -p "$HOOK_DIR"
install -m 0755 "$REPO_ROOT/scripts/tls/certbot_deploy_hook.sh" "$HOOK_DIR/certbot_deploy_hook.sh"
echo "Deploy hook installed: $HOOK_DIR/certbot_deploy_hook.sh"

# ── 4. verify nginx config and reload ─────────────────────────────────
nginx -t
systemctl reload nginx

echo
echo "TLS is live for https://$DOMAIN"
echo "  certificate: /etc/letsencrypt/live/$DOMAIN/"
echo "  renewals:    certbot renews automatically (systemd timer/cron); the deploy hook reloads nginx."
echo "  check:       certbot certificates && sudo certbot renew --dry-run"
