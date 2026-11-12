#!/usr/bin/env bash
#
# deploy.sh - DMS Deployment Script
#
# This script performs production deployment of the DMS application on AlmaLinux.
# It is designed to be run manually on the server after code is pushed to Git.
#
# Prerequisites:
#   - Git repository cloned on the server
#   - Python virtual environment activated (venv)
#   - Gunicorn installed in the virtual environment
#   - PostgreSQL running and accessible
#   - Nginx configured as reverse proxy
#
# WARNING: This script uses `git reset --hard` which will discard any local commits
# or uncommitted changes on the server. Ensure any important local changes are
# committed to Git before running this script.
#
# Usage: ./deploy.sh
#

set -euo pipefail

# ============================================================================
# Configuration - Adjust these values for your server
# ============================================================================

# Application directory (where the repo is cloned)
APP_DIR="/var/www/dms"

# Python virtual environment path
VENV_DIR="${APP_DIR}/venv"

# Git remote name (default is 'origin')
GIT_REMOTE="origin"

# Git branch to deploy (default is 'main')
GIT_BRANCH="main"

# Gunicorn configuration
GUNICORN_WORKERS="${GUNICORN_WORKERS:-4}"
GUNICORN_BIND="${GUNICORN_BIND:-127.0.0.1:8000}"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_success() {
    echo "[SUCCESS] $1"
}

# ============================================================================
# Step 1: Fetch Latest Code
# ============================================================================

log_info "=== Step 1: Fetching latest code from Git ==="

# Change to application directory
cd "${APP_DIR}" || {
    log_error "Failed to change to application directory: ${APP_DIR}"
    exit 1
}

log_info "Current directory: $(pwd)"

# Fetch from the remote repository
log_info "Fetching from ${GIT_REMOTE} ${GIT_BRANCH}..."
git fetch "${GIT_REMOTE}" "${GIT_BRANCH}"

if [ $? -ne 0 ]; then
    log_error "Failed to fetch from Git repository"
    exit 1
fi

log_success "Successfully fetched latest code"

# ============================================================================
# Step 2: Reset to Remote Main
# ============================================================================

log_info "=== Step 2: Resetting to origin/${GIT_BRANCH} ==="

# Reset hard to the remote main branch
# NOTE: This will discard any local commits or uncommitted changes
log_warning "⚠️  WARNING: 'git reset --hard' will DISCARD all local commits and uncommitted changes!"
log_warning "Ensure any important work is committed to Git before continuing."

read -p "Do you want to continue with git reset --hard? (y/n): " -n 1 -r
echo    # move to new line

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Deployment aborted by user."
    exit 0
fi

log_info "Resetting to ${GIT_REMOTE}/${GIT_BRANCH}..."
git reset --hard "${GIT_REMOTE}/${GIT_BRANCH}"

if [ $? -ne 0 ]; then
    log_error "Failed to reset Git repository"
    exit 1
fi

log_success "Successfully reset to ${GIT_REMOTE}/${GIT_BRANCH}"
log_info "Local changes discarded. Code is now at commit: $(git rev-parse --short HEAD)"

# ============================================================================
# Step 3: Apply Database Migrations
# ============================================================================

log_info "=== Step 3: Applying Database Migrations ==="

# Activate virtual environment
if [ -d "${VENV_DIR}" ]; then
    log_info "Activating virtual environment at ${VENV_DIR}..."
    source "${VENV_DIR}/bin/activate"
else
    log_error "Virtual environment not found at ${VENV_DIR}"
    log_info "Installing dependencies..."
    python3 -m venv "${VENV_DIR}"
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip
fi

# Install requirements
log_info "Installing Python dependencies from requirements.txt..."
pip install -r "${APP_DIR}/requirements.txt"

if [ $? -ne 0 ]; then
    log_error "Failed to install Python dependencies"
    exit 1
fi

# Apply Alembic migrations
log_info "Running alembic upgrade head..."
cd "${APP_DIR}"

if [ -f "alembic.ini"; then
    "${VENV_DIR}/bin/alembic" upgrade head
    if [ $? -ne 0 ]; then
        log_error "Alembic migration failed"
        exit 1
    fi
    log_success "Database migrations applied successfully"
else
    log_warning "alembic.ini not found in ${APP_DIR}. Skipping database migrations."
fi

# ============================================================================
# Step 4: Restart Gunicorn
# ============================================================================

log_info "=== Step 4: Restarting Gunicorn ==="

# Check if gunicorn is available
if ! command -v gunicorn &>/dev/null; then
    log_error "Gunicorn not found in the virtual environment"
    log_info "Installing Gunicorn..."
    pip install gunicorn
fi

# Stop any existing Gunicorn process
log_info "Stopping existing Gunicorn processes..."
pkill -f "gunicorn main:app" 2>/dev/null || true
sleep 1

# Start Gunicorn with Uvicorn worker for FastAPI
# Using the UvicornWorker class for proper FastAPI/ASGI support
log_info "Starting Gunicorn with ${GUNICORN_WORKERS} workers on ${GUNICORN_BIND}..."
log_info "Using UvicornWorker for ASGI support..."

cd "${APP_DIR}"

# Start Gunicorn in the background
nohup "${VENV_DIR}/bin/gunicorn" \
    main:app \
    -w "${GUNICORN_WORKERS}" \
    -k uvicorn.worker.UvicornWorker \
    --bind "${GUNICORN_BIND}" \
    --error-logfile "${APP_DIR}/gunicorn_error.log" \
    --access-logfile "${APP_DIR}/gunicorn_access.log" \
    --pid "${APP_DIR}/gunicorn.pid" \
    > "${APP_DIR}/gunicorn_output.log" 2>&1 &

# Wait a moment for Gunicorn to start
sleep 2

# Verify Gunicorn is running
if pgrep -f "gunicorn main:app" > /dev/null; then
    log_success "Gunicorn is running successfully"
else
    log_error "Gunicorn failed to start. Check logs in ${APP_DIR}/gunicorn_output.log"
    cat "${APP_DIR}/gunicorn_output.log" 2>/dev/null || true
    exit 1
fi

# ============================================================================
# Step 5: Verify Backend Health
# ============================================================================

log_info "=== Step 5: Verifying Backend Health ==="

# Wait a moment for the server to be fully up
sleep 2

# Check the health endpoint
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    log_success "Backend health check passed (HTTP 200)"
else
    log_error "Backend health check failed (HTTP ${HTTP_CODE})"
    log_info "Checking Gunicorn output logs..."
    cat "${APP_DIR}/gunicorn_output.log" 2>/dev/null || true
    exit 1
fi

# ============================================================================
# Step 6: Verify Nginx
# ============================================================================

log_info "=== Step 6: Verifying Nginx ==="

# Check if nginx is running
if systemctl is-active --quiet nginx; then
    log_success "Nginx is running"
else
    log_warning "Nginx is not running. Attempting to start..."
    systemctl start nginx
    systemctl enable nginx
fi

# Reload Nginx to pick up any configuration changes
log_info "Reloading Nginx configuration..."
systemctl reload nginx 2>/dev/null || true
sleep 1

# Verify application accessibility through nginx
HTTPS_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://localhost/health 2>/dev/null || echo "000")
HTTP_CODE_FALLBACK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health 2>/dev/null || echo "000")

if [ "$HTTPS_CODE" = "200" ] || [ "$HTTP_CODE_FALLBACK" = "200" ]; then
    log_success "Application is accessible through Nginx"
else
    log_warning "Application health check through Nginx returned ${HTTPS_CODE} (HTTPS) / ${HTTP_CODE_FALLBACK} (HTTP)"
    log_info "This may be expected if TLS certificates are not yet configured."
fi

# ============================================================================
# Step 7: Deployment Summary
# ============================================================================

log_info "=== Deployment Complete ==="
echo ""
echo "========================================="
echo "  DMS Deployment Summary"
echo "========================================="
echo "  Repository: $(git remote get-url "${GIT_REMOTE}" 2>/dev/null || echo "local")"
echo "  Branch: ${GIT_BRANCH}"
echo "  Commit: $(git rev-parse --short HEAD)"
echo "  Application Directory: ${APP_DIR}"
echo "  Gunicorn Workers: ${GUNICORN_WORKERS}"
echo "  Gunicorn Bind: ${GUNICORN_BIND}"
echo "  Database: Alembic migrations applied"
echo "  Status: Deployment completed"
echo ""
echo "========================================="
echo "  Verification"
echo "========================================="
echo "  Backend Health: http://127.0.0.1:8000/health"
echo "  Gunicorn PID: $(cat "${APP_DIR}/gunicorn.pid" 2>/dev/null || echo "unknown")"
echo "  Nginx Status: $(systemctl is-active nginx 2>/dev/null || echo "inactive")"
echo ""
log_success "DMS deployment completed successfully!"
echo ""

# Optional: Show the last few commits for reference
log_info "Recent Git history:"
git log --oneline -5 2>/dev/null || echo "No git history available"

exit 0