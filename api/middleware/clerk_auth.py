"""Verify a Clerk session and its current, verified primary email.

The JWT proves its origin; the Backend API checks that the session and user
have not subsequently been revoked, banned, or deleted.
"""

import re

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings

security = HTTPBearer()
_CLERK_API = "https://api.clerk.com/v1"


async def _clerk_object(path: str, secret: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            response = await client.get(
                _CLERK_API + path,
                headers={"Authorization": "Bearer " + secret, "Accept": "application/json"},
            )
    except httpx.RequestError:
        raise HTTPException(503, "Identity verification is temporarily unavailable.") from None
    if response.status_code in (401, 403, 404):
        raise HTTPException(401, "Invalid or expired session.")
    if response.status_code != 200:
        raise HTTPException(503, "Identity verification is temporarily unavailable.")
    if len(response.content) > 65536:
        raise HTTPException(503, "Identity verification is temporarily unavailable.")
    try:
        value = response.json()
    except ValueError:
        raise HTTPException(503, "Identity verification is temporarily unavailable.") from None
    if not isinstance(value, dict):
        raise HTTPException(503, "Identity verification is temporarily unavailable.")
    return value


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    settings = get_settings()
    token = credentials.credentials
    if not settings.CLERK_JWT_KEY or not settings.CLERK_ISSUER or not settings.CLERK_SECRET_KEY:
        raise HTTPException(503, "Identity verification is not configured.")
    if len(token) > 16384:
        raise HTTPException(401, "Invalid or expired session.")
    try:
        claims = jwt.decode(
            token,
            settings.CLERK_JWT_KEY.replace("\\n", "\n"),
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER,
            options={"verify_aud": False, "require": ["sub", "sid", "iss", "exp", "iat", "nbf"]},
            leeway=5,
        )
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "Invalid or expired session.") from None
    allowed = {item.strip().rstrip("/") for item in settings.CLERK_AUTHORIZED_PARTIES.split(",") if item.strip()}
    if not allowed or claims.get("azp") not in allowed:
        raise HTTPException(401, "Invalid or expired session.")
    user_id, session_id = claims.get("sub"), claims.get("sid")
    if not all(isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9_]+", item) for item in (user_id, session_id)):
        raise HTTPException(401, "Invalid or expired session.")

    session = await _clerk_object("/sessions/" + session_id, settings.CLERK_SECRET_KEY)
    if session.get("status") != "active" or session.get("user_id") != user_id:
        raise HTTPException(401, "This session has ended. Please sign in again.")
    user = await _clerk_object("/users/" + user_id, settings.CLERK_SECRET_KEY)
    if user.get("id") != user_id or user.get("banned") is True or user.get("locked") is True:
        raise HTTPException(401, "This account is unavailable.")
    primary_id = user.get("primary_email_address_id")
    addresses = user.get("email_addresses") or []
    primary = next((address for address in addresses if isinstance(address, dict) and address.get("id") == primary_id), None)
    email = primary.get("email_address") if primary else None
    verification = primary.get("verification") if primary else None
    if (not isinstance(email, str) or not email or len(email) > 255
            or not isinstance(verification, dict) or verification.get("status") != "verified"):
        raise HTTPException(403, "A verified email address is required.")
    first, last = user.get("first_name"), user.get("last_name")
    full_name = " ".join(item for item in (first, last) if isinstance(item, str))[:255]
    return {"sub": "clerk:" + user_id, "email": email.strip().lower(),
            "email_verified": True, "name": full_name, "provider": "clerk"}
