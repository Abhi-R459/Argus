"""Intermediate Test Gate 5: Evidence Pack Export Endpoint (PACK-002).

Validates:
1. GET /api/audit-logs/export-pack returns 200 OK and valid .arguspack ZIP archive.
2. In-memory ZIP unpack contains all 5 mandatory files:
   - manifest.json
   - events.jsonl
   - checkpoints.json
   - signature.sig
   - verify_standalone.py
3. Standalone verifier (verify_standalone.py) verifies the exported bundle with exit code 0.
4. Role enforcement: compliance_auditor allowed; hr_admin forbidden (403); unauthenticated rejected (401).
"""

from __future__ import annotations

import io
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import AsyncClient

from db.cli.verify_standalone import verify_bundle, recompute_event_hash
from db.cli.signer import sign_checkpoint

pytestmark = pytest.mark.asyncio


class MockAuditRow:
    """Mock audit log row mimicking SQLAlchemy query result."""
    def __init__(self, seq, actor_id, emp_id, action, tbl, row_id, old_val, new_val, sev, h, prev, ts):
        self.sequence_id = seq
        self.actor_user_id = actor_id
        self.employee_id = emp_id
        self.action = action
        self.table_name = tbl
        self.row_id = row_id
        self.old_value = old_val
        self.new_value = new_val
        self.severity = sev
        self.entry_hash = h
        self.previous_hash = prev
        self.created_at = ts


async def test_export_pack_empty(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert /api/audit-logs/export-pack returns valid ZIP bundle with 5 files on empty DB."""
    mock_audit_res = MagicMock()
    mock_audit_res.all.return_value = []

    mock_cp_res = MagicMock()
    mock_cp_res.all.return_value = []

    mock_db_session.execute.side_effect = [mock_audit_res, mock_cp_res]

    response = await client_auditor.get("/api/audit-logs/export-pack")
    assert response.status_code == 200
    assert "attachment; filename=\"audit_evidence_" in response.headers.get("Content-Disposition", "")
    assert response.headers.get("Content-Disposition", "").endswith(".arguspack\"")
    assert response.headers.get("X-Argus-Bundle-Version") == "1.0"

    # Inspect zip contents in-memory
    zf = zipfile.ZipFile(io.BytesIO(response.content), "r")
    namelist = zf.namelist()
    for mandatory in ["manifest.json", "events.jsonl", "checkpoints.json", "signature.sig", "verify_standalone.py"]:
        assert mandatory in namelist

    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest["total_events"] == 0
    assert manifest["bundle_version"] == "1.0"
    assert manifest["signature_algorithm"] == "Ed25519"
    assert len(manifest["public_key_hex"]) == 64


async def test_export_pack_with_entries_and_standalone_verify(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert exported .arguspack bundle contains valid events and verifies cleanly with verify_standalone."""
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    prev_h = "0" * 64

    # Row 1
    row1_dict = {
        "sequence_id": 1,
        "actor_user_id": 1,
        "action": "INSERT",
        "table_name": "employees",
        "row_id": 101,
        "old_value_text": None,
        "new_value_text": json.dumps({"full_name": "Alice", "status": "ACTIVE"}, sort_keys=True, separators=(",", ":")),
        "created_at_text": now.isoformat(),
    }
    h1 = recompute_event_hash(row1_dict, prev_h)
    row1 = MockAuditRow(
        1, 1, 101, "INSERT", "employees", 101, None, {"full_name": "Alice", "status": "ACTIVE"}, "INFO", h1, prev_h, now
    )

    # Row 2
    row2_dict = {
        "sequence_id": 2,
        "actor_user_id": 1,
        "action": "UPDATE",
        "table_name": "employees",
        "row_id": 101,
        "old_value_text": json.dumps({"status": "ACTIVE"}, sort_keys=True, separators=(",", ":")),
        "new_value_text": json.dumps({"status": "PROMOTED"}, sort_keys=True, separators=(",", ":")),
        "created_at_text": now.isoformat(),
    }
    h2 = recompute_event_hash(row2_dict, h1)
    row2 = MockAuditRow(
        2, 1, 101, "UPDATE", "employees", 101, {"status": "ACTIVE"}, {"status": "PROMOTED"}, "INFO", h2, h1, now
    )

    mock_audit_res = MagicMock()
    mock_audit_res.all.return_value = [row1, row2]

    mock_cp_res = MagicMock()
    mock_cp_res.all.return_value = []

    mock_db_session.execute.side_effect = [mock_audit_res, mock_cp_res]

    response = await client_auditor.get("/api/audit-logs/export-pack")
    assert response.status_code == 200

    # Unpack into temp directory and verify using verify_standalone.py
    with tempfile.TemporaryDirectory() as td:
        bundle_path = Path(td) / "bundle.arguspack"
        bundle_path.write_bytes(response.content)

        # Verify using verify_bundle directly
        exit_code, report = verify_bundle(bundle_path)
        assert exit_code == 0
        assert report["status"] == "SUCCESS"
        assert report["signature_valid"] is True
        assert report["total_events"] == 2
        assert len(report["mismatches"]) == 0
        assert len(report["gaps"]) == 0


async def test_export_pack_hr_forbidden(client_hr: AsyncClient):
    """Assert hr_admin role cannot download the .arguspack bundle."""
    response = await client_hr.get("/api/audit-logs/export-pack")
    assert response.status_code == 403


async def test_export_pack_unauth_unauthorized(client_unauth: AsyncClient):
    """Assert unauthenticated request cannot download the .arguspack bundle."""
    response = await client_unauth.get("/api/audit-logs/export-pack")
    assert response.status_code == 401
