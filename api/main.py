from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import init_engines, dispose_engines, get_session_factory
from .config import get_settings
from .routers import health, auth, employees, audits, dashboard

logger = logging.getLogger(__name__)


async def _refresh_suspicious_activity_periodically() -> None:
    """Refresh risk flags at a bounded cadence, coordinated across API workers."""
    lock_key = audits.SUSPICIOUS_ACTIVITY_REFRESH_LOCK_KEY
    interval = max(10, get_settings().SUSPICIOUS_ACTIVITY_REFRESH_SECONDS)
    while True:
        await asyncio.sleep(interval)
        try:
            factory = get_session_factory("compliance_auditor")
            async with factory() as session:
                lock_result = await session.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": lock_key},
                )
                if not lock_result.scalar():
                    await session.rollback()
                    continue
                try:
                    await session.execute(text("CALL refresh_suspicious_activity_flags()"))
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    try:
                        await session.execute(
                            text("SELECT pg_advisory_unlock(:lock_key)"),
                            {"lock_key": lock_key},
                        )
                        await session.commit()
                    except Exception:
                        await session.rollback()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled suspicious-activity refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async lifespan handler: initialize DB engines on startup, dispose on shutdown."""
    await init_engines()
    refresh_task = asyncio.create_task(_refresh_suspicious_activity_periodically())
    try:
        yield
    finally:
        refresh_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass
        await dispose_engines()


app = FastAPI(
    title="Argus API",
    description="Tamper-evident, self-verifying audit trail engine for PostgreSQL",
    version="1.2.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server and common deployment origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers under /api prefix
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(audits.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
