"""Clerk identity and UI-selected workspace mode."""

from fastapi import APIRouter, Depends

from ..middleware.clerk_auth import verify_clerk_token
from ..schemas.user import UserSyncResponse
from ..services.identity_user import resolve_clerk_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/sync", response_model=UserSyncResponse)
async def sync_user(identity: dict = Depends(verify_clerk_token)):
    return await resolve_clerk_user(identity)


@router.get("/me", response_model=UserSyncResponse)
async def get_my_profile(identity: dict = Depends(verify_clerk_token)):
    return await resolve_clerk_user(identity)
