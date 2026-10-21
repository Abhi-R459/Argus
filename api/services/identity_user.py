"""Bind verified Clerk identities to stable Argus user IDs."""

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from ..database import get_session_factory
from ..models.auth_identity import AuthIdentity
from ..models.user import User


async def resolve_clerk_user(identity: dict) -> User:
    subject = identity.get("sub")
    email = identity.get("email")
    if (identity.get("provider") != "clerk" or identity.get("email_verified") is not True
            or not isinstance(subject, str) or not subject.startswith("clerk:")
            or not isinstance(email, str) or not email):
        raise HTTPException(401, "Invalid identity.")
    normalized_email = email.strip().lower()
    async with get_session_factory("hr_admin")() as session:
        link = (await session.execute(
            select(AuthIdentity).where(AuthIdentity.provider == "clerk", AuthIdentity.subject == subject)
        )).scalar_one_or_none()
        if link:
            user = (await session.execute(
                select(User).where(User.user_id == link.user_id)
            )).scalar_one_or_none()
            if user is None or user.email.strip().lower() != normalized_email:
                raise HTTPException(403, "This account is not linked to that email.")
        else:
            # Preserve Supabase-era IDs for an earlier release's rollback path.
            user = (await session.execute(
                select(User).where(func.lower(User.email) == normalized_email).with_for_update()
            )).scalar_one_or_none()
            if user is None:
                user = User(
                    clerk_user_id=subject,
                    full_name=identity.get("name") or "Unknown",
                    email=normalized_email,
                    role="compliance_auditor",
                    account_role=None,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
            session.add(AuthIdentity(provider="clerk", subject=subject, user_id=user.user_id))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                raise HTTPException(409, "Account linking changed. Please sign in again.") from None
        if not user.is_active:
            raise HTTPException(401, "User account is deactivated.")
        return user


async def bind_account_role(user: User, role: str) -> User:
    """Atomically bind the account once; later attempts always conflict."""
    if role not in {"hr_admin", "compliance_auditor"}:
        raise HTTPException(422, "Invalid account role.")
    async with get_session_factory("hr_admin")() as session:
        result = await session.execute(
            update(User)
            .where(User.user_id == user.user_id, User.account_role.is_(None))
            .values(account_role=role, role=role)
            .returning(User.user_id)
        )
        if result.scalar_one_or_none() is None:
            await session.rollback()
            raise HTTPException(409, "Account role has already been chosen.")
        await session.commit()
    user.account_role = role
    user.role = role
    return user
