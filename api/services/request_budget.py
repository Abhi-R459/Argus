from fastapi import HTTPException
from sqlalchemy import text

from ..config import get_settings
from ..database import get_session_factory


async def consume_request_budget(user, scope: str = "api", limit: int = 120):
    if get_settings().APP_ENV == "development":
        return
    # Commit separately so a failed business transaction cannot refund usage.
    async with get_session_factory(user.role)() as session:
        result = await session.execute(
            text("SELECT allowed, retry_after FROM argus_private.consume_request_budget(:actor, :scope, :limit)"),
            {"actor": user.user_id, "scope": scope, "limit": limit},
        )
        allowed, retry_after = result.one()
        await session.commit()
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before trying again.",
                            headers={"Retry-After": str(retry_after)})
