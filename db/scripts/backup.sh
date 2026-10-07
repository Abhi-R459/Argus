#!/bin/sh
set -eu

# Produce a self-contained custom-format backup and checksum manifest. The
# temporary directory and final directory share a filesystem so publication is
# an atomic rename; incomplete dumps are never presented as completed backups.
umask 077
: "${BACKUP_DIR:?BACKUP_DIR is required}"
: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

mkdir -p "$BACKUP_DIR"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
final_dir="$BACKUP_DIR/argus-$timestamp"
if [ -e "$final_dir" ]; then
    echo "Backup destination already exists: $final_dir" >&2
    exit 1
fi

temp_dir=$(mktemp -d "$BACKUP_DIR/.argus-backup.XXXXXX")
cleanup() {
    if [ -n "${temp_dir:-}" ] && [ -d "$temp_dir" ]; then
        rm -rf "$temp_dir"
    fi
}
trap cleanup EXIT HUP INT TERM

archive="$temp_dir/backup.dump"
pg_dump --format=custom --compress=6 --no-owner --no-acl --file="$archive"
(cd "$temp_dir" && sha256sum backup.dump > backup.dump.sha256)
printf '{\n  "manifest_version": "1.0",\n  "database": "%s",\n  "created_at_utc": "%s",\n  "format": "postgresql-custom",\n  "archive": "backup.dump",\n  "sha256_file": "backup.dump.sha256"\n}\n' \
    "$PGDATABASE" "$timestamp" > "$temp_dir/manifest.json"

mv "$temp_dir" "$final_dir"
temp_dir=
printf 'Backup created: %s\n' "$final_dir"
