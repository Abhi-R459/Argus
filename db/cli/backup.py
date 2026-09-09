"""Backup integrity verification module for the Argus tamper-evident audit system.

Provides functions to dump the PostgreSQL database, compute streaming SHA-256
checksums, record backup metadata into the database, and verify backup
integrity against stored hashes.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess

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


def dump_and_hash(db_url: str, output_path: str) -> str:
    """Runs pg_dump targeting the database at db_url and computes its SHA-256 hash.

    Executes pg_dump via subprocess.run, writes the SQL dump to output_path,
    and computes the SHA-256 checksum of the resulting dump file by streaming
    in 64KB chunks.

    Args:
        db_url: Connection URL for the target PostgreSQL database.
        output_path: Destination file path for the SQL dump.

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


def verify_backup(conn: psycopg2.extensions.connection, backup_id: int) -> bool:
    """Verifies the integrity of a backup record against its stored SHA-256 hash.

    Queries the backups table for the record with the given backup_id,
    re-computes the SHA-256 hash of the file at file_reference using 64KB
    streaming chunks, and compares the computed hash with the stored hash.

    Args:
        conn: A psycopg2 database connection.
        backup_id: The primary key ID of the backup record to verify.

    Returns:
        True if the re-computed hash matches the stored hash, False otherwise.

    Raises:
        ValueError: If no backup record is found with the specified backup_id.
        FileNotFoundError: If the backup file no longer exists on disk.
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

    computed_hash = _hash_file(file_reference)

    if computed_hash == stored_hash:
        logger.info(
            "Backup ID %s verified successfully (hash: %s)",
            backup_id,
            computed_hash,
        )
        return True

    logger.warning(
        "Backup ID %s verification failed. Expected: %s, Computed: %s",
        backup_id,
        stored_hash,
        computed_hash,
    )
    return False
