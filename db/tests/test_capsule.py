"""Unit tests for Argus Forensic Merkle Capsule Generator and Verifier (NOVEL-009-D & NOVEL-009-E)."""

from datetime import datetime, timezone
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import zipfile

import pytest

from db.cli.capsule import (
    generate_capsule,
    PreMerkleCheckpointError,
    SequenceNotFoundError,
    UncheckpointedTailError,
)
from db.cli.merkle_tree import ArgusMerkleTree, compute_leaf_hash
from db.cli.verify_capsule import verify_capsule


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_rows():
    """Generates 5 sample audit rows spanning sequence IDs 1..5."""
    rows = []
    prev_h = "0" * 64
    for i in range(1, 6):
        row = {
            "sequence_id": i,
            "actor_user_id": 100 + i,
            "employee_id": 42,
            "action": "UPDATE",
            "table_name": "employees",
            "row_id": "42",
            "old_value": {"salary": 80000 + (i - 1) * 10000},
            "new_value": {"salary": 80000 + i * 10000},
            "severity": "NORMAL",
            "entry_hash": f"hash{i:060d}",
            "previous_hash": prev_h,
            "created_at": "2026-09-25T12:00:00+00:00",
        }
        prev_h = row["entry_hash"]
        rows.append(row)
    return rows


@pytest.fixture
def sample_checkpoint(sample_rows):
    """Generates sample checkpoint covering sequence 5 with Merkle root."""
    tree = ArgusMerkleTree.build(sample_rows)
    from db.cli.keygen import generate_keypair
    from db.cli.signer import sign_checkpoint

    priv_pem, pub_pem = generate_keypair()
    cp_hash = "cp_hash_000000000000000000000000000000000000000000000000000000001"
    bound_payload = f"{cp_hash}:{tree.root}".encode("utf-8")
    sig = sign_checkpoint(priv_pem, bound_payload)

    return {
        "checkpoint_id": 1,
        "sequence_id": 5,
        "checkpoint_hash": cp_hash,
        "signature": sig,
        "key_id": "local:ed25519:test",
        "merkle_root": tree.root,
        "merkle_leaf_count": 5,
        "created_at": datetime.now(timezone.utc),
        "pub_pem": pub_pem.decode("utf-8"),
        "priv_pem": priv_pem,
    }


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_generate_capsule_structure(sample_rows, sample_checkpoint, tmp_path):
    """Test that generate_capsule produces a valid zip containing all 5 required files."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Setup database mocks:
    # 1. Row lookup for seq 3
    row_3 = next(r for r in sample_rows if r["sequence_id"] == 3)
    mock_cur.fetchone.side_effect = [
        row_3,  # SELECT * FROM audit_log WHERE sequence_id = 3
        sample_checkpoint,  # SELECT * FROM chain_checkpoints WHERE sequence_id >= 3
        None,  # Preceding checkpoint query
    ]
    # 2. Interval rows query (seq > 0 AND seq <= 5)
    mock_cur.fetchall.return_value = sample_rows

    out_file = tmp_path / "test_proof.arguscap"
    bundle_bytes = generate_capsule(
        mock_conn,
        seq_id=3,
        output_path=out_file,
        public_key_pem=sample_checkpoint["pub_pem"],
    )

    assert len(bundle_bytes) > 0
    assert out_file.is_file()

    with zipfile.ZipFile(out_file, "r") as zf:
        names = zf.namelist()
        assert "evidence_row.json" in names
        assert "merkle_proof.json" in names
        assert "checkpoint.json" in names
        assert "public_key.pem" in names
        assert "verify_capsule.py" in names

        # Verify evidence_row contents
        ev_data = json.loads(zf.read("evidence_row.json").decode("utf-8"))
        assert ev_data["sequence_id"] == 3
        assert ev_data["employee_id"] == 42

        # Verify proof contents
        proof_data = json.loads(zf.read("merkle_proof.json").decode("utf-8"))
        assert proof_data["sequence_id"] == 3
        assert proof_data["merkle_root"] == sample_checkpoint["merkle_root"]
        assert len(proof_data["audit_path"]) > 0


def test_verify_capsule_roundtrip(sample_rows, sample_checkpoint):
    """Test that verify_capsule returns success on a cleanly generated capsule."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    row_3 = next(r for r in sample_rows if r["sequence_id"] == 3)
    mock_cur.fetchone.side_effect = [row_3, sample_checkpoint, None]
    mock_cur.fetchall.return_value = sample_rows

    bundle_bytes = generate_capsule(
        mock_conn,
        seq_id=3,
        public_key_pem=sample_checkpoint["pub_pem"],
    )

    is_valid, msg, details = verify_capsule(
        bundle_bytes, trusted_public_key_pem=sample_checkpoint["pub_pem"]
    )
    assert is_valid is True
    assert details["signature_valid"] is True
    assert details["leaf_hash_valid"] is True
    assert details["path_valid"] is True
    assert details["root_match"] is True
    assert "SUCCESS" in msg


def test_capsule_roundtrip_preserves_postgres_datetime_and_memoryview_signature(sample_rows):
    """PostgreSQL datetime/memoryview values must retain verifiable wire bytes."""
    from db.cli.keygen import generate_keypair
    from db.cli.signer import sign_checkpoint

    rows = [dict(row, created_at=datetime(2026, 10, 7, 5, 0, tzinfo=timezone.utc)) for row in sample_rows]
    tree = ArgusMerkleTree.build(rows)
    private_pem, public_pem = generate_keypair()
    checkpoint_hash = "postgres-checkpoint-hash"
    signature = sign_checkpoint(private_pem, f"{checkpoint_hash}:{tree.root}".encode())
    checkpoint = {
        "checkpoint_id": 9,
        "sequence_id": 5,
        "checkpoint_hash": checkpoint_hash,
        "signature": memoryview(signature),
        "key_id": "local:ed25519:test",
        "merkle_root": tree.root,
        "merkle_leaf_count": len(rows),
        "created_at": datetime(2026, 10, 7, 5, 1, tzinfo=timezone.utc),
    }

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.side_effect = [rows[2], checkpoint, None]
    mock_cur.fetchall.return_value = rows

    bundle = generate_capsule(
        mock_conn,
        seq_id=3,
        public_key_pem=public_pem.decode("utf-8"),
    )
    valid, message, details = verify_capsule(bundle, trusted_public_key_pem=public_pem)

    assert valid, message
    assert details["signature_valid"] is True
    assert details["leaf_hash_valid"] is True
    assert details["path_valid"] is True
    assert details["root_match"] is True


def test_verify_capsule_requires_external_trust_anchor(sample_rows, sample_checkpoint):
    """An archive must not establish trust in its own bundled public key."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.side_effect = [
        next(r for r in sample_rows if r["sequence_id"] == 3),
        sample_checkpoint,
        None,
    ]
    mock_cur.fetchall.return_value = sample_rows

    bundle = generate_capsule(
        mock_conn, seq_id=3, public_key_pem=sample_checkpoint["pub_pem"]
    )

    valid, message, details = verify_capsule(bundle)
    assert valid is False
    assert details["signature_valid"] is False
    assert "trusted public key" in message.lower()

    from db.cli.keygen import generate_keypair
    _, unrelated_public_key = generate_keypair()
    valid, _, details = verify_capsule(
        bundle, trusted_public_key_pem=unrelated_public_key.decode("utf-8")
    )
    assert valid is False
    assert details["signature_valid"] is False


def test_verify_capsule_tampered_evidence_row(sample_rows, sample_checkpoint):
    """Test that modifying a single field in evidence_row causes verification failure (exit 1)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    row_2 = next(r for r in sample_rows if r["sequence_id"] == 2)
    mock_cur.fetchone.side_effect = [row_2, sample_checkpoint, None]
    mock_cur.fetchall.return_value = sample_rows

    bundle_bytes = generate_capsule(
        mock_conn,
        seq_id=2,
        public_key_pem=sample_checkpoint["pub_pem"],
    )

    # Tamper with evidence_row.json inside the zip
    in_buf = io.BytesIO(bundle_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, "r") as zin:
        with zipfile.ZipFile(out_buf, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "evidence_row.json":
                    ev = json.loads(data.decode("utf-8"))
                    ev["new_value"]["salary"] = 99999999  # Tamper salary
                    data = json.dumps(ev).encode("utf-8")
                zout.writestr(item, data)

    tampered_bytes = out_buf.getvalue()
    is_valid, msg, details = verify_capsule(
        tampered_bytes, trusted_public_key_pem=sample_checkpoint["pub_pem"]
    )

    assert is_valid is False
    assert details["leaf_hash_valid"] is False
    assert "tampered" in msg.lower()


def test_verify_capsule_tampered_merkle_sibling(sample_rows, sample_checkpoint):
    """Test that mutating an audit path sibling hash causes verification failure."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    row_4 = next(r for r in sample_rows if r["sequence_id"] == 4)
    mock_cur.fetchone.side_effect = [row_4, sample_checkpoint, None]
    mock_cur.fetchall.return_value = sample_rows

    bundle_bytes = generate_capsule(
        mock_conn,
        seq_id=4,
        public_key_pem=sample_checkpoint["pub_pem"],
    )

    # Tamper with merkle_proof.json sibling hash
    in_buf = io.BytesIO(bundle_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, "r") as zin:
        with zipfile.ZipFile(out_buf, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "merkle_proof.json":
                    proof = json.loads(data.decode("utf-8"))
                    # Alter the first sibling hash
                    proof["audit_path"][0]["sibling_hash"] = "deadbeef" * 8
                    data = json.dumps(proof).encode("utf-8")
                zout.writestr(item, data)

    tampered_bytes = out_buf.getvalue()
    is_valid, msg, details = verify_capsule(
        tampered_bytes, trusted_public_key_pem=sample_checkpoint["pub_pem"]
    )

    assert is_valid is False
    assert details["path_valid"] is False


def test_verify_capsule_tampered_checkpoint_signature(sample_rows, sample_checkpoint):
    """Test that tampering with checkpoint signature triggers signature invalid failure."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    row_1 = next(r for r in sample_rows if r["sequence_id"] == 1)
    mock_cur.fetchone.side_effect = [row_1, sample_checkpoint, None]
    mock_cur.fetchall.return_value = sample_rows

    bundle_bytes = generate_capsule(
        mock_conn,
        seq_id=1,
        public_key_pem=sample_checkpoint["pub_pem"],
    )

    in_buf = io.BytesIO(bundle_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, "r") as zin:
        with zipfile.ZipFile(out_buf, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "checkpoint.json":
                    cp = json.loads(data.decode("utf-8"))
                    cp["signature_hex"] = "00" * 64  # Zeroed out signature
                    data = json.dumps(cp).encode("utf-8")
                zout.writestr(item, data)

    tampered_bytes = out_buf.getvalue()
    is_valid, msg, details = verify_capsule(
        tampered_bytes, trusted_public_key_pem=sample_checkpoint["pub_pem"]
    )

    assert is_valid is False
    assert details["signature_valid"] is False
    assert "signature verification failed" in msg.lower()


def test_generate_capsule_sequence_not_found():
    """Test that requesting non-existent sequence raises SequenceNotFoundError."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = None

    with pytest.raises(SequenceNotFoundError):
        generate_capsule(mock_conn, seq_id=999999)


def test_generate_capsule_uncheckpointed_tail():
    """Test that requesting uncheckpointed row raises UncheckpointedTailError."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.side_effect = [
        {"sequence_id": 99, "action": "INSERT"},  # row exists
        None,  # no checkpoint >= 99
    ]

    with pytest.raises(UncheckpointedTailError):
        generate_capsule(mock_conn, seq_id=99)


def test_generate_capsule_pre_merkle_checkpoint():
    """Test that requesting sequence sealed under pre-Merkle checkpoint raises PreMerkleCheckpointError."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.side_effect = [
        {"sequence_id": 10, "action": "INSERT"},
        {
            "checkpoint_id": 1,
            "sequence_id": 25,
            "checkpoint_hash": "abc",
            "signature": b"\x00" * 64,
            "merkle_root": None,  # Pre-Merkle!
        },
    ]

    with pytest.raises(PreMerkleCheckpointError):
        generate_capsule(mock_conn, seq_id=10)


def test_verify_capsule_cli_exit_codes(sample_rows, sample_checkpoint, tmp_path):
    """Test verify_capsule CLI exits with 0 on valid capsule and 1 on tampered capsule."""
    import subprocess
    import sys

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    row_3 = next(r for r in sample_rows if r["sequence_id"] == 3)
    mock_cur.fetchone.side_effect = [row_3, sample_checkpoint, None]
    mock_cur.fetchall.return_value = sample_rows

    valid_file = tmp_path / "valid.arguscap"
    generate_capsule(
        mock_conn,
        seq_id=3,
        output_path=valid_file,
        public_key_pem=sample_checkpoint["pub_pem"],
    )
    trusted_key_file = tmp_path / "trusted_public_key.pem"
    trusted_key_file.write_text(sample_checkpoint["pub_pem"], encoding="utf-8")

    # 1. Run CLI on valid capsule -> exit code 0
    res_valid = subprocess.run(
        [
            sys.executable,
            "-m",
            "db.cli.verify_capsule",
            str(valid_file),
            "--trusted-public-key",
            str(trusted_key_file),
        ],
        capture_output=True,
        text=True,
    )
    assert res_valid.returncode == 0
    assert "[PASS]" in res_valid.stdout

    # 2. Tamper evidence row in zip -> exit code 1
    tampered_file = tmp_path / "tampered.arguscap"
    with zipfile.ZipFile(valid_file, "r") as zin:
        with zipfile.ZipFile(tampered_file, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "evidence_row.json":
                    ev = json.loads(data.decode("utf-8"))
                    ev["employee_id"] = 999
                    data = json.dumps(ev).encode("utf-8")
                zout.writestr(item, data)

    res_tampered = subprocess.run(
        [
            sys.executable,
            "-m",
            "db.cli.verify_capsule",
            str(tampered_file),
            "--trusted-public-key",
            str(trusted_key_file),
        ],
        capture_output=True,
        text=True,
    )
    assert res_tampered.returncode == 1
    assert "[FAIL]" in res_tampered.stdout
