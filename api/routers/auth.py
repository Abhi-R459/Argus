from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from ..middleware.supabase_auth import verify_supabase_token, validate_local_access
from ..database import get_session_factory
from ..models.user import User
from ..schemas.user import UserSyncResponse
from ..config import get_settings
from ..services.request_budget import consume_request_budget

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/sync", response_model=UserSyncResponse)
async def sync_user(
    token_payload: dict = Depends(verify_supabase_token),
):
    """Synchronize the authenticated Supabase user with the local users table.
    
    Looks up the user by clerk_user_id. If found, returns the existing record.
    A first-time account is created only when its verified email is listed in
    the server-side role allowlist. Email contents and user-controlled metadata
    are never used to grant a role.
    """
    clerk_user_id = token_payload.get("sub")
    email = token_payload.get("email", "") or ""
    full_name = token_payload.get("name", token_payload.get("first_name", "")) or ""
    if not isinstance(email, str) or not isinstance(full_name, str) or len(email) > 255 or len(full_name) > 255:
        raise HTTPException(status_code=400, detail="Invalid account profile claims.")
    email = email.strip().lower()
    
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject claim."
        )
    
    # Use hr_admin pool for user management
    session_factory = get_session_factory("hr_admin")
    async with session_factory() as session:
        # Look up existing user
        result = await session.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            settings = get_settings()
            normalized_email = email.strip().lower()
            verified_email = token_payload.get("email_verified") is True
            hr_admin_emails = {
                item.strip().lower()
                for item in settings.HR_ADMIN_EMAILS.split(",")
                if item.strip()
            }
            auditor_emails = {
                item.strip().lower()
                for item in settings.COMPLIANCE_AUDITOR_EMAILS.split(",")
                if item.strip()
            }

            if not verified_email or not normalized_email:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="A verified, administrator-provisioned account is required.",
                )
            if normalized_email in hr_admin_emails:
                assigned_role = "hr_admin"
            elif normalized_email in auditor_emails:
                assigned_role = "compliance_auditor"
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This account has not been provisioned for Argus. Contact an administrator.",
                )

            statement = insert(User).values(
                clerk_user_id=clerk_user_id,
                full_name=full_name or "Unknown",
                email=normalized_email,
                role=assigned_role,
                is_active=True,
            ).on_conflict_do_nothing(index_elements=[User.clerk_user_id])
            try:
                await session.execute(statement)
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise HTTPException(status_code=409, detail="This email is already linked to another account. Contact an administrator.") from exc
            result = await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))
            user = result.scalar_one()
            if not user.is_active:
                raise HTTPException(status_code=401, detail="User account is deactivated.")
        elif not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated."
            )
        else:
            validate_local_access(user, token_payload)
            # Update name/email from Supabase if changed
            updated = False
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                updated = True
            if email and token_payload.get("email_verified") is True and user.email != email:
                user.email = email
                updated = True
            if updated:
                try:
                    await session.commit()
                except IntegrityError as exc:
                    await session.rollback()
                    raise HTTPException(status_code=409, detail="This email is already linked to another account. Contact an administrator.") from exc
                await session.refresh(user)
    
    validate_local_access(user, token_payload)
    await consume_request_budget(user)
    return user


@router.get("/me", response_model=UserSyncResponse)
async def get_my_profile(
    token_payload: dict = Depends(verify_supabase_token),
):
    """Retrieve the profile and role of the currently authenticated user."""
    clerk_user_id = token_payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject claim."
        )
    session_factory = get_session_factory("hr_admin")
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
    # Release this connection before synchronization or budgeting uses the pool.
    if user is None:
        return await sync_user(token_payload)
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is deactivated.")
    validate_local_access(user, token_payload)
    await consume_request_budget(user)
    return user


@router.post("/role", response_model=UserSyncResponse)
async def switch_user_role(
    new_role: str,
    token_payload: dict = Depends(verify_supabase_token),
):
    """Switch user role between 'hr_admin' and 'compliance_auditor' for demonstration and testing."""
    settings = get_settings()
    if not settings.ALLOW_DEMO_ROLE_SWITCH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role switching is disabled in production environments."
        )

    if new_role not in ("hr_admin", "compliance_auditor"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'hr_admin' or 'compliance_auditor'."
        )
    
    clerk_user_id = token_payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject."
        )
    
    session_factory = get_session_factory("hr_admin")
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Call POST /api/auth/sync first."
            )
        user.role = new_role
        await session.commit()
        await session.refresh(user)
        return user
