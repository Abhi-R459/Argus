"""Back up and reset a confirmed loopback-only demo database.

Usage: python scripts/clean_local_data.py --confirm-local-database argus
Requires the existing argus-db-1 Docker container. Hosted URLs are refused.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values
import psycopg2
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('salary_history', 'employees', 'roles', 'departments', 'audit_log',
          'suspicious_activity_flags', 'suspicious_activity_reviews', 'security_audit_events',
          'chain_checkpoints', 'backups', 'users')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-local-database', required=True)
    args = parser.parse_args()
    values = dotenv_values(ROOT / '.env.local')
    dsn = values.get('DATABASE_URL_MIGRATIONS', '')
    url = make_url(dsn)
    if url.host not in {'localhost', '127.0.0.1'} or url.port != 5433 or url.database != args.confirm_local_database or url.database != 'argus':
        raise RuntimeError('Refusing cleanup: the target must be the confirmed local argus database on port 5433.')
    info = json.loads(subprocess.check_output(['docker', 'inspect', 'argus-db-1']))[0]
    bindings = info['NetworkSettings']['Ports']['5432/tcp']
    if not any(port['HostIp'] == '127.0.0.1' and port['HostPort'] == '5433' for port in bindings):
        raise RuntimeError('The backup container does not match the local database endpoint.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_dir = ROOT / 'backups' / ('pre-launch-cleanup-' + stamp)
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup = backup_dir / 'argus.dump'
    with backup.open('wb') as output:
        subprocess.run(['docker','exec','argus-db-1','pg_dump','-U','postgres','-Fc','-d','argus'], stdout=output, stderr=subprocess.PIPE, check=True)
    with backup.open('rb') as source:
        subprocess.run(['docker','exec','-i','argus-db-1','pg_restore','--list'], stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    manifest = {'database':'argus', 'host':'127.0.0.1:5433', 'created_at':stamp,
                'sha256':hashlib.sha256(backup.read_bytes()).hexdigest()}
    # Preserve local evidence before resetting the chain; keys stay in place.
    anchor = (ROOT / (values.get('ANCHOR_FILE_PATH') or 'anchor/local_demo/chain_anchor.log')).resolve()
    allowed_anchor_root = (ROOT / 'anchor').resolve()
    if not anchor.is_relative_to(allowed_anchor_root):
        raise RuntimeError('Refusing cleanup of an anchor outside the local workspace anchor directory.')
    evidence = sorted(path.resolve() for path in allowed_anchor_root.rglob('*') if path.is_file())
    if any(not path.is_relative_to(allowed_anchor_root) for path in evidence):
        raise RuntimeError('Refusing cleanup of evidence outside the workspace anchor directory.')
    evidence.append((ROOT / '.argus_snapshot.json').resolve())
    manifest['evidence_files'] = [str(path.relative_to(ROOT)) for path in evidence if path.is_file()]
    for index, path in enumerate(evidence):
        if path.is_file():
            (backup_dir / f'evidence-{index}-{path.name}').write_bytes(path.read_bytes())
    with psycopg2.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        assert cursor.fetchone()[0] == args.confirm_local_database
        cursor.execute("SET LOCAL lock_timeout='5s'")
        cursor.execute('SELECT pg_advisory_xact_lock(514729380123)')
        cursor.execute('TRUNCATE ' + ','.join('public.' + table for table in TABLES) + ', argus_private.actor_context_nonces RESTART IDENTITY CASCADE')
        cursor.execute("UPDATE public.chain_state SET tail_hash=%s, tail_sequence_id=0, last_checkpoint_sequence_id=0 WHERE id=1", ('0'*64,))
        cursor.execute("INSERT INTO users(user_id,clerk_user_id,full_name,email,role,is_active) VALUES (0,'argus-system-maintenance','Argus System Maintenance','system-maintenance@argus.invalid','hr_admin',false)")
        counts = {}
        for table in TABLES:
            cursor.execute('SELECT count(*) FROM public.' + table)
            counts[table] = cursor.fetchone()[0]
        if any(count for table,count in counts.items() if table != 'users') or counts['users'] != 1:
            raise RuntimeError('Cleanup verification failed; the transaction will be rolled back.')
    for path in evidence:
        if path.is_file():
            path.unlink()
    manifest['remaining_rows'] = counts
    (backup_dir / 'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Local demo records removed. Disabled system identity and cryptographic keys retained.')
    print('Verified recovery backup:', backup_dir)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Cleanup stopped:', type(exc).__name__, file=sys.stderr)
        sys.exit(1)
