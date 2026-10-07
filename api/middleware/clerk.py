from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import PyJWTError
from ..config import get_settings

security = HTTPBearer()

# Cache Clerk JWKS keys
_jwks_cache: dict | None = None


async def _fetch_clerk_jwks() -> dict:
    """Fetch Clerk's JWKS for JWT verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    
    settings = get_settings()
    # If CLERK_JWT_KEY is provided (PEM public key), use it directly
    if settings.CLERK_JWT_KEY:
        _jwks_cache = {"pem_key": settings.CLERK_JWT_KEY}
        return _jwks_cache
    
    # Otherwise, we'd need to fetch from Clerk's JWKS endpoint
    # For development, we use the PEM key approach
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="CLERK_JWT_KEY not configured. Set it in .env."
    )


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify a Clerk JWT and return the decoded payload.
    
    Returns the decoded JWT payload containing at minimum:
    - sub: The Clerk user ID
    """
    token = credentials.credentials
    settings = get_settings()
    
    try:
        keys = await _fetch_clerk_jwks()
        
        if "pem_key" in keys:
            issuer = settings.CLERK_ISSUER.strip() or None
            required_claims = ["exp", "iat", "sub"]
            options = {
                "verify_aud": False,  # Clerk session tokens do not always include aud.
                "verify_iss": issuer is not None,
                "require": required_claims,
            }
            if settings.APP_ENV in {"staging", "production"}:
                options["require"].append("iss")
            payload = jwt.decode(
                token,
                keys["pem_key"],
                algorithms=["RS256"],
                issuer=issuer,
                options=options,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No valid Clerk key configuration found."
            )
        
        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim."
            )

        authorized_parties = settings.authorized_parties
        authorized_party = payload.get("azp")
        if settings.APP_ENV in {"staging", "production"} and not authorized_party:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing authorized party claim.",
            )
        if authorized_party and authorized_parties and authorized_party.rstrip("/") not in authorized_parties:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: untrusted authorized party.",
            )
        
        return payload
        
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authorization token."
        )
