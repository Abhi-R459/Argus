"""Create signed checkpoints at the HR-selected audit-event interval."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..database import get_session_factory
from .checkpoints import CHECKPOINT_LOCK_KEY, create_signed_checkpoint

logger = logging.getLogger(__name__)
POLL_SECONDS = 15
SYSTEM_ACTOR_ID = 0
SYSTEM_ACTOR_EMAIL = "system-maintenance@argus.invalid"


def _rolling_checkpoint_plan(
    latest_checkpoint: tuple[int, int] | None,
    latest_event_sequence: int,
    interval_events: int,
) -> tuple[int, int | None, str] | None:
    """Return the covered boundary, row to replace, and audit event type."""
    if latest_checkpoint is not None and latest_event_sequence <= latest_checkpoint[1]:
        return None

    if latest_checkpoint is not None and latest_checkpoint[1] % interval_events:
        return (
            latest_checkpoint[1] - latest_checkpoint[1] % interval_events,
            latest_checkpoint[0],
            "CHECKPOINT_AUTO_REPLACED",
        )

    return (
        latest_checkpoint[1] if latest_checkpoint else 0,
        None,
        "CHECKPOINT_AUTO_CREATED",
    )


async def run_checkpoint_scheduler() -> None:
    """Keep interval boundaries and one replaceable checkpoint at the current tail."""
    while True:
        try:
            factory = get_session_factory("hr_admin")
            async with factory() as session:
                settings_result = await session.execute(text(
                    "SELECT enabled, interval_events "
                    "FROM checkpoint_schedule_settings WHERE id = 1"
                ))
                settings = settings_result.first()
                if settings is None or not bool(settings[0]):
                    await session.rollback()
                else:
                    interval_events = int(settings[1])
                    lock_result = await session.execute(
                        text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                        {"lock_key": CHECKPOINT_LOCK_KEY},
                    )
                    if not lock_result.scalar():
                        await session.rollback()
                    else:
                        checkpoint_result = await session.execute(text(
                            "SELECT checkpoint_id, sequence_id FROM chain_checkpoints "
                            "ORDER BY sequence_id DESC LIMIT 1"
                        ))
                        checkpoint_row = checkpoint_result.first()
                        latest_checkpoint = (
                            (int(checkpoint_row[0]), int(checkpoint_row[1]))
                            if checkpoint_row
                            else None
                        )
                        event_result = await session.execute(text(
                            "SELECT COALESCE(MAX(sequence_id), 0) FROM audit_log"
                        ))
                        latest_event_sequence = int(event_result.scalar() or 0)
                        plan = _rolling_checkpoint_plan(
                            latest_checkpoint, latest_event_sequence, interval_events
                        )
                        if plan is None:
                            await session.rollback()
                            await asyncio.sleep(POLL_SECONDS)
                            continue
                        starting_after_sequence, replace_checkpoint_id, event_type = plan
                        result = await create_signed_checkpoint(
                            session,
                            actor_user_id=SYSTEM_ACTOR_ID,
                            actor_email=SYSTEM_ACTOR_EMAIL,
                            client_ip="system",
                            max_events=interval_events,
                            starting_after_sequence=starting_after_sequence,
                            replace_checkpoint_id=replace_checkpoint_id,
                            event_type=event_type,
                        )
                        if result is None:
                            await session.rollback()
                        else:
                            await session.commit()
                            logger.info(
                                "Automatic checkpoint %s sealed %s events through sequence %s",
                                result["checkpoint_id"],
                                result["entries_sealed"],
                                result["sequence_id"],
                            )
        except asyncio.CancelledError:
            raise
        except IntegrityError:
            logger.info("Automatic checkpoint skipped because another checkpoint sealed the boundary")
        except Exception:
            # Driver exceptions can contain connection strings or SQL parameters.
            logger.warning("Automatic checkpoint scheduler failed (%s)", "unexpected error")
        await asyncio.sleep(POLL_SECONDS)
