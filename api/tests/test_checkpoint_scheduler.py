"""Tests for exact, distributed automatic checkpoint boundaries."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.checkpoints import create_signed_checkpoint
from api.services.checkpoint_scheduler import _append_checkpoint_plan


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


@pytest.mark.parametrize(
    ("checkpoint", "latest", "expected"),
    [
        ((5, 216), 217, None),
        ((5, 249), 250, 249),
        ((4, 200), 201, None),
        ((5, 216), 216, None),
        (None, 16, None),
        (None, 50, 0),
        ((6, 218), 249, None),
        ((6, 218), 250, 218),
    ],
)
def test_scheduler_appends_only_at_fixed_boundaries(checkpoint, latest, expected):
    assert _append_checkpoint_plan(checkpoint, latest, 50) == expected


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


@pytest.mark.asyncio
async def test_scheduler_appends_after_a_partial_checkpoint():
    session = AsyncMock()
    session.add = MagicMock()
    latest = MagicMock()
    latest.first.return_value = (218,)
    entries = MagicMock()
    entries.mappings.return_value.all.return_value = [_event(seq) for seq in range(219, 251)]
    inserted = MagicMock()
    inserted.first.return_value = (7, datetime(2026, 10, 21, tzinfo=timezone.utc))
    session.execute.side_effect = [MagicMock(), MagicMock(), latest, entries, inserted]

    result = await create_signed_checkpoint(
        session,
        actor_user_id=0,
        actor_email="system-maintenance@argus.invalid",
        client_ip="system",
        max_events=50,
        starting_after_sequence=218,
        signer_loader=FakeSigner,
        event_type="CHECKPOINT_AUTO_CREATED",
    )

    assert result["checkpoint_id"] == 7
    assert result["sequence_id"] == 250
    assert result["entries_sealed"] == 32
    entries_query = session.execute.call_args_list[3]
    assert entries_query.args[1] == {"last_sequence": 218, "max_events": 50}
    insert_query = session.execute.call_args_list[4]
    assert "INSERT INTO chain_checkpoints" in str(insert_query.args[0])
    event = session.add.call_args.args[0]
    assert event.event_type == "CHECKPOINT_AUTO_CREATED"
    assert event.matches_found == 32
