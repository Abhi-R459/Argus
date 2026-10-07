import hashlib
import hmac

import pytest

from db.crypto.actor_context import (
    canonical_actor_payload,
    create_actor_context,
    parse_context_secret,
)


TEST_SECRET = "ab" * 32


def test_actor_context_signature_is_deterministic_for_canonical_payload():
    context = create_actor_context(
        actor_user_id=42,
        actor_employee_id=7,
        db_role="hr_admin",
        secret_hex=TEST_SECRET,
        key_id="key_v1",
        now=1_800_000_000,
    )
    payload = canonical_actor_payload(
        key_id=context["key_id"],
        actor_user_id=int(context["actor_user_id"]),
        actor_employee_id=int(context["actor_employee_id"]),
        db_role=context["db_role"],
        nonce=context["nonce"],
        issued_at=int(context["issued_at"]),
        expires_at=int(context["expires_at"]),
    )

    expected = hmac.new(parse_context_secret(TEST_SECRET), payload, hashlib.sha256).hexdigest()
    assert context["signature"] == expected
    assert context["expires_at"] == str(int(context["issued_at"]) + 30)


def test_actor_context_binds_database_role_and_actor_fields():
    context = create_actor_context(
        actor_user_id=42,
        actor_employee_id=7,
        db_role="hr_admin",
        secret_hex=TEST_SECRET,
        now=1_800_000_000,
    )
    original = canonical_actor_payload(
        key_id=context["key_id"],
        actor_user_id=42,
        actor_employee_id=7,
        db_role="hr_admin",
        nonce=context["nonce"],
        issued_at=int(context["issued_at"]),
        expires_at=int(context["expires_at"]),
    )
    changed_actor = canonical_actor_payload(
        key_id=context["key_id"],
        actor_user_id=43,
        actor_employee_id=7,
        db_role="hr_admin",
        nonce=context["nonce"],
        issued_at=int(context["issued_at"]),
        expires_at=int(context["expires_at"]),
    )
    changed_role = canonical_actor_payload(
        key_id=context["key_id"],
        actor_user_id=42,
        actor_employee_id=7,
        db_role="compliance_auditor",
        nonce=context["nonce"],
        issued_at=int(context["issued_at"]),
        expires_at=int(context["expires_at"]),
    )

    assert original != changed_actor
    assert original != changed_role


@pytest.mark.parametrize("secret", ["", "too-short", "zz" * 32, "ab" * 31])
def test_context_secret_rejects_missing_malformed_or_short_values(secret):
    with pytest.raises(ValueError, match="AUDIT_CONTEXT_SECRET"):
        parse_context_secret(secret)


def test_context_rejects_unexpected_database_roles_and_long_lifetimes():
    with pytest.raises(ValueError, match="database role"):
        create_actor_context(
            actor_user_id=42,
            actor_employee_id=7,
            db_role="postgres",
            secret_hex=TEST_SECRET,
        )
    with pytest.raises(ValueError, match="60 seconds"):
        canonical_actor_payload(
            key_id="v1",
            actor_user_id=42,
            actor_employee_id=7,
            db_role="hr_admin",
            nonce="00000000-0000-0000-0000-000000000000",
            issued_at=100,
            expires_at=161,
        )
