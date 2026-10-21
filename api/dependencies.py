from typing import AsyncGenerator, Callable, List
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .middleware.clerk_auth import verify_clerk_token
from .database import get_session_factory
from .models.user import User
from .services.identity_user import resolve_clerk_user
from db.crypto.actor_context import create_actor_context
from .config import get_settings
from .services.request_budget import consume_request_budget


async def get_current_user(
    token_payload: dict = Depends(verify_clerk_token),
) -> User:
    """Resolve a verified Clerk account and its database-bound role."""
    user = await resolve_clerk_user(token_payload)
    if user.account_role not in {"hr_admin", "compliance_auditor"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choose your account role first.")
    # The legacy column is updated together with account_role for database
    # actor assertions and rollback compatibility.
    user.role = user.account_role
    await consume_request_budget(user)
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
            settings = get_settings()
            actor_context = create_actor_context(
                actor_user_id=current_user.user_id,
                actor_employee_id=getattr(current_user, "employee_id", None),
                db_role=current_user.role,
                secret_hex=settings.AUDIT_CONTEXT_SECRET,
                key_id=settings.AUDIT_CONTEXT_KEY_ID,
            )
            await session.execute(
                text(
                    "SELECT set_config('argus.actor_context_version', :version, true), "
                    "set_config('argus.actor_context_key_id', :key_id, true), "
                    "set_config('argus.actor_user_id', :actor_user_id, true), "
                    "set_config('argus.actor_employee_id', :actor_employee_id, true), "
                    "set_config('argus.actor_db_role', :db_role, true), "
                    "set_config('argus.actor_nonce', :nonce, true), "
                    "set_config('argus.actor_issued_at', :issued_at, true), "
                    "set_config('argus.actor_expires_at', :expires_at, true), "
                    "set_config('argus.actor_signature', :signature, true)"
                ),
                actor_context,
            )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

