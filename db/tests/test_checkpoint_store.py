"""Unit tests for db.cli.checkpoint_store module."""

import hashlib
from unittest.mock import MagicMock, patch
import pytest

from db.cli.checkpoint_store import (
    compute_checkpoint_hash,
    get_checkpoint,
    get_checkpoints_in_range,
    store_checkpoint,
)


def test_compute_checkpoint_hash_empty():
    """Test compute_checkpoint_hash with empty list."""
    expected = hashlib.sha256(b"").hexdigest()
    assert compute_checkpoint_hash([]) == expected


def test_compute_checkpoint_hash_multiple_entries():
    """Test compute_checkpoint_hash with list of entry hashes."""
    entries = [
        "a" * 64,
        "b" * 64,
        "c" * 64,
    ]
    expected_concatenation = "".join(entries)
    expected_hash = hashlib.sha256(expected_concatenation.encode("utf-8")).hexdigest()
    result = compute_checkpoint_hash(entries)
    assert result == expected_hash
    assert len(result) == 64


def test_store_checkpoint_success():
    """Test store_checkpoint when insertion is successful (row inserted)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.rowcount = 1

    seq_id = 100
    chk_hash = "f" * 64
    sig = b"signature_bytes_12345"

    inserted = store_checkpoint(mock_conn, seq_id, chk_hash, sig)

    assert inserted is True
    mock_cur.execute.assert_called_once_with(
        "INSERT INTO chain_checkpoints (sequence_id, checkpoint_hash, signature) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (sequence_id) DO NOTHING",
        (seq_id, chk_hash, sig),
    )
    mock_conn.commit.assert_called_once()


def test_store_checkpoint_conflict():
    """Test store_checkpoint when row already exists (conflict)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.rowcount = 0

    seq_id = 100
    chk_hash = "f" * 64
    sig = b"signature_bytes_12345"

    inserted = store_checkpoint(mock_conn, seq_id, chk_hash, sig)

    assert inserted is False
    mock_conn.commit.assert_called_once()


def test_store_checkpoint_exception_rollback():
    """Test store_checkpoint triggers conn.rollback on exception."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.execute.side_effect = Exception("DB error")

    with pytest.raises(Exception, match="DB error"):
        store_checkpoint(mock_conn, 1, "a" * 64, b"sig")

    mock_conn.rollback.assert_called_once()


def test_get_checkpoint_found():
    """Test get_checkpoint when checkpoint exists."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_row = {
        "checkpoint_id": 1,
        "sequence_id": 50,
        "checkpoint_hash": "a" * 64,
        "signature": b"sig_data",
        "created_at": "2026-08-06T12:00:00Z",
    }
    mock_cur.fetchone.return_value = mock_row

    result = get_checkpoint(mock_conn, 1)

    assert result == mock_row
    assert isinstance(result, dict)
    mock_cur.execute.assert_called_once_with(
        "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
        "FROM chain_checkpoints "
        "WHERE checkpoint_id = %s",
        (1,),
    )


def test_get_checkpoint_not_found():
    """Test get_checkpoint when checkpoint does not exist."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = None

    result = get_checkpoint(mock_conn, 999)

    assert result is None


def test_get_checkpoints_in_range():
    """Test get_checkpoints_in_range returns matching checkpoints."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_rows = [
        {
            "checkpoint_id": 1,
            "sequence_id": 10,
            "checkpoint_hash": "a" * 64,
            "signature": b"sig1",
            "created_at": "2026-08-06T10:00:00Z",
        },
        {
            "checkpoint_id": 2,
            "sequence_id": 20,
            "checkpoint_hash": "b" * 64,
            "signature": b"sig2",
            "created_at": "2026-08-06T11:00:00Z",
        },
    ]
    mock_cur.fetchall.return_value = mock_rows

    results = get_checkpoints_in_range(mock_conn, 10, 20)

    assert results == mock_rows
    mock_cur.execute.assert_called_once_with(
        "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
        "FROM chain_checkpoints "
        "WHERE sequence_id BETWEEN %s AND %s "
        "ORDER BY sequence_id",
        (10, 20),
    )
