"""Clerk identity and one-time account role setup."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Literal

from ..middleware.clerk_auth import verify_clerk_token
from ..schemas.user import UserSyncResponse
from ..services.identity_user import resolve_clerk_user, bind_account_role

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RoleChoice(BaseModel):
    role: Literal["hr_admin", "compliance_auditor"]


@router.post("/sync", response_model=UserSyncResponse)
async def sync_user(identity: dict = Depends(verify_clerk_token)):
    return await resolve_clerk_user(identity)


@router.get("/me", response_model=UserSyncResponse)
async def get_my_profile(identity: dict = Depends(verify_clerk_token)):
    return await resolve_clerk_user(identity)


@router.post("/choose-role", response_model=UserSyncResponse)
async def choose_account_role(choice: RoleChoice, identity: dict = Depends(verify_clerk_token)):
    user = await resolve_clerk_user(identity)
    return await bind_account_role(user, choice.role)
