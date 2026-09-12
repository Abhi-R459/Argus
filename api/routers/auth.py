from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..middleware.clerk import verify_clerk_token
from ..database import get_session_factory
from ..models.user import User
from ..schemas.user import UserSyncResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/sync", response_model=UserSyncResponse)
async def sync_user(
    token_payload: dict = Depends(verify_clerk_token),
):
    """Synchronize the authenticated Clerk user with the local users table.
    
    Looks up the user by clerk_user_id. If found, returns the existing record.
    If the user does not exist in the local users table, returns 401 — 
    new users must be provisioned by an admin (the users table has a 
    role column that must be set explicitly).
    """
    clerk_user_id = token_payload.get("sub")
    email = token_payload.get("email", "")
    full_name = token_payload.get("name", token_payload.get("first_name", ""))
    
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
            # Auto-provision: create user with data from Clerk token
            # Default role is hr_admin; can be changed by another admin later
            user = User(
                clerk_user_id=clerk_user_id,
                full_name=full_name or "Unknown",
                email=email or f"{clerk_user_id}@placeholder.com",
                role="hr_admin",  # Default role for new users
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated."
            )
        else:
            # Update name/email from Clerk if changed
            updated = False
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                updated = True
            if email and user.email != email:
                user.email = email
                updated = True
            if updated:
                await session.commit()
                await session.refresh(user)
    
    return user


@router.post("/role", response_model=UserSyncResponse)
async def switch_user_role(
    new_role: str,
    token_payload: dict = Depends(verify_clerk_token),
):
    """Switch user role between 'hr_admin' and 'compliance_auditor' for demonstration and testing."""
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
