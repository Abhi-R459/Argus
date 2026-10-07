import datetime
import hashlib
import json
from unittest.mock import MagicMock, patch
import pytest

from db.cli.checkpoint_store import (
    compute_checkpoint_hash,
    create_dual_trigger_checkpoint,
    get_all_checkpoints,
    get_checkpoint,
    get_checkpoints_in_range,
    get_latest_checkpoint,
    get_uncheckpointed_entries,
    should_create_checkpoint,
    store_checkpoint,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_SECONDS,
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


def test_get_all_checkpoints():
    """Test get_all_checkpoints returns all checkpoints ordered by sequence_id."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.return_value = [{"checkpoint_id": 1, "sequence_id": 25}]

    rows = get_all_checkpoints(mock_conn)
    assert len(rows) == 1
    assert rows[0]["sequence_id"] == 25


def test_get_latest_checkpoint_found():
    """Test get_latest_checkpoint returns the newest checkpoint by sequence_id."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = {
        "checkpoint_id": 5,
        "sequence_id": 125,
        "checkpoint_hash": "c" * 64,
        "signature": b"sig",
        "created_at": datetime.datetime(2026, 8, 6, 12, 0, 0, tzinfo=datetime.timezone.utc),
    }

    latest = get_latest_checkpoint(mock_conn)
    assert latest is not None
    assert latest["sequence_id"] == 125


def test_get_latest_checkpoint_none():
    """Test get_latest_checkpoint returns None when no checkpoints exist."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = None

    assert get_latest_checkpoint(mock_conn) is None


def test_get_uncheckpointed_entries():
    """Test get_uncheckpointed_entries returns audit log entries after given sequence."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.return_value = [
        {"sequence_id": 101, "entry_hash": "a" * 64, "created_at": datetime.datetime.now(datetime.timezone.utc)},
        {"sequence_id": 102, "entry_hash": "b" * 64, "created_at": datetime.datetime.now(datetime.timezone.utc)},
    ]

    entries = get_uncheckpointed_entries(mock_conn, last_checkpoint_seq=100)
    assert len(entries) == 2
    assert entries[0]["sequence_id"] == 101
    mock_cur.execute.assert_called_once()


def test_should_create_checkpoint_no_entries():
    """Test should_create_checkpoint returns False when there are 0 uncheckpointed entries."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Mock get_latest_checkpoint returning seq=50
    mock_cur.fetchone.return_value = {
        "checkpoint_id": 1,
        "sequence_id": 50,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
    }
    # Mock get_uncheckpointed_entries returning empty
    mock_cur.fetchall.return_value = []

    should_fire, reason, details = should_create_checkpoint(mock_conn)
    assert should_fire is False
    assert reason == "no_entries"
    assert details["entries_since"] == 0


def test_should_create_checkpoint_entry_count_threshold():
    """Test should_create_checkpoint fires when entry count reaches max_entries (25)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    now = datetime.datetime(2026, 8, 6, 12, 0, 10, tzinfo=datetime.timezone.utc)
    # Checkpoint created 10 seconds ago (< 60s)
    mock_cur.fetchone.return_value = {
        "checkpoint_id": 1,
        "sequence_id": 50,
        "created_at": datetime.datetime(2026, 8, 6, 12, 0, 0, tzinfo=datetime.timezone.utc),
    }

    # 25 uncheckpointed entries accumulated
    fake_entries = [
        {"sequence_id": 50 + i, "entry_hash": "a" * 64, "created_at": now}
        for i in range(1, 26)
    ]
    mock_cur.fetchall.return_value = fake_entries

    should_fire, reason, details = should_create_checkpoint(
        mock_conn,
        max_entries=25,
        max_seconds=60.0,
        current_time=now,
    )
    assert should_fire is True
    assert reason == "entry_count_threshold"
    assert details["entries_since"] == 25


def test_should_create_checkpoint_time_elapsed_threshold():
    """Test should_create_checkpoint fires when elapsed time exceeds max_seconds (60s)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Checkpoint created 75 seconds ago (> 60s)
    cp_time = datetime.datetime(2026, 8, 6, 12, 0, 0, tzinfo=datetime.timezone.utc)
    current_time = datetime.datetime(2026, 8, 6, 12, 1, 15, tzinfo=datetime.timezone.utc)

    mock_cur.fetchone.return_value = {
        "checkpoint_id": 1,
        "sequence_id": 50,
        "created_at": cp_time,
    }

    # Only 3 uncheckpointed entries (< 25)
    fake_entries = [
        {"sequence_id": 51, "entry_hash": "a" * 64, "created_at": cp_time},
        {"sequence_id": 52, "entry_hash": "b" * 64, "created_at": cp_time},
        {"sequence_id": 53, "entry_hash": "c" * 64, "created_at": cp_time},
    ]
    mock_cur.fetchall.return_value = fake_entries

    should_fire, reason, details = should_create_checkpoint(
        mock_conn,
        max_entries=25,
        max_seconds=60.0,
        current_time=current_time,
    )
    assert should_fire is True
    assert reason == "time_elapsed_threshold"
    assert details["entries_since"] == 3
    assert details["seconds_since"] == 75.0


def test_should_create_checkpoint_threshold_not_reached():
    """Test should_create_checkpoint returns False when neither count nor time threshold is met."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Checkpoint created 20 seconds ago (< 60s)
    cp_time = datetime.datetime(2026, 8, 6, 12, 0, 0, tzinfo=datetime.timezone.utc)
    current_time = datetime.datetime(2026, 8, 6, 12, 0, 20, tzinfo=datetime.timezone.utc)

    mock_cur.fetchone.return_value = {
        "checkpoint_id": 1,
        "sequence_id": 50,
        "created_at": cp_time,
    }

    # Only 5 entries (< 25)
    fake_entries = [
        {"sequence_id": 50 + i, "entry_hash": "a" * 64, "created_at": cp_time}
        for i in range(1, 6)
    ]
    mock_cur.fetchall.return_value = fake_entries

    should_fire, reason, details = should_create_checkpoint(
        mock_conn,
        max_entries=25,
        max_seconds=60.0,
        current_time=current_time,
    )
    assert should_fire is False
    assert reason == "threshold_not_reached"
    assert details["entries_since"] == 5
    assert details["seconds_since"] == 20.0


def test_create_dual_trigger_checkpoint_success():
    """Test create_dual_trigger_checkpoint creates and records checkpoint when triggered."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.rowcount = 1

    # First fetchone: latest checkpoint (seq=0)
    # Second fetchall: uncheckpointed rows
    # Third fetchone: retrieved inserted checkpoint row
    cp_row = {
        "checkpoint_id": 1,
        "sequence_id": 25,
        "checkpoint_hash": "d" * 64,
        "signature": b"\x00" * 64,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
    }
    mock_cur.fetchone.side_effect = [None, cp_row]

    fake_entries = [
        {"sequence_id": i, "entry_hash": f"{i:064x}", "created_at": datetime.datetime.now(datetime.timezone.utc)}
        for i in range(1, 26)
    ]
    # Two fetchall calls: one for should_create_checkpoint, one for creation fetch
    mock_cur.fetchall.side_effect = [fake_entries, fake_entries]

    result = create_dual_trigger_checkpoint(mock_conn, max_entries=25)

    assert result is not None
    assert result["event"] == "checkpoint_created"
    assert result["checkpoint_sequence_id"] == 25
    assert result["entries_in_range"] == 25
    assert result["trigger_reason"] == "entry_count_threshold"


def test_create_dual_trigger_checkpoint_with_signer():
    """Test create_dual_trigger_checkpoint invokes provided signer."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.rowcount = 1

    mock_cur.fetchone.side_effect = [
        None,
        {"checkpoint_id": 1, "sequence_id": 25, "checkpoint_hash": "e" * 64, "signature": b"custom_sig", "created_at": datetime.datetime.now(datetime.timezone.utc)},
    ]
    fake_entries = [
        {"sequence_id": i, "entry_hash": f"{i:064x}", "created_at": datetime.datetime.now(datetime.timezone.utc)}
        for i in range(1, 26)
    ]
    mock_cur.fetchall.side_effect = [fake_entries, fake_entries]

    custom_signer = MagicMock()
    custom_signer.sign.return_value = b"custom_signature_bytes"

    result = create_dual_trigger_checkpoint(mock_conn, max_entries=25, signer=custom_signer)

    assert result is not None
    custom_signer.sign.assert_called_once()


def test_create_dual_trigger_checkpoint_skipped():
    """Test create_dual_trigger_checkpoint returns None when conditions are not satisfied."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_cur.fetchone.return_value = {
        "checkpoint_id": 1,
        "sequence_id": 10,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
    }
    # 2 entries, 0 seconds elapsed
    mock_cur.fetchall.return_value = [
        {"sequence_id": 11, "entry_hash": "a" * 64, "created_at": datetime.datetime.now(datetime.timezone.utc)},
        {"sequence_id": 12, "entry_hash": "b" * 64, "created_at": datetime.datetime.now(datetime.timezone.utc)},
    ]

    result = create_dual_trigger_checkpoint(
        mock_conn,
        max_entries=25,
        max_seconds=60.0,
        current_time=datetime.datetime.now(datetime.timezone.utc),
    )
    assert result is None


def test_cli_auto_checkpoint_run_once_trigger_and_skip(monkeypatch, capsys):
    """Test auto-checkpoint CLI command with --run-once under triggered and skipped states."""
    from db.cli.verifier import main

    mock_conn = MagicMock()

    with patch("db.cli.verifier.get_connection", return_value=mock_conn):
        # 1. Triggered run
        fake_res = {
            "event": "checkpoint_created",
            "checkpoint_id": 3,
            "checkpoint_sequence_id": 50,
            "checkpoint_hash": "a" * 64,
            "entries_in_range": 25,
            "trigger_reason": "entry_count_threshold",
            "newly_stored": True,
        }
        with patch("db.cli.checkpoint_store.create_dual_trigger_checkpoint", return_value=fake_res):
            monkeypatch.setattr(
                "sys.argv",
                [
                    "argus-verifier",
                    "auto-checkpoint",
                    "--run-once",
                    "--db-url",
                    "postgresql://postgres:password@localhost:5433/argus",
                ],
            )
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "checkpoint_created" in out
            assert "sequence_id=50" in out

        # 2. Skipped run
        with patch("db.cli.checkpoint_store.create_dual_trigger_checkpoint", return_value=None):
            monkeypatch.setattr(
                "sys.argv",
                [
                    "argus-verifier",
                    "auto-checkpoint",
                    "--run-once",
                    "--db-url",
                    "postgresql://postgres:password@localhost:5433/argus",
                ],
            )
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "checkpoint_skipped" in out


def test_create_checkpoint_with_merkle_tree():
    """Verify that create_dual_trigger_checkpoint computes and stores RFC 6962 Merkle tree."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Mock should_create_checkpoint to return True
    mock_cur.fetchone.return_value = {
        "checkpoint_id": 42,
        "sequence_id": 125,
        "checkpoint_hash": "c" * 64,
        "signature": b"s" * 64,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
    }

    raw_audit_rows = [
        {
            "sequence_id": i,
            "actor_user_id": 1,
            "employee_id": 42,
            "action": "UPDATE",
            "table_name": "employees",
            "row_id": 42,
            "old_value": {"salary": 80000},
            "new_value": {"salary": 85000},
            "severity": "INFO",
            "entry_hash": f"hash_{i:04d}" + "0" * 55,
            "previous_hash": "0" * 64,
            "created_at": datetime.datetime.now(datetime.timezone.utc),
        }
        for i in range(101, 126)
    ]

    with patch(
        "db.cli.checkpoint_store.should_create_checkpoint",
        return_value=(True, "entry_count_threshold", {"last_checkpoint_seq": 100}),
    ), patch(
        "db.cli.checkpoint_store.get_uncheckpointed_entries",
        return_value=raw_audit_rows,
    ), patch(
        "db.cli.checkpoint_store.get_uncheckpointed_rows",
        return_value=raw_audit_rows,
    ), patch(
        "db.cli.checkpoint_store.store_checkpoint",
        return_value=True,
    ) as mock_store:
        mock_signer = MagicMock()
        mock_signer.sign.return_value = b"signed_merkle_checkpoint"
        mock_signer.key_id = "test:key:v1"

        res = create_dual_trigger_checkpoint(
            mock_conn,
            signer=mock_signer,
        )

        assert res is not None
        assert res["merkle_root"] is not None
        assert len(res["merkle_root"]) == 64
        assert res["merkle_leaf_count"] == 25

        # Assert store_checkpoint was called with merkle_root and merkle_leaf_count
        mock_store.assert_called_once()
        args, kwargs = mock_store.call_args
        assert kwargs.get("merkle_root") == res["merkle_root"]
        assert kwargs.get("merkle_leaf_count") == 25


