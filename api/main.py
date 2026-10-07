from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import init_engines, dispose_engines, get_session_factory
from .config import get_settings
from .routers import health, auth, employees, audits, dashboard, checkpoints

logger = logging.getLogger(__name__)
ACTOR_NONCE_PRUNE_LOCK_KEY = 4702394923396477262


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


async def _prune_actor_context_nonces_periodically() -> None:
    """Bound nonce-table growth while retaining expired contexts for replay detection."""
    while True:
        await asyncio.sleep(6 * 60 * 60)
        try:
            factory = get_session_factory("compliance_auditor")
            async with factory() as session:
                lock_result = await session.execute(
                    text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                    {"lock_key": ACTOR_NONCE_PRUNE_LOCK_KEY},
                )
                if not lock_result.scalar():
                    await session.rollback()
                    continue
                result = await session.execute(
                    text("SELECT argus_private.prune_actor_context_nonces()")
                )
                deleted = result.scalar_one()
                await session.commit()
                logger.info("Pruned %s expired actor-context nonces", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Actor-context nonce cleanup failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async lifespan handler: initialize DB engines on startup, dispose on shutdown."""
    await init_engines()
    refresh_task = asyncio.create_task(_refresh_suspicious_activity_periodically())
    nonce_prune_task = asyncio.create_task(_prune_actor_context_nonces_periodically())
    try:
        yield
    finally:
        refresh_task.cancel()
        nonce_prune_task.cancel()
        try:
            await asyncio.gather(refresh_task, nonce_prune_task)
        except asyncio.CancelledError:
            pass
        await dispose_engines()


settings = get_settings()

app = FastAPI(
    title="Argus API",
    description="Tamper-evident, self-verifying audit trail engine for PostgreSQL",
    version="1.2.0",
    lifespan=lifespan,
    docs_url=None if settings.APP_ENV in {"staging", "production"} else "/docs",
    redoc_url=None if settings.APP_ENV in {"staging", "production"} else "/redoc",
    openapi_url=None if settings.APP_ENV in {"staging", "production"} else "/openapi.json",
)

# CORS — allow Vite dev server and common deployment origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Keep API responses from being cached, framed, or MIME-sniffed."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response

# Mount all routers under /api prefix
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(audits.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(checkpoints.router, prefix="/api")
