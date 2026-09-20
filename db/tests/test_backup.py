"""Unit tests for the db.cli.backup module."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from db.cli.anchor_store import LocalFileAnchorStore
from db.cli.backup import (
    CHUNK_SIZE,
    _hash_file,
    dump_and_hash,
    export_backup_manifest,
    record_backup,
    verify_backup,
    verify_backup_manifest,
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


def test_export_backup_manifest_default_path(tmp_path):
    """Test export_backup_manifest generates default manifest file when path is not specified."""
    backup_file = tmp_path / "argus_backup.sql"
    backup_file.write_bytes(b"-- Dump data\n")
    digest = hashlib.sha256(b"-- Dump data\n").hexdigest()

    manifest_dest = export_backup_manifest(
        backup_hash=digest,
        file_reference=str(backup_file),
        chain_checkpoint_id=7,
    )

    expected_manifest_path = tmp_path / "argus_backup.sql.manifest.json"
    assert manifest_dest == str(expected_manifest_path)
    assert expected_manifest_path.exists()

    with open(expected_manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["manifest_version"] == "1.0"
    assert data["backup_hash"] == digest
    assert data["file_reference"] == os.path.abspath(str(backup_file))
    assert data["file_name"] == "argus_backup.sql"
    assert data["file_size_bytes"] == len(b"-- Dump data\n")
    assert data["chain_checkpoint_id"] == 7
    assert data["algorithm"] == "SHA-256"
    assert "exported_at" in data
    assert data["status"] == "VALID"


def test_export_backup_manifest_custom_path(tmp_path):
    """Test export_backup_manifest creates custom off-host directory and writes manifest."""
    backup_file = tmp_path / "db.sql"
    backup_file.write_bytes(b"DATA")
    digest = hashlib.sha256(b"DATA").hexdigest()

    off_host_dir = tmp_path / "off_host_anchors"
    custom_manifest_path = off_host_dir / "db_manifest.json"

    result_path = export_backup_manifest(
        backup_hash=digest,
        file_reference=str(backup_file),
        manifest_path=str(custom_manifest_path),
    )

    assert result_path == str(custom_manifest_path)
    assert custom_manifest_path.exists()

    with open(custom_manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["backup_hash"] == digest


def test_export_backup_manifest_with_anchor_store(tmp_path):
    """Test export_backup_manifest integrates with an external AnchorStore."""
    anchor_dir = tmp_path / "anchors"
    anchor_store = LocalFileAnchorStore(str(anchor_dir))

    backup_file = tmp_path / "snapshot.sql"
    backup_file.write_bytes(b"SNAPSHOT")
    digest = hashlib.sha256(b"SNAPSHOT").hexdigest()

    result_ref = export_backup_manifest(
        backup_hash=digest,
        file_reference=str(backup_file),
        chain_checkpoint_id=12,
        anchor_store=anchor_store,
    )

    # Verify anchor store received it
    assert anchor_store.verify(12) is True
    # Anchor file exists
    assert (anchor_dir / "12.json").exists()


def test_verify_backup_manifest_success(tmp_path):
    """Test verify_backup_manifest returns True when backup file matches manifest digest."""
    backup_file = tmp_path / "prod.sql"
    content = b"PROD_DATABASE_DUMP"
    backup_file.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()

    manifest_file = tmp_path / "prod.manifest.json"
    export_backup_manifest(
        backup_hash=digest,
        file_reference=str(backup_file),
        manifest_path=str(manifest_file),
    )

    assert verify_backup_manifest(str(backup_file), str(manifest_file)) is True


def test_verify_backup_manifest_tampered(tmp_path):
    """Test verify_backup_manifest returns False when backup file has been modified."""
    backup_file = tmp_path / "tampered.sql"
    backup_file.write_bytes(b"ORIGINAL_BACKUP")
    digest = hashlib.sha256(b"ORIGINAL_BACKUP").hexdigest()

    manifest_file = tmp_path / "tampered.manifest.json"
    export_backup_manifest(
        backup_hash=digest,
        file_reference=str(backup_file),
        manifest_path=str(manifest_file),
    )

    # Tamper with the backup file
    backup_file.write_bytes(b"MALICIOUS_MODIFICATION")

    assert verify_backup_manifest(str(backup_file), str(manifest_file)) is False


def test_verify_backup_manifest_missing_files(tmp_path):
    """Test verify_backup_manifest raises FileNotFoundError if file or manifest is missing."""
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps({"backup_hash": "a" * 64}))

    with pytest.raises(FileNotFoundError, match="Backup manifest not found"):
        verify_backup_manifest(str(tmp_path / "file.sql"), str(tmp_path / "nonexistent.json"))

    with pytest.raises(FileNotFoundError, match="Backup file not found"):
        verify_backup_manifest(str(tmp_path / "nonexistent.sql"), str(manifest_file))


def test_verify_backup_manifest_malformed_json(tmp_path):
    """Test verify_backup_manifest raises ValueError on corrupt manifest or missing hash."""
    backup_file = tmp_path / "file.sql"
    backup_file.write_bytes(b"DATA")

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("NOT_VALID_JSON{")
    with pytest.raises(ValueError, match="Invalid backup manifest format"):
        verify_backup_manifest(str(backup_file), str(bad_json))

    missing_hash = tmp_path / "missing_hash.json"
    missing_hash.write_text(json.dumps({"key": "val"}))
    with pytest.raises(ValueError, match="missing required 'backup_hash' field"):
        verify_backup_manifest(str(backup_file), str(missing_hash))


def test_verify_backup_cross_verify_manifest_match(tmp_path):
    """Test verify_backup with manifest_path succeeds when DB hash, file, and manifest match."""
    backup_file = tmp_path / "verified.sql"
    content = b"SECURE_BACKUP_STREAM"
    backup_file.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()

    manifest_file = tmp_path / "verified.manifest.json"
    export_backup_manifest(
        backup_hash=expected_hash,
        file_reference=str(backup_file),
        manifest_path=str(manifest_file),
    )

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (expected_hash, str(backup_file))

    result = verify_backup(mock_conn, 10, manifest_path=str(manifest_file))
    assert result is True


def test_verify_backup_cross_verify_db_tampered(tmp_path):
    """Test verify_backup fails when DB record is tampered relative to off-host manifest."""
    backup_file = tmp_path / "unmodified.sql"
    content = b"CLEAN_FILE"
    backup_file.write_bytes(content)
    real_hash = hashlib.sha256(content).hexdigest()

    # Off-host manifest has the real hash
    manifest_file = tmp_path / "offsite.manifest.json"
    export_backup_manifest(
        backup_hash=real_hash,
        file_reference=str(backup_file),
        manifest_path=str(manifest_file),
    )

    # Rogue DBA updated backups table to a forged hash
    forged_db_hash = "f" * 64
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (forged_db_hash, str(backup_file))

    # Cross verification fails because DB hash doesn't match off-host manifest!
    result = verify_backup(mock_conn, 10, manifest_path=str(manifest_file))
    assert result is False


def test_dump_and_hash_with_manifest_export(tmp_path):
    """Test dump_and_hash automatically exports manifest when manifest_path is provided."""
    output_file = tmp_path / "dump.sql"
    manifest_file = tmp_path / "dump.manifest.json"
    content = b"-- Dump with manifest\n"

    def fake_run(cmd, check, capture_output, text):
        output_file.write_bytes(content)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("db.cli.backup.subprocess.run", side_effect=fake_run):
        digest = dump_and_hash(
            "postgresql://localhost/argus",
            str(output_file),
            manifest_path=str(manifest_file),
        )

    expected_hash = hashlib.sha256(content).hexdigest()
    assert digest == expected_hash
    assert manifest_file.exists()

    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["backup_hash"] == expected_hash


def test_cli_backup_dump_and_verify_manifest_e2e(tmp_path, monkeypatch, capsys):
    """Test CLI commands for dump and verify using off-host manifests."""
    from db.cli.verifier import main

    dump_file = tmp_path / "cli_dump.sql"
    manifest_file = tmp_path / "cli_manifest.json"
    content = b"CLI_DUMP_CONTENT"

    def fake_run(cmd, check, capture_output, text):
        dump_file.write_bytes(content)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (101,)

    with patch("db.cli.backup.subprocess.run", side_effect=fake_run):
        with patch("db.cli.verifier.get_connection", return_value=mock_conn):
            monkeypatch.setattr(
                "sys.argv",
                [
                    "argus-verifier",
                    "backup",
                    "dump",
                    "--output",
                    str(dump_file),
                    "--manifest-path",
                    str(manifest_file),
                    "--db-url",
                    "postgresql://postgres:password@localhost:5433/argus",
                ],
            )
            exit_code = main()

    assert exit_code == 0
    assert manifest_file.exists()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["event"] == "backup_created"
    assert data["manifest_path"] == os.path.abspath(str(manifest_file))

    # Test CLI standalone off-host verification without DB
    monkeypatch.setattr(
        "sys.argv",
        [
            "argus-verifier",
            "backup",
            "verify",
            "--file",
            str(dump_file),
            "--manifest-path",
            str(manifest_file),
        ],
    )
    exit_code_verify = main()
    assert exit_code_verify == 0
    out_verify = capsys.readouterr().out
    assert "backup_manifest_verified" in out_verify
    assert "VALID" in out_verify

