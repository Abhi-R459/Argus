"""Backup integrity verification module for the Argus tamper-evident audit system.

Provides functions to dump the PostgreSQL database, compute streaming SHA-256
checksums, record backup metadata into the database, and verify backup
integrity against stored hashes.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import subprocess
from typing import Any

import psycopg2

logger = logging.getLogger("argus.backup")

CHUNK_SIZE = 65536  # 64 KB streaming chunk size


def _hash_file(path: str) -> str:
    """Computes the SHA-256 hex digest of a file by reading in 64KB chunks.

    Args:
        path: Path to the file to hash.

    Returns:
        The SHA-256 hex digest string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(path):
        logger.error("File not found for hashing: %s", path)
        raise FileNotFoundError(f"Backup file not found: {path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def dump_and_hash(
    db_url: str,
    output_path: str,
    manifest_path: str | None = None,
) -> str:
    """Runs pg_dump targeting the database at db_url and computes its SHA-256 hash.

    Executes pg_dump via subprocess.run, writes the SQL dump to output_path,
    and computes the SHA-256 checksum of the resulting dump file by streaming
    in 64KB chunks. If manifest_path is supplied, exports an off-host JSON
    manifest containing the computed hash, timestamp, and metadata.

    Args:
        db_url: Connection URL for the target PostgreSQL database.
        output_path: Destination file path for the SQL dump.
        manifest_path: Optional destination path to export the off-host manifest.

    Returns:
        The SHA-256 hex digest string of the generated dump file.

    Raises:
        FileNotFoundError: If pg_dump is not found on the system.
        subprocess.CalledProcessError: If pg_dump execution fails.
    """
    logger.info("Executing pg_dump for database to '%s'", output_path)
    try:
        subprocess.run(
            ["pg_dump", "-f", output_path, db_url],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        logger.error("pg_dump executable not found on system PATH")
        raise
    except subprocess.CalledProcessError as exc:
        logger.error(
            "pg_dump failed with exit code %s: %s",
            exc.returncode,
            exc.stderr,
        )
        raise

    file_hash = _hash_file(output_path)
    logger.info("Completed dump and computed SHA-256 hash: %s", file_hash)

    if manifest_path is not None:
        export_backup_manifest(
            backup_hash=file_hash,
            file_reference=output_path,
            manifest_path=manifest_path,
        )

    return file_hash


def record_backup(
    conn: psycopg2.extensions.connection,
    backup_hash: str,
    file_reference: str,
    chain_checkpoint_id: int | None = None,
) -> int:
    """Inserts a backup metadata record into the backups table.

    Uses a parameterized query to insert the backup record, commits the
    transaction, and returns the auto-generated backup_id.

    Args:
        conn: A psycopg2 database connection.
        backup_hash: The SHA-256 hex digest of the backup file.
        file_reference: File path or reference identifier for the backup.
        chain_checkpoint_id: Optional checkpoint ID to associate with the backup.

    Returns:
        The auto-generated backup_id.

    Raises:
        psycopg2.Error: If a database error occurs during the operation.
    """
    query = (
        "INSERT INTO backups (chain_checkpoint_id, backup_hash, file_reference) "
        "VALUES (%s, %s, %s) "
        "RETURNING backup_id"
    )
    logger.info(
        "Recording backup for '%s' (hash: %s, checkpoint_id: %s)",
        file_reference,
        backup_hash,
        chain_checkpoint_id,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(query, (chain_checkpoint_id, backup_hash, file_reference))
            row = cur.fetchone()
            if row is None:
                raise ValueError("Failed to retrieve auto-generated backup_id")
            backup_id = row["backup_id"] if isinstance(row, dict) else row[0]
        conn.commit()
        logger.info("Successfully recorded backup with ID %s", backup_id)
        return int(backup_id)
    except Exception:
        conn.rollback()
        raise


def export_backup_manifest(
    backup_hash: str,
    file_reference: str,
    manifest_path: str | None = None,
    chain_checkpoint_id: int | None = None,
    anchor_store: Any | None = None,
) -> str:
    """Exports backup verification metadata to an off-host manifest or external anchor store.

    Generates a cryptographically bound manifest containing the backup's SHA-256
    checksum, canonical file reference, file size, timestamp, algorithm, and optional
    checkpoint link. This manifest can be saved to an off-host filesystem path (e.g.,
    an NFS mount or isolated storage volume) or pushed to an external AnchorStore,
    preventing a compromised database host from undetectably rewriting both the backup
    and its verification record.

    Args:
        backup_hash: The SHA-256 hex digest of the backup file.
        file_reference: File path or reference identifier for the backup.
        manifest_path: Destination path for the JSON manifest. If None and no anchor_store,
            defaults to ``{file_reference}.manifest.json``.
        chain_checkpoint_id: Optional chain checkpoint ID associated with the backup.
        anchor_store: Optional AnchorStore instance to push the manifest to.

    Returns:
        The destination manifest file path or anchor reference string.
    """
    file_ref_abs = os.path.abspath(file_reference)
    manifest_data = {
        "manifest_version": "1.0",
        "backup_hash": backup_hash.strip(),
        "file_reference": file_ref_abs,
        "file_name": os.path.basename(file_reference),
        "file_size_bytes": os.path.getsize(file_reference) if os.path.exists(file_reference) else None,
        "chain_checkpoint_id": chain_checkpoint_id,
        "algorithm": "SHA-256",
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "VALID",
    }
    payload_json = json.dumps(manifest_data, indent=2)

    dest_path = manifest_path
    if dest_path is None and anchor_store is None:
        dest_path = f"{file_reference}.manifest.json"

    result_ref = ""
    if dest_path is not None:
        dir_name = os.path.dirname(os.path.abspath(dest_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(payload_json)
        logger.info("Exported backup manifest to '%s'", dest_path)
        result_ref = dest_path

    if anchor_store is not None:
        cid = chain_checkpoint_id if chain_checkpoint_id is not None else 0
        anchor_ref = anchor_store.push(cid, payload_json)
        logger.info("Pushed backup manifest to external anchor store (ref: %s)", anchor_ref)
        if not result_ref:
            result_ref = str(anchor_ref)

    return result_ref


def verify_backup_manifest(
    file_path: str,
    manifest_path: str,
) -> bool:
    """Verifies a backup file against an independent off-host manifest JSON.

    Reads the manifest JSON from manifest_path, extracts the recorded backup_hash,
    computes the SHA-256 checksum of the file at file_path, and verifies that they
    match exactly.

    Args:
        file_path: Path to the backup file on disk.
        manifest_path: Path to the independent manifest JSON file.

    Returns:
        True if the computed file hash matches the manifest's backup_hash, False otherwise.

    Raises:
        FileNotFoundError: If the manifest file or backup file does not exist.
        ValueError: If the manifest file is invalid JSON or missing 'backup_hash'.
    """
    if not os.path.exists(manifest_path):
        logger.error("Backup manifest not found: %s", manifest_path)
        raise FileNotFoundError(f"Backup manifest not found: {manifest_path}")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as exc:
        logger.error("Failed to parse backup manifest '%s': %s", manifest_path, exc)
        raise ValueError(f"Invalid backup manifest format in '{manifest_path}': {exc}") from exc

    if not isinstance(manifest, dict) or "backup_hash" not in manifest:
        logger.error("Manifest '%s' missing required 'backup_hash' field", manifest_path)
        raise ValueError(f"Manifest '{manifest_path}' missing required 'backup_hash' field")

    expected_hash = str(manifest["backup_hash"]).strip()

    if not os.path.exists(file_path):
        logger.error("Backup file not found for verification: %s", file_path)
        raise FileNotFoundError(f"Backup file not found: {file_path}")

    computed_hash = _hash_file(file_path)

    if computed_hash == expected_hash:
        logger.info(
            "Backup '%s' successfully verified against manifest '%s' (hash: %s)",
            file_path,
            manifest_path,
            computed_hash,
        )
        return True

    logger.warning(
        "Backup manifest verification failed for '%s'. Expected (manifest): %s, Computed: %s",
        file_path,
        expected_hash,
        computed_hash,
    )
    return False


def verify_backup(
    conn: psycopg2.extensions.connection,
    backup_id: int,
    manifest_path: str | None = None,
) -> bool:
    """Verifies the integrity of a backup record against its stored SHA-256 hash.

    Queries the backups table for the record with the given backup_id,
    re-computes the SHA-256 hash of the file at file_reference using 64KB
    streaming chunks, and compares the computed hash with the stored hash.
    Optionally cross-verifies against an independent off-host manifest file at manifest_path.

    Args:
        conn: A psycopg2 database connection.
        backup_id: The primary key ID of the backup record to verify.
        manifest_path: Optional path to an off-host manifest file to cross-verify against.

    Returns:
        True if the re-computed hash matches the stored hash (and manifest hash if provided),
        False otherwise.

    Raises:
        ValueError: If no backup record is found with the specified backup_id or manifest is malformed.
        FileNotFoundError: If the backup file or manifest file no longer exists on disk.
        psycopg2.Error: If a database error occurs during query execution.
    """
    query = (
        "SELECT backup_hash, file_reference "
        "FROM backups "
        "WHERE backup_id = %s"
    )
    logger.info("Verifying backup record with ID %s", backup_id)
    with conn.cursor() as cur:
        cur.execute(query, (backup_id,))
        row = cur.fetchone()

    if row is None:
        logger.error("Backup record with ID %s not found", backup_id)
        raise ValueError(f"Backup ID {backup_id} not found in database")

    if isinstance(row, dict):
        stored_hash = str(row["backup_hash"]).strip()
        file_reference = str(row["file_reference"])
    else:
        stored_hash = str(row[0]).strip()
        file_reference = str(row[1])

    if manifest_path is not None:
        if not os.path.exists(manifest_path):
            logger.error("Backup manifest not found: %s", manifest_path)
            raise FileNotFoundError(f"Backup manifest not found: {manifest_path}")
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as exc:
            logger.error("Failed to parse backup manifest '%s': %s", manifest_path, exc)
            raise ValueError(f"Invalid backup manifest format in '{manifest_path}': {exc}") from exc

        if not isinstance(manifest, dict) or "backup_hash" not in manifest:
            logger.error("Manifest '%s' missing required 'backup_hash' field", manifest_path)
            raise ValueError(f"Manifest '{manifest_path}' missing required 'backup_hash' field")

        manifest_hash = str(manifest["backup_hash"]).strip()
        if manifest_hash != stored_hash:
            logger.warning(
                "Backup ID %s stored DB hash (%s) does not match off-host manifest (%s)",
                backup_id,
                stored_hash,
                manifest_hash,
            )
            return False

    computed_hash = _hash_file(file_reference)

    if computed_hash == stored_hash:
        logger.info(
            "Backup ID %s verified successfully (hash: %s%s)",
            backup_id,
            computed_hash,
            " [verified with off-host manifest]" if manifest_path else "",
        )
        return True

    logger.warning(
        "Backup ID %s verification failed. Expected: %s, Computed: %s",
        backup_id,
        stored_hash,
        computed_hash,
    )
    return False
