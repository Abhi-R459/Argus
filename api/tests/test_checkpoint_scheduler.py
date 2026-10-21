"""Tests for exact, distributed automatic checkpoint boundaries."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.checkpoints import create_signed_checkpoint


class FakeSigner:
    key_id = "local:ed25519:v1"

    def sign(self, payload: bytes) -> bytes:
        assert payload
        return b"s" * 64


def _event(sequence_id: int) -> dict:
    return {
        "sequence_id": sequence_id,
        "actor_user_id": 1,
        "employee_id": 1,
        "action": "UPDATE",
        "table_name": "employees",
        "row_id": 1,
        "old_value": {"name": "before"},
        "new_value": {"name": "after"},
        "severity": "INFO",
        "entry_hash": f"{sequence_id:064x}",
        "previous_hash": "0" * 64,
        "created_at": datetime(2026, 10, 21, tzinfo=timezone.utc),
    }


@pytest.mark.asyncio
async def test_auto_checkpoint_seals_one_exact_interval_and_records_system_actor():
    session = AsyncMock()
    session.add = MagicMock()
    latest = MagicMock()
    latest.first.return_value = (100,)
    entries = MagicMock()
    entries.mappings.return_value.all.return_value = [_event(seq) for seq in range(101, 121)]
    inserted = MagicMock()
    inserted.first.return_value = (8, datetime(2026, 10, 21, tzinfo=timezone.utc))
    session.execute.side_effect = [MagicMock(), MagicMock(), latest, entries, inserted]

    result = await create_signed_checkpoint(
        session,
        actor_user_id=0,
        actor_email="system-maintenance@argus.invalid",
        client_ip="system",
        max_events=20,
        require_full_interval=True,
        signer_loader=FakeSigner,
        event_type="CHECKPOINT_AUTO_CREATED",
    )

    assert result["sequence_id"] == 120
    assert result["entries_sealed"] == 20
    entries_query = session.execute.call_args_list[3]
    assert entries_query.args[1] == {"last_sequence": 100, "max_events": 20}
    event = session.add.call_args.args[0]
    assert event.event_type == "CHECKPOINT_AUTO_CREATED"
    assert event.actor_user_id == 0
    assert event.matches_found == 20


@pytest.mark.asyncio
async def test_auto_checkpoint_does_nothing_before_interval_is_reached():
    session = AsyncMock()
    session.add = MagicMock()
    latest = MagicMock()
    latest.first.return_value = (100,)
    entries = MagicMock()
    entries.mappings.return_value.all.return_value = []
    session.execute.side_effect = [MagicMock(), MagicMock(), latest, entries]

    result = await create_signed_checkpoint(
        session,
        actor_user_id=0,
        actor_email="system-maintenance@argus.invalid",
        client_ip="system",
        max_events=20,
        signer_loader=FakeSigner,
        event_type="CHECKPOINT_AUTO_CREATED",
    )

    assert result is None
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_auto_checkpoint_waits_for_the_complete_interval():
    session = AsyncMock()
    session.add = MagicMock()
    latest = MagicMock()
    latest.first.return_value = (100,)
    entries = MagicMock()
    entries.mappings.return_value.all.return_value = [_event(seq) for seq in range(101, 120)]
    session.execute.side_effect = [MagicMock(), MagicMock(), latest, entries]

    result = await create_signed_checkpoint(
        session,
        actor_user_id=0,
        actor_email="system-maintenance@argus.invalid",
        client_ip="system",
        max_events=20,
        require_full_interval=True,
        signer_loader=FakeSigner,
        event_type="CHECKPOINT_AUTO_CREATED",
    )

    assert result is None
    session.add.assert_not_called()
