import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from ..database import get_session_factory

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """Health check endpoint. No authentication required."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check():
    """Report readiness only while both least-privilege DB roles can connect."""
    try:
        for role in ("hr_admin", "compliance_auditor"):
            session_factory = get_session_factory(role)
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        logger.warning("API readiness check failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Required database connection is unavailable.",
        ) from exc
