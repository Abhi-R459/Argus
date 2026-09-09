"""Unit tests for the db.cli.backup module."""

from __future__ import annotations

import hashlib
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from db.cli.backup import (
    CHUNK_SIZE,
    _hash_file,
    dump_and_hash,
    record_backup,
    verify_backup,
)


def test_hash_file_empty(tmp_path):
    """Test _hash_file on an empty file."""
    empty_file = tmp_path / "empty.sql"
    empty_file.write_bytes(b"")

    expected_hash = hashlib.sha256(b"").hexdigest()
    assert _hash_file(str(empty_file)) == expected_hash


def test_hash_file_multi_chunk(tmp_path):
    """Test _hash_file on a file larger than CHUNK_SIZE (64KB)."""
    large_file = tmp_path / "large.sql"
    # Create content larger than 64KB (e.g. 150KB)
    content = b"ArgusBackupTestData" * 10000
    assert len(content) > CHUNK_SIZE
    large_file.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    assert _hash_file(str(large_file)) == expected_hash


def test_hash_file_not_found(tmp_path):
    """Test _hash_file raises FileNotFoundError for non-existent file."""
    non_existent = tmp_path / "non_existent.sql"
    with pytest.raises(FileNotFoundError, match="Backup file not found"):
        _hash_file(str(non_existent))


def test_dump_and_hash_success(tmp_path):
    """Test dump_and_hash executes pg_dump and returns the computed hash."""
    output_file = tmp_path / "dump.sql"
    content = b"-- PostgreSQL database dump\nSELECT 1;\n"

    def fake_run(cmd, check, capture_output, text):
        assert cmd == ["pg_dump", "-f", str(output_file), "postgresql://localhost/argus"]
        assert check is True
        assert capture_output is True
        assert text is True
        output_file.write_bytes(content)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("db.cli.backup.subprocess.run", side_effect=fake_run):
        digest = dump_and_hash("postgresql://localhost/argus", str(output_file))

    expected_hash = hashlib.sha256(content).hexdigest()
    assert digest == expected_hash


def test_dump_and_hash_pg_dump_not_found(tmp_path):
    """Test dump_and_hash raises FileNotFoundError when pg_dump is not found."""
    output_file = tmp_path / "dump.sql"

    with patch("db.cli.backup.subprocess.run", side_effect=FileNotFoundError("pg_dump not found")):
        with pytest.raises(FileNotFoundError):
            dump_and_hash("postgresql://localhost/argus", str(output_file))


def test_dump_and_hash_pg_dump_failure(tmp_path):
    """Test dump_and_hash raises CalledProcessError when pg_dump fails."""
    output_file = tmp_path / "dump.sql"

    error = subprocess.CalledProcessError(1, ["pg_dump"], stderr="connection to server failed")
    with patch("db.cli.backup.subprocess.run", side_effect=error):
        with pytest.raises(subprocess.CalledProcessError):
            dump_and_hash("postgresql://localhost/argus", str(output_file))


def test_record_backup_success():
    """Test record_backup inserts record and returns auto-generated backup_id."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (42,)

    backup_hash = "a" * 64
    file_ref = "/var/backups/dump_20260831.sql"
    checkpoint_id = 10

    backup_id = record_backup(mock_conn, backup_hash, file_ref, checkpoint_id)

    assert backup_id == 42
    mock_cur.execute.assert_called_once_with(
        "INSERT INTO backups (chain_checkpoint_id, backup_hash, file_reference) "
        "VALUES (%s, %s, %s) "
        "RETURNING backup_id",
        (checkpoint_id, backup_hash, file_ref),
    )
    mock_conn.commit.assert_called_once()


def test_record_backup_dict_cursor():
    """Test record_backup handles dict-like cursor results (e.g. RealDictCursor)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = {"backup_id": 99}

    backup_hash = "b" * 64
    file_ref = "/var/backups/dump_99.sql"

    backup_id = record_backup(mock_conn, backup_hash, file_ref, None)

    assert backup_id == 99
    mock_cur.execute.assert_called_once_with(
        "INSERT INTO backups (chain_checkpoint_id, backup_hash, file_reference) "
        "VALUES (%s, %s, %s) "
        "RETURNING backup_id",
        (None, backup_hash, file_ref),
    )
    mock_conn.commit.assert_called_once()


def test_record_backup_exception_rollback():
    """Test record_backup calls rollback on exception."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.execute.side_effect = Exception("DB insert error")

    with pytest.raises(Exception, match="DB insert error"):
        record_backup(mock_conn, "c" * 64, "/path/dump.sql")

    mock_conn.rollback.assert_called_once()


def test_record_backup_no_row_returned():
    """Test record_backup raises ValueError if no row is returned."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = None

    with pytest.raises(ValueError, match="Failed to retrieve auto-generated backup_id"):
        record_backup(mock_conn, "d" * 64, "/path/dump.sql")

    mock_conn.rollback.assert_called_once()


def test_verify_backup_success(tmp_path):
    """Test verify_backup returns True when file hash matches stored hash."""
    backup_file = tmp_path / "valid_backup.sql"
    content = b"-- Valid backup content\n"
    backup_file.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (expected_hash, str(backup_file))

    result = verify_backup(mock_conn, 1)

    assert result is True
    mock_cur.execute.assert_called_once_with(
        "SELECT backup_hash, file_reference "
        "FROM backups "
        "WHERE backup_id = %s",
        (1,),
    )


def test_verify_backup_dict_cursor(tmp_path):
    """Test verify_backup with dict cursor and matching hash."""
    backup_file = tmp_path / "valid_backup_dict.sql"
    content = b"-- Valid backup content dict\n"
    backup_file.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = {
        "backup_hash": f"{expected_hash}   ",  # test padding stripping
        "file_reference": str(backup_file),
    }

    result = verify_backup(mock_conn, 5)

    assert result is True


def test_verify_backup_mismatch(tmp_path):
    """Test verify_backup returns False when file hash does not match stored hash."""
    backup_file = tmp_path / "corrupted_backup.sql"
    backup_file.write_bytes(b"tampered content")

    stored_hash = "e" * 64

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (stored_hash, str(backup_file))

    result = verify_backup(mock_conn, 2)

    assert result is False


def test_verify_backup_not_found():
    """Test verify_backup raises ValueError when backup_id does not exist."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = None

    with pytest.raises(ValueError, match="Backup ID 999 not found in database"):
        verify_backup(mock_conn, 999)


def test_verify_backup_file_not_found():
    """Test verify_backup raises FileNotFoundError when backup file is missing."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = ("a" * 64, "/non/existent/path/backup.sql")

    with pytest.raises(FileNotFoundError, match="Backup file not found"):
        verify_backup(mock_conn, 3)
