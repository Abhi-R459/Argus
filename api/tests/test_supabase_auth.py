from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.error import HTTPError, URLError

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.middleware import supabase_auth as auth

URL = "https://abcdefghijklmnopqrst.supabase.co"
USER = "1ac1a96e-09fb-4dc8-a34a-cc2ac0dbe699"
SESSION = "ab8c1e92-e2c0-44ea-8f31-6fb78bddba4f"


def token(**changes):
    now = datetime.now(timezone.utc)
    claims = {"sub": USER, "session_id": SESSION, "iss": URL + "/auth/v1",
              "aud": "authenticated", "role": "authenticated",
              "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=5)).timestamp())}
    claims.update(changes)
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=jwt.encode(claims, "inert-test-key" * 4, algorithm="HS256"))


@pytest.fixture
def identity(monkeypatch):
    user = {"id": USER, "email": "hr@example.test", "email_confirmed_at": "2026-10-11T00:00:00Z",
            "identities": [{"provider": "google", "identity_data": {
                "email": "hr@example.test", "email_verified": True}}],
            "user_metadata": {"full_name": "Approved HR", "role": "compliance_auditor"}}
    fetch = MagicMock(return_value=user)
    active = AsyncMock(return_value=True)
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(
        SUPABASE_URL=URL, SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
        HR_ADMIN_EMAILS="hr@example.test", COMPLIANCE_AUDITOR_EMAILS="audit@example.test"))
    monkeypatch.setattr(auth, "_fetch_authenticated_user", fetch)
    monkeypatch.setattr(auth, "_session_is_active", active)
    return user, fetch, active


@pytest.mark.asyncio
async def test_trusted_google_identity_and_server_allowlist_determine_role(identity):
    result = await auth.verify_supabase_token(token())
    assert result["sub"] == "supabase:" + USER
    assert result["email_verified"] is True
    assert result["argus_role"] == "hr_admin"
    identity[1].assert_called_once()
    identity[2].assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("claims", [
    {"iss": "https://other.supabase.co/auth/v1"}, {"aud": "service_role"},
    {"role": "service_role"}, {"sub": "invalid"}, {"session_id": "invalid"},
    {"is_anonymous": True}, {"exp": 1}, {"iat": 9999999999},
])
async def test_invalid_claims_never_reach_identity_or_database(identity, claims):
    with pytest.raises(HTTPException) as exc:
        await auth.verify_supabase_token(token(**claims))
    assert exc.value.status_code == 401
    identity[1].assert_not_called()
    identity[2].assert_not_awaited()


@pytest.mark.asyncio
async def test_signature_rejection_never_falls_back_to_decoded_claims(identity):
    identity[1].side_effect = HTTPException(401, "Invalid session")
    with pytest.raises(HTTPException) as exc:
        await auth.verify_supabase_token(token())
    assert exc.value.status_code == 401
    identity[2].assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["wrong_id", "unconfirmed", "anonymous", "email_provider", "unverified_google", "mismatched_email", "not_approved", "metadata_only"])
async def test_untrusted_or_unapproved_profiles_are_rejected(identity, case):
    user = identity[0]
    if case == "wrong_id": user["id"] = SESSION
    elif case == "unconfirmed": user["email_confirmed_at"] = None
    elif case == "anonymous": user["is_anonymous"] = True
    elif case == "email_provider": user["identities"][0]["provider"] = "email"
    elif case == "unverified_google": user["identities"][0]["identity_data"]["email_verified"] = False
    elif case == "mismatched_email": user["identities"][0]["identity_data"]["email"] = "different@example.test"
    elif case == "not_approved":
        user["email"] = user["identities"][0]["identity_data"]["email"] = "other@example.test"
    else:
        user["identities"] = []
        user["user_metadata"]["email_verified"] = True
    with pytest.raises(HTTPException) as exc:
        await auth.verify_supabase_token(token())
    assert exc.value.status_code in (401, 403)
    identity[2].assert_not_awaited()


@pytest.mark.asyncio
async def test_signed_out_session_cannot_access_api(identity):
    identity[2].return_value = False
    with pytest.raises(HTTPException) as exc:
        await auth.verify_supabase_token(token())
    assert exc.value.status_code == 401


@pytest.mark.parametrize("profile", [
    {"email": "other@example.test", "email_verified": True, "argus_role": "hr_admin"},
    {"email": "hr@example.test", "email_verified": True, "argus_role": "compliance_auditor"},
    {"email": "hr@example.test", "email_verified": False, "argus_role": "hr_admin"},
])
def test_linked_account_cannot_keep_access_after_identity_changes(profile):
    with pytest.raises(HTTPException) as exc:
        auth.validate_local_access(SimpleNamespace(email="hr@example.test", role="hr_admin"), profile)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("failure,status", [
    (HTTPError(URL, 401, "unauthorized", {}, None), 401),
    (HTTPError(URL, 500, "PRIVATE AUTH ERROR", {}, None), 503),
    (HTTPError(URL, 302, "redirect", {}, None), 503),
    (URLError("PRIVATE NETWORK ERROR"), 503),
])
def test_auth_server_failures_are_bounded_and_redacted(monkeypatch, failure, status):
    opener = MagicMock()
    opener.open.side_effect = failure
    monkeypatch.setattr(auth, "build_opener", lambda *args: opener)
    with pytest.raises(HTTPException) as exc:
        auth._fetch_authenticated_user("private-token", URL, "sb_publishable_test")
    assert exc.value.status_code == status
    assert "PRIVATE" not in exc.value.detail
    assert opener.open.call_args.kwargs["timeout"] == 5


def test_auth_tokens_cannot_be_forwarded_to_redirects():
    assert auth._NoRedirects().redirect_request(None, None, 302, "", {}, "https://other.example") is None
