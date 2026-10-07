#!/bin/sh
set -eu

# This helper only restores to a new, empty staging database. Production
# restores must follow the operator's tested provider-specific recovery plan.
umask 077
backup_dir=${1:-}
: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE must name an empty staging database}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${ARGUS_RESTORE_CONFIRM:?Set ARGUS_RESTORE_CONFIRM to RESTORE:<target database>}"

case "$PGDATABASE" in
    argus_restore_*) ;;
    *) echo "Refusing restore: target must start with argus_restore_." >&2; exit 2 ;;
esac
if [ "$ARGUS_RESTORE_CONFIRM" != "RESTORE:$PGDATABASE" ]; then
    echo "Refusing restore: confirmation must exactly match RESTORE:$PGDATABASE." >&2
    exit 2
fi
if [ -z "$backup_dir" ] || [ ! -d "$backup_dir" ]; then
    echo "Provide an existing backup directory." >&2
    exit 2
fi

archive="$backup_dir/backup.dump"
manifest="$backup_dir/manifest.json"
checksum="$backup_dir/backup.dump.sha256"
for path in "$archive" "$manifest" "$checksum"; do
    if [ ! -f "$path" ]; then
        echo "Required backup artifact is missing: $path" >&2
        exit 2
    fi
done

(cd "$backup_dir" && sha256sum -cs backup.dump.sha256) || {
    echo "Backup checksum verification failed." >&2
    exit 1
}
grep -Fq '"archive": "backup.dump"' "$manifest" || {
    echo "Backup manifest does not describe the expected archive." >&2
    exit 1
}
pg_restore --list "$archive" >/dev/null

object_count=$(psql --no-psqlrc --tuples-only --no-align --set ON_ERROR_STOP=1 \
    --command="SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')) + (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%') + (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND t.typtype <> 'c') + (SELECT count(*) FROM pg_namespace n WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'public') AND n.nspname NOT LIKE 'pg_toast%')")
if [ "$object_count" != "0" ]; then
    echo "Refusing restore: target '$PGDATABASE' contains user database objects." >&2
    exit 2
fi

pg_restore --exit-on-error --no-owner --no-privileges --dbname="$PGDATABASE" "$archive"
printf 'Restore completed into empty staging database: %s\n' "$PGDATABASE"
