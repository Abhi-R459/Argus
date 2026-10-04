"""API integration tests for Merkle Evidence Capsule and Proof endpoints (NOVEL-009-F & NOVEL-009-H).

Tests:
1. RBAC: compliance_auditor authorized, hr_admin receives 403 Forbidden.
2. Error conditions: sequence not found (404), pre-Merkle checkpoint (404), uncheckpointed tail (422).
3. Capsule download: returns application/zip with attachment header and verifiable .arguscap bundle.
4. Proof inspection: returns MerkleProofResponse with audit path and root.
"""

import io
from unittest.mock import MagicMock, patch
import zipfile

from httpx import AsyncClient
import pytest

from db.cli.capsule import (
    PreMerkleCheckpointError,
    SequenceNotFoundError,
    UncheckpointedTailError,
)
from db.cli.merkle_tree import ArgusMerkleTree
from db.cli.verify_capsule import verify_capsule

pytestmark = pytest.mark.asyncio


def _create_mock_capsule_bytes(seq_id=42):
    """Generates a real in-memory .arguscap archive for mock test responses."""
    from db.cli.capsule import generate_capsule

    sample_rows = [
        {
            "sequence_id": seq_id,
            "actor_user_id": 101,
            "employee_id": 1,
            "action": "UPDATE",
            "table_name": "employees",
            "row_id": "1",
            "old_value": {"salary": 80000},
            "new_value": {"salary": 90000},
            "severity": "NORMAL",
            "entry_hash": "a" * 64,
            "previous_hash": "0" * 64,
            "created_at": "2026-09-25T12:00:00+00:00",
        }
    ]
    tree = ArgusMerkleTree.build(sample_rows)
    from db.cli.keygen import generate_keypair
    from db.cli.signer import sign_checkpoint

    priv_pem, pub_pem = generate_keypair()
    cp_hash = "b" * 64
    bound = f"{cp_hash}:{tree.root}".encode("utf-8")
    sig = sign_checkpoint(priv_pem, bound)

    cp_mock = {
        "checkpoint_id": 10,
        "sequence_id": seq_id,
        "checkpoint_hash": cp_hash,
        "signature": sig,
        "key_id": "local:ed25519:test",
        "merkle_root": tree.root,
        "merkle_leaf_count": 1,
        "created_at": "2026-09-25T12:00:00+00:00",
    }

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.side_effect = [sample_rows[0], cp_mock, None]
    mock_cur.fetchall.return_value = sample_rows

    return generate_capsule(mock_conn, seq_id, public_key_pem=pub_pem.decode("utf-8"))


# ---------------------------------------------------------------------------
# RBAC Tests
# ---------------------------------------------------------------------------

async def test_capsule_hr_forbidden(client_hr: AsyncClient):
    """GET /api/audit-logs/{seq_id}/capsule must be 403 Forbidden for HR admin."""
    response = await client_hr.get("/api/audit-logs/42/capsule")
    assert response.status_code == 403


async def test_proof_hr_forbidden(client_hr: AsyncClient):
    """GET /api/audit-logs/{seq_id}/proof must be 403 Forbidden for HR admin."""
    response = await client_hr.get("/api/audit-logs/42/proof")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Capsule Endpoint Tests
# ---------------------------------------------------------------------------

async def test_capsule_sequence_not_found(client_auditor: AsyncClient):
    """Missing sequence ID returns 404 Not Found."""
    with patch(
        "db.cli.capsule.generate_capsule",
        side_effect=SequenceNotFoundError("Sequence ID 999 not found in audit_log."),
    ):
        with patch("psycopg2.connect"):
            response = await client_auditor.get("/api/audit-logs/999/capsule")
            assert response.status_code == 404
            assert "999 not found" in response.json()["detail"]


async def test_capsule_pre_merkle_checkpoint(client_auditor: AsyncClient):
    """Pre-Merkle era checkpoint returns 404 Not Found."""
    with patch(
        "db.cli.capsule.generate_capsule",
        side_effect=PreMerkleCheckpointError("Checkpoint #1 is pre-Merkle (merkle_root is null)."),
    ):
        with patch("psycopg2.connect"):
            response = await client_auditor.get("/api/audit-logs/10/capsule")
            assert response.status_code == 404
            assert "pre-Merkle" in response.json()["detail"]


async def test_capsule_uncheckpointed_tail(client_auditor: AsyncClient):
    """Uncheckpointed sequence in the tail returns 422 Unprocessable Entity."""
    with patch(
        "db.cli.capsule.generate_capsule",
        side_effect=UncheckpointedTailError("Sequence ID 99 has not yet been sealed in a checkpoint."),
    ):
        with patch("psycopg2.connect"):
            response = await client_auditor.get("/api/audit-logs/99/capsule")
            assert response.status_code == 422
            assert "uncheckpointed tail" in response.json()["detail"] or "not yet been sealed" in response.json()["detail"]


async def test_capsule_auditor_success(client_auditor: AsyncClient):
    """Compliance auditor can download .arguscap bundle with valid ZIP headers and structure."""
    fake_zip_bytes = _create_mock_capsule_bytes(42)

    with patch("db.cli.capsule.generate_capsule", return_value=fake_zip_bytes):
        with patch("psycopg2.connect"):
            response = await client_auditor.get("/api/audit-logs/42/capsule")
            assert response.status_code == 200
            assert response.headers["Content-Type"] == "application/zip"
            assert 'filename="proof_seq42.arguscap"' in response.headers["Content-Disposition"]

            # Verify bundle contents
            is_valid, msg, details = verify_capsule(response.content)
            assert is_valid is True
            assert details["sequence_id"] == 42
            assert details["signature_valid"] is True


# ---------------------------------------------------------------------------
# Proof Metadata Endpoint Tests
# ---------------------------------------------------------------------------

async def test_proof_endpoint_success(client_auditor: AsyncClient):
    """GET /api/audit-logs/{seq_id}/proof returns structured Merkle proof metadata."""
    sample_row = {
        "sequence_id": 42,
        "actor_user_id": 1,
        "employee_id": 5,
        "action": "UPDATE",
        "table_name": "employees",
        "row_id": "5",
        "old_value": {},
        "new_value": {"salary": 100000},
        "severity": "NORMAL",
        "entry_hash": "a" * 64,
        "previous_hash": "0" * 64,
        "created_at": "2026-09-25T12:00:00+00:00",
    }
    tree = ArgusMerkleTree.build([sample_row])
    cp_row = {
        "checkpoint_id": 5,
        "sequence_id": 42,
        "merkle_root": tree.root,
        "merkle_leaf_count": 1,
    }

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.side_effect = [
        {"sequence_id": 42, "created_at": "2026-09-25T12:00:00+00:00"},  # row check
        cp_row,  # checkpoint check
        None,    # prev checkpoint
    ]
    mock_cur.fetchall.return_value = [sample_row]

    with patch("psycopg2.connect", return_value=mock_conn):
        response = await client_auditor.get("/api/audit-logs/42/proof")
        assert response.status_code == 200
        data = response.json()
        assert data["sequence_id"] == 42
        assert data["checkpoint_id"] == 5
        assert data["merkle_root"] == tree.root
        assert "leaf_hash" in data
        assert "audit_path" in data
