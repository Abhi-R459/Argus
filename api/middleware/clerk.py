from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from functools import lru_cache
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
            # Decode using the PEM public key
            payload = jwt.decode(
                token,
                keys["pem_key"],
                algorithms=["RS256"],
                options={"verify_aud": False},  # Clerk doesn't always set aud
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
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authorization token."
        )
