#!/usr/bin/env bash
# sync_uploads.sh
# Run on SOURCE VM (103.244.247.84) as user mchowdhury.
# Pushes folders to almalinux@123.176.58.16 via rsync over SSH.
# First run = full copy. Later runs = only changed/new files (rsync delta).

set -uo pipefail

# ---------- config ----------
DEST_USER="almalinux"
DEST_HOST="123.176.58.16"
DEST_PORT="22"
SSH_KEY="${HOME}/.ssh/id_ed25519_dms_sync"
LOG_DIR="${HOME}/logs"
LOG_FILE="${LOG_DIR}/sync_uploads.log"
LOCK_FILE="/tmp/sync_uploads.lock"
DELETE_REMOTE="no"          # "yes" = mirror deletions to dest

# Jobs: "SOURCE_FOLDER|DEST_PARENT_DIR"  (source folder is copied INTO dest parent)
JOBS=(
    "/var/www/dms/backend/storage/uploads|/opt/103.244.247.84/"                          # -> /opt/uploads
    "/var/www/dms/backend/backups_data/XFL|/opt/103.244.247.84/backups_data/"  # -> .../backups_data/XFL
)
# ----------------------------

mkdir -p "${LOG_DIR}"
log() { echo "$(date '+%F %T') $*" >> "${LOG_FILE}"; }

# prevent overlapping runs
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    log "SKIP: previous run still active"
    exit 0
fi

[[ -r "${SSH_KEY}" ]] || { log "ERROR: ssh key missing: ${SSH_KEY}"; exit 1; }

RSYNC_OPTS=(-a -z --partial --itemize-changes --stats --human-readable --timeout=300)
[[ "${DELETE_REMOTE}" == "yes" ]] && RSYNC_OPTS+=(--delete)

SSH_OPTS=(-p "${DEST_PORT}" -i "${SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=20)
SSH_CMD="ssh ${SSH_OPTS[*]}"

overall=0

for job in "${JOBS[@]}"; do
    src="${job%%|*}"
    dest="${job##*|}"

    if [[ ! -d "${src}" ]]; then
        log "ERROR: source missing: ${src}"
        overall=1
        continue
    fi

    log "START ${src} -> ${DEST_USER}@${DEST_HOST}:${dest}"

    # ensure dest parent exists (no-op if present)
    if ! ssh "${SSH_OPTS[@]}" "${DEST_USER}@${DEST_HOST}" "mkdir -p '${dest}'" >> "${LOG_FILE}" 2>&1; then
        log "FAIL: cannot create/access dest dir ${dest}"
        overall=1
        continue
    fi

    if rsync "${RSYNC_OPTS[@]}" -e "${SSH_CMD}" "${src}" "${DEST_USER}@${DEST_HOST}:${dest}" >> "${LOG_FILE}" 2>&1; then
        log "OK: ${src}"
    else
        rc=$?
        log "FAIL: rsync exit ${rc} for ${src}"
        overall=${rc}
    fi
done

exit "${overall}"
