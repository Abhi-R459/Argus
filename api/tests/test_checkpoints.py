"""Tests for the HR-admin on-demand checkpoint action."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from api.routers import checkpoints


class FakeSigner:
    key_id = "local:ed25519:v1"

    def __init__(self):
        self.payload = None

    def sign(self, payload: bytes) -> bytes:
        self.payload = payload
        return b"s" * 64


def _row(sequence_id: int, entry_hash: str) -> dict:
    return {
        "sequence_id": sequence_id,
        "actor_user_id": 1,
        "employee_id": 1,
        "action": "UPDATE",
        "table_name": "employees",
        "row_id": 1,
        "old_value": {"name": "A"},
        "new_value": {"name": "B"},
        "severity": "INFO",
        "entry_hash": entry_hash,
        "previous_hash": "0" * 64,
        "created_at": datetime(2026, 10, 7, tzinfo=timezone.utc),
    }


@pytest.mark.asyncio
async def test_hr_admin_can_create_signed_checkpoint(client_hr, mock_db_session, monkeypatch):
    signer = FakeSigner()
    monkeypatch.setattr(checkpoints, "_load_signer", lambda: signer)

    latest = MagicMock()
    latest.first.return_value = (100,)
    entries = MagicMock()
    entries.mappings.return_value.all.return_value = [_row(101, "a" * 64), _row(102, "b" * 64)]
    inserted = MagicMock()
    inserted.first.return_value = (9, datetime(2026, 10, 7, tzinfo=timezone.utc))
    mock_db_session.execute.side_effect = [MagicMock(), MagicMock(), latest, entries, inserted]

    response = await client_hr.post("/api/checkpoints/create")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoint_id"] == 9
    assert payload["sequence_id"] == 102
    assert payload["entries_sealed"] == 2
    assert payload["signature_status"] == "signed"
    assert payload["external_anchor_created"] is False
    assert signer.payload == f"{payload['checkpoint_hash']}:{payload['merkle_root']}".encode()
    recorded_event = mock_db_session.add.call_args.args[0]
    assert recorded_event.event_type == "CHECKPOINT_CREATED"
    assert recorded_event.actor_email == "hr@argus.test"
    assert recorded_event.sequence_id == 102


@pytest.mark.asyncio
async def test_checkpoint_action_rejects_empty_uncheckpointed_tail(client_hr, mock_db_session):
    latest = MagicMock()
    latest.first.return_value = (100,)
    entries = MagicMock()
    entries.mappings.return_value.all.return_value = []
    mock_db_session.execute.side_effect = [MagicMock(), MagicMock(), latest, entries]

    response = await client_hr.post("/api/checkpoints/create")

    assert response.status_code == 409
    assert response.json()["detail"] == "There are no new audit events to checkpoint."
    mock_db_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_auditor_cannot_create_checkpoint(client_auditor, mock_db_session):
    response = await client_auditor.post("/api/checkpoints/create")

    assert response.status_code == 403
    mock_db_session.execute.assert_not_called()
