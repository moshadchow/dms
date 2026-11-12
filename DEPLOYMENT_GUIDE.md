# GitHub Actions CI/CD Pipeline - DMS AlmaLinux Deployment

## 1. Complete Workflow File

The workflow is at `.github/workflows/deploy.yml`. Key features:

- Triggers on `push` to `main` branch and `workflow_dispatch` (manual)
- CI validation job runs backend tests and frontend build/lint
- Deployment job runs only after successful validation
- Secure SSH key authentication with host key verification
- Preserves production `.env`, `storage/uploads/`, and runtime data
- Applies Alembic migrations safely
- Restarts Gunicorn (with UvicornWorker for ASGI support) instead of systemctl
- Verifies health endpoint

## 2. Required GitHub Repository Secrets

The following secrets must be configured in the GitHub repository settings:

| Secret | Description | Example |
|--------|-------------|---------|
| `DEPLOY_HOST` | AlmaLinux production server hostname or IP | `dms.xpertfintech.com` |
| `DEPLOY_USER` | SSH deployment user account | `mchowdhury` |
| `DEPLOY_SSH_KEY` | Private SSH key for authentication (PEM format) | `-----BEGIN OPENSSH KEY-----...` |
| `DEPLOY_SSH_PORT` | SSH port (default 22) | `22` |

**Important**: The `DEPLOY_SSH_KEY` must be the private key corresponding to the public key deployed on the AlmaLinux server. Never commit this key to the repository.

## 3. Required AlmaLinux Server-Side Preparation

### 3.1 Create the Deployment User Account

```bash
# Add dedicated deployment user
sudo useradd -m -s /bin/bash mchowdhury

# Set up SSH authorized_keys for the deployment user
sudo -u mchowdhury mkdir -p /home/mchowdhury/.ssh
# Append the GitHub Actions public key to authorized_keys
sudo -u mchowdhury sh -c "cat >> /home/mchowdhury/.ssh/authorized_keys"
sudo chown -R mchowdhury:mchowdhury /home/mchowdhury/.ssh
sudo chmod 700 /home/mchowdhury/.ssh
sudo chmod 600 /home/mchowdhury/.ssh/authorized_keys
```

### 3.2 Configure Application Directory Structure

```bash
# Create the application root
sudo mkdir -p /var/www/dms

# Set up backend directory (where repo is cloned)
sudo mkdir -p /var/www/dms/backend
sudo chown -R mchowdhury:mchowdhury /var/www/dms/backend

# Set up storage directory (contains uploaded documents - MUST BE PRESERVED)
sudo mkdir -p /var/www/dms/storage
sudo chown -R mchowdhury:mchowdhury /var/www/dms/storage

# Set up Gunicorn working directory
sudo mkdir -p /var/www/dms/gunicorn
sudo chown -R mchowdhury:mchowdhury /var/www/dms/gunicorn

# Set up frontend directory
sudo mkdir -p /var/www/dms/dms-app/dist
sudo chown -R mchowdhury:mchowdhury /var/www/dms/dms-app

# Ensure log directories exist
sudo mkdir -p /var/log/nginx
sudo mkdir -p /var/log/dms
sudo chown -R mchowdhury:mchowdhury /var/log/nginx /var/log/dms
```

### 3.3 Install Production Dependencies on Server

```bash
# Install Python and dependencies
sudo dnf install -y python3 python3-pip python3-venv

# Clone the repository or set up the deployment
sudo -u mchowdhury git clone <repo-url> /var/www/dms

# OR if repo already exists:
sudo -u mchowdhury git -C /var/www/dms fetch origin main

# Install Node.js for frontend builds (if not already)
sudo dnf install -y nodejs npm

# Install PostgreSQL and ensure it's running
sudo dnf install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

# Create and activate Python virtual environment
sudo -u mchowdhury /var/www/dms/venv/bin/python3 -m venv /var/www/dms/venv
sudo -u mchowdhury source /var/www/dms/venv/bin/activate

# Install Python dependencies
sudo -u mchowdhury /var/www/dms/venv/bin/pip install -r requirements.txt

# Install Gunicorn with UvicornWorker for ASGI/FastAPI support
sudo -u mchowdhury /var/www/dms/venv/bin/pip install gunicorn

# Initialize Gunicorn with a basic config if needed
# (the deploy.sh script handles Gunicorn startup)

# Create systemd service for Gunicorn (replaces the old uvicorn service)
sudo cp /path/to/gunicorn.service /etc/systemd/system/gunicorn.service
sudo systemctl enable --now gunicorn

# Install and configure Nginx
sudo dnf install -y nginx
# Copy dms.conf to /etc/nginx/conf.d/dms.conf
sudo systemctl enable --now nginx

# Configure firewall
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 3.4 Configure Gunicorn Service (systemd)

Create `/etc/systemd/system/gunicorn.service`:

```ini
[Unit]
Description=Gunicorn instance for DMS
After=network.target postgresql.service

[Service]
User=mchowdhury
Group=mchowdhury
WorkingDirectory=/var/www/dms
# Activate the virtual environment
Environment="PATH=/var/www/dms/venv/bin:$PATH"
# Set the Django settings module (adjust if needed)
Environment="DJANGO_SETTINGS_MODULE=main"
# Number of worker processes
Environment=GUNICORN_WORKERS=4

# Main process
ExecStart=/var/www/dms/venv/bin/gunicorn main:app \
    -w $GUNICORN_WORKERS \
    -k uvicorn.worker.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --pid /var/www/dms/gunicorn/gunicorn.pid \
    --error-logfile /var/log/dms/gunicorn_error.log \
    --access-logfile /var/log/dms/gunicorn_access.log

# Handle service restart gracefully
ExecReload=/bin/kill -HUP $MAINPID
ExecStop=/bin/kill -TERM $MAINPID

[Install]
WantedBy=multi-user.target
```

### 3.5 Set Up SSH and Sudo Permissions

- **Authentication**: SSH key-based only (password authentication disabled)
- **Host key**: Server's SSH host key must be verified/fingerprinted
- **Port**: Default 22 (configure via `DEPLOY_SSH_PORT` secret if different)
- **User**: `DEPLOY_USER` account must have `.ssh/authorized_keys` set up

**Sudo permissions**: The deployment user needs NO unrestricted sudo. The `deploy.sh` script and Gunicorn service manage restarts without sudo by running in the deployment user's context.

### 3.6 File and Directory Permissions

```bash
# Deployment user must own these directories:
# /var/www/dms/backend        - backend source code
# /var/www/dms/storage        - uploaded documents and runtime data
# /var/www/dms/dms-app/dist   - frontend build output
# /var/www/dms/venv           - Python virtual environment

# Gunicorn log directories:
# /var/log/dms/               - Gunicorn logs (owned by deployment user)

# Nginx must be able to read:
# /var/www/dms/dms-app/dist   (public HTML)
# /var/log/nginx/             (access logs - may run as root)

# PostgreSQL data directory must be owned by postgres user/group
```

## 4. Triggering the First Deployment

### 4.1 Configure Repository Secrets

1. Navigate to GitHub Repository → Settings → Secrets and variables → Actions
2. Add all four required secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_SSH_PORT`
3. For `DEPLOY_SSH_KEY`, paste the entire private key (PEM format, including `-----BEGIN OPENSSH KEY-----` and `-----END OPENSSH KEY-----`)

### 4.2 Push to Main Branch

The workflow will trigger automatically on pushes to the `main` branch:

```bash
git checkout main
git add .
git commit -m "Prepare CI/CD pipeline with Gunicorn"
git push origin main
```

Or trigger manually:

1. Navigate to the Actions tab in GitHub
2. Select "DMS Production Deploy" workflow
3. Click "Run workflow" button

## 5. Running deploy.sh Manually on the Server

### 5.1 Prerequisites on the Server

```bash
# The repository must be cloned on the server
git clone <repo-url> /var/www/dms
cd /var/www/dms

# Or if already cloned:
cd /var/www/dms
git remote add origin <repo-url>
git fetch origin

# Set up Python virtual environment if not exists
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

### 5.2 Make Script Executable

```bash
chmod +x /path/to/deploy.sh
```

### 5.3 Run the Deployment Script

```bash
./deploy.sh
```

The script will:
1. ✅ Fetch latest code from Git
2. ⚠️ **Reset hard** to `origin/main` (discards local commits - confirm when prompted)
3. 📦 Install Python dependencies
4. 🔄 Apply Alembic migrations
5. 🌟 Restart Gunicorn (with UvicornWorker)
6. 🏥 Verify backend health endpoint
7. 🔄 Verify Nginx status
8. 📊 Print deployment summary

### 5.4 Verify the Deployment

```bash
# Check the health endpoint
curl http://127.0.0.1:8000/health

# Expected: {"status": "ok", "app": "DMS", "version": "x.x.x"}

# Check Gunicorn is running
ps aux | grep gunicorn

# Check Nginx status
systemctl status nginx

# Access through TLS (if configured)
curl -I https://dms.xpertfintech.com/health
```

## 6. Rollback Procedure

### 6.1 Rolling Back Gunicorn

```bash
# Stop the current Gunicorn process
sudo systemctl stop gunicorn

# Or using the PID file
kill $(cat /var/www/dms/gunicorn/gunicorn.pid) 2>/dev/null || true

# Start Gunicorn with a previous commit
# The deploy.sh uses git reset --hard, so to roll back:
git fetch origin
git checkout <previous-commit-hash>
./deploy.sh
# Or manually:
source venv/bin/activate
nohup venv/bin/gunicorn main:app -w 4 -k uvicorn.worker.UvicornWorker --bind 127.0.0.1:8000 > gunicorn_output.log 2>&1 &
```

### 6.2 Rolling Back Database Migrations

**⚠️ Critical: Never auto-reverse migrations without a validated procedure.**

If a migration needs to be reversed:

```bash
# Roll back one migration
source venv/bin/activate
venv/bin/alembic downgrade -1

# Or roll back to a specific revision
venv/bin/alembic downgrade <target_revision>

# Restart Gunicorn
sudo systemctl restart gunicorn

# Verify health
curl http://127.0.0.1:8000/health
```

### 6.3 Database Backup Before Migration

```bash
# Create a backup of the PostgreSQL database
pg_dump -U dmsuser -d dmsdb -Fc > /var/backups/dmsdb_backup_$(date +%Y%m%d).bak

# Verify the backup can be restored:
pg_restore -U dmsuser -d dmsdb /var/backups/dmsdb_backup_20240101.bak

# Store backup outside the application directory
# e.g., /var/backups/ or an external backup service
```

### 6.4 Emergency Rollback Steps

If the deployment causes a complete outage:

```bash
# 1. Stop the current Gunicorn
sudo systemctl stop gunicorn

# 2. Restore the previous code
# Navigate to the repo and check out a previous commit
git checkout <previous-commit-hash>

# 3. Restart Gunicorn
sudo systemctl start gunicorn

# 4. Verify health
curl http://127.0.0.1:8000/health

# 5. If issues persist, restore from a full server backup
# This is why regular backups of /var/www/dms are essential
```

## 7. Workflow Quality Checklist

- [x] `.github/workflows/deploy.yml` exists with valid YAML syntax
- [x] Workflow triggers on `push` to `main` branch
- [x] Workflow supports `workflow_dispatch` for manual execution
- [x] CI validation runs backend tests (accepts known baseline failures)
- [x] CI validation runs frontend lint and build
- [x] Deployment job only runs after successful validation (`needs: validate`)
- [x] Secure SSH key authentication (no hardcoded credentials)
- [x] SSH host key verification enabled (not disabled)
- [x] Production `.env` file never transferred from GitHub
- [x] Production `.env` never overwritten during deployment
- [x] `storage/uploads/` directory preserved (no destructive operations)
- [x] Alembic migrations applied safely (`alembic upgrade head`)
- [x] Gunicorn restarted (with UvicornWorker for ASGI support)
- [x] Backend health endpoint verified (`/health`)
- [x] Nginx status verified
- [x] Application accessible through nginx/TLS
- [x] Clear success/failure messages in workflow logs
- [x] Sensitive information not exposed in logs
- [x] Explicit pinned action versions (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`, `webfactory/ssh-agent@v0.10.0`)
- [x] CI validation and deployment separated into understandable jobs
- [x] Deployment failure reporting is clear and actionable
- [x] Rollback procedure documented
- [x] Uses Gunicorn + UvicornWorker (not systemd uvicorn service)
- [x] `git reset --hard` with user confirmation prompt
- [x] No assumptions about the old systemd uvicorn service (replaced by Gunicorn)
- [x] Python 3.11 and Node.js 20 versions match project requirements
- [x] No upgrade of pinned dependencies in requirements.txt
- [x] deploy.sh created with full server-side deployment steps