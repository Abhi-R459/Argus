from typing import AsyncGenerator, Callable, List
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from .middleware.clerk import verify_clerk_token
from .database import get_session_factory
from .models.user import User


async def get_current_user(
    token_payload: dict = Depends(verify_clerk_token),
) -> User:
    """Resolve the Clerk token to a local User record.
    
    Uses the hr_admin pool for the lookup since both roles need
    to be able to read from the users table.
    """
    clerk_user_id = token_payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject."
        )
    
    session_factory = get_session_factory("hr_admin")
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(
                User.clerk_user_id == clerk_user_id,
                User.is_active == True,
            )
        )
        user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive. Call POST /api/auth/sync first."
        )
    
    return user


def require_role(allowed_roles: List[str]) -> Callable:
    """Factory for role-checking dependencies.
    
    Usage:
        @router.post("/employees", dependencies=[Depends(require_role(["hr_admin"]))])
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Privilege separation error: {current_user.role} cannot perform this action."
            )
        return current_user
    return role_checker


async def get_db_session(
    current_user: User = Depends(get_current_user),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session routed by the current user's role.
    
    hr_admin → hr_admin Postgres pool
    compliance_auditor → compliance_auditor Postgres pool
    """
    session_factory = get_session_factory(current_user.role)
    async with session_factory() as session:
        try:
            # Bind authenticated actor identity to PostgreSQL session-local state for triggers
            if current_user and getattr(current_user, "user_id", None) is not None:
                await session.execute(
                    text("SELECT set_config('argus.actor_user_id', :uid, true)"),
                    {"uid": str(current_user.user_id)},
                )
            if current_user and getattr(current_user, "employee_id", None) is not None:
                await session.execute(
                    text("SELECT set_config('argus.actor_employee_id', :eid, true)"),
                    {"eid": str(current_user.employee_id)},
                )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

