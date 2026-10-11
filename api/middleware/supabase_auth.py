"""Validate identity with Supabase Auth and enforce immediate session revocation.

The Auth server verifies the token signature. Only after that succeeds do we
consume its claims. No JWT signing secret or service-role key is needed here.
"""

import asyncio
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from ..config import get_settings
from ..database import get_session_factory

security = HTTPBearer()


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an access token or API key to a redirect destination.
        return None


def _fetch_authenticated_user(token: str, url: str, publishable_key: str) -> dict:
    request = Request(url + "/auth/v1/user", headers={
        "apikey": publishable_key, "Authorization": "Bearer " + token,
        "Accept": "application/json",
    })
    try:
        with build_opener(_NoRedirects()).open(request, timeout=5) as response:
            if response.status != 200:
                raise HTTPException(503, "Identity verification is temporarily unavailable.")
            body = response.read(65537)
            if len(body) > 65536:
                raise ValueError("Oversized identity response")
            user = json.loads(body)
            if not isinstance(user, dict):
                raise ValueError("Invalid identity response")
            return user
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise HTTPException(401, "Invalid or expired session.") from None
        raise HTTPException(503, "Identity verification is temporarily unavailable.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(503, "Identity verification is temporarily unavailable.") from None


async def _session_is_active(user_id: UUID, session_id: UUID) -> bool:
    async with get_session_factory("hr_admin")() as session:
        result = await session.execute(text(
            "SELECT argus_private.supabase_session_active(:user_id, :session_id)"
        ), {"user_id": user_id, "session_id": session_id})
        return result.scalar_one() is True


def provisioned_role(email: str) -> str | None:
    settings = get_settings()
    normalized = email.strip().lower()
    for role, values in (("hr_admin", settings.HR_ADMIN_EMAILS),
                         ("compliance_auditor", settings.COMPLIANCE_AUDITOR_EMAILS)):
        if normalized in {item.strip().lower() for item in values.split(",") if item.strip()}:
            return role
    return None


async def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    settings = get_settings()
    # Restrict outbound identity requests even during local development.
    if not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", settings.SUPABASE_URL) or not re.fullmatch(
        r"sb_publishable_[A-Za-z0-9_-]+", settings.SUPABASE_PUBLISHABLE_KEY
    ):
        raise HTTPException(503, "Identity verification is not configured.")
    token = credentials.credentials
    if len(token) > 16384:
        raise HTTPException(401, "Invalid or expired session.")
    try:
        if jwt.get_unverified_header(token).get("alg") not in {"HS256", "RS256", "ES256"}:
            raise jwt.InvalidTokenError()
        # This preflight rejects malformed/expired tokens cheaply. None of these
        # claims authorize access until the Auth server verifies the signature.
        claims = jwt.decode(token, options={
            "verify_signature": False, "verify_exp": True, "verify_iat": True,
            "verify_nbf": True, "verify_iss": True, "verify_aud": True,
            "require": ["sub", "iss", "aud", "exp", "iat", "session_id"],
        }, issuer=settings.SUPABASE_URL + "/auth/v1", audience="authenticated")
        user_id, session_id = UUID(claims["sub"]), UUID(claims["session_id"])
        if claims.get("role") != "authenticated" or claims.get("is_anonymous") is True:
            raise jwt.InvalidTokenError()
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise HTTPException(401, "Invalid or expired session.") from None

    user = await asyncio.to_thread(_fetch_authenticated_user, token,
                                   settings.SUPABASE_URL, settings.SUPABASE_PUBLISHABLE_KEY)
    if user.get("id") != str(user_id) or user.get("is_anonymous") is True:
        raise HTTPException(401, "Invalid or expired session.")
    email = user.get("email")
    if not isinstance(email, str) or not email or len(email) > 255 or not user.get("email_confirmed_at"):
        raise HTTPException(403, "A verified Google account is required.")
    email = email.strip().lower()
    # Google identity data is maintained by Auth, unlike editable user_metadata.
    google_verified = any(
        identity.get("provider") == "google"
        and isinstance(identity.get("identity_data"), dict)
        and identity["identity_data"].get("email_verified") is True
        and str(identity["identity_data"].get("email", "")).strip().lower() == email
        for identity in (user.get("identities") or []) if isinstance(identity, dict)
    )
    if not google_verified:
        raise HTTPException(403, "A verified Google account is required.")
    role = provisioned_role(email)
    if role is None:
        raise HTTPException(403, "This account has not been provisioned for Argus.")
    if not await _session_is_active(user_id, session_id):
        raise HTTPException(401, "This session has ended. Please sign in again.")
    metadata = user.get("user_metadata") or {}
    name = metadata.get("full_name", "") if isinstance(metadata, dict) else ""
    return {"sub": "supabase:" + str(user_id), "email": email,
            "email_verified": True, "argus_role": role,
            "name": name[:255] if isinstance(name, str) else ""}


def validate_local_access(user, identity: dict) -> None:
    """A linked account cannot keep privileges after its approved identity changes."""
    if (identity.get("email_verified") is not True
        or identity.get("argus_role") != user.role
        or str(identity.get("email", "")).strip().lower() != user.email.strip().lower()):
        raise HTTPException(403, "This account is not approved for this workspace.")
