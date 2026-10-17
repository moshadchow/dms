#!/usr/bin/env bash
# Certbot renewal deploy hook — installed to
# /etc/letsencrypt/renewal-hooks/deploy/ by scripts/tls/install_tls.sh.
# Runs after every successful renewal; validates the full nginx config
# before reloading so a broken dms.conf can never be pushed live.
set -euo pipefail

nginx -t
systemctl reload nginx
