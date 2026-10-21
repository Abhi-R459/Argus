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


async def run_checkpoint_scheduler() -> None:
    """Poll persistent HR settings and create one exact-size checkpoint at a time."""
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
                        result = await create_signed_checkpoint(
                            session,
                            actor_user_id=SYSTEM_ACTOR_ID,
                            actor_email=SYSTEM_ACTOR_EMAIL,
                            client_ip="system",
                            max_events=interval_events,
                            require_full_interval=True,
                            event_type="CHECKPOINT_AUTO_CREATED",
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
