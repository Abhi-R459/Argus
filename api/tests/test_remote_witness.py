"""Independent witness signatures require pinned, distinct external identities."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from api.services.remote_witness import checkpoint_prefix_bytes, verify_remote_witnesses

ORIGIN_PRIVATE = Ed25519PrivateKey.generate()
ORIGIN_PEM = ORIGIN_PRIVATE.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()


def _checkpoint(identifier: int) -> dict:
    return {
        "checkpoint_id": identifier, "sequence_id": identifier * 25,
        "checkpoint_hash": "a" * 64, "merkle_root": "b" * 64,
        "signature_hex": "c" * 128, "key_id": "origin-key",
    }


def _configure(tmp_path, name: str, domain: str, key: Ed25519PrivateKey) -> None:
    (tmp_path / f"{name}.pem").write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    (tmp_path / f"{name}.domain").write_text(domain, encoding="utf-8")


def test_two_distinct_pinned_witnesses_verify_and_tampering_fails(tmp_path):
    checkpoints = [_checkpoint(1), _checkpoint(2)]
    first = Ed25519PrivateKey.generate()
    second = Ed25519PrivateKey.generate()
    _configure(tmp_path, "auditor.one", "operator-one", first)
    _configure(tmp_path, "auditor.two", "operator-two", second)
    payload = checkpoint_prefix_bytes(checkpoints, 1)
    checkpoints[-1]["witnesses"] = [
        {"name": "auditor.one", "signature_hex": first.sign(payload).hex()},
        {"name": "auditor.two", "signature_hex": second.sign(payload).hex()},
    ]
    verified = verify_remote_witnesses(checkpoints, tmp_path, origin_public_key_pem=ORIGIN_PEM)
    assert verified.status == "pass"
    assert verified.independent_trust_domains is True
    assert verified.valid_witnesses == 2

    changed = json.loads(json.dumps(checkpoints))
    changed[0]["merkle_root"] = "f" * 64
    assert verify_remote_witnesses(changed, tmp_path, origin_public_key_pem=ORIGIN_PEM).status == "fail"


def test_one_operator_or_key_cannot_count_twice(tmp_path):
    checkpoints = [_checkpoint(1)]
    first = Ed25519PrivateKey.generate()
    second = Ed25519PrivateKey.generate()
    _configure(tmp_path, "auditor.one", "same-operator", first)
    _configure(tmp_path, "auditor.two", "SAME-OPERATOR", second)
    payload = checkpoint_prefix_bytes(checkpoints, 0)
    checkpoints[0]["witnesses"] = [
        {"name": "auditor.one", "signature_hex": first.sign(payload).hex()},
        {"name": "auditor.two", "signature_hex": second.sign(payload).hex()},
    ]
    assert verify_remote_witnesses(checkpoints, tmp_path, origin_public_key_pem=ORIGIN_PEM).status == "fail"
    (tmp_path / "auditor.two.domain").write_text("other-operator", encoding="utf-8")
    _configure(tmp_path, "auditor.two", "other-operator", first)
    checkpoints[0]["witnesses"][1]["signature_hex"] = first.sign(payload).hex()
    assert verify_remote_witnesses(checkpoints, tmp_path, origin_public_key_pem=ORIGIN_PEM).status == "fail"


def test_origin_signing_key_cannot_be_a_witness(tmp_path):
    checkpoints = [_checkpoint(1)]
    second = Ed25519PrivateKey.generate()
    _configure(tmp_path, "auditor.one", "operator-one", ORIGIN_PRIVATE)
    _configure(tmp_path, "auditor.two", "operator-two", second)
    payload = checkpoint_prefix_bytes(checkpoints, 0)
    checkpoints[0]["witnesses"] = [
        {"name": "auditor.one", "signature_hex": ORIGIN_PRIVATE.sign(payload).hex()},
        {"name": "auditor.two", "signature_hex": second.sign(payload).hex()},
    ]
    assert verify_remote_witnesses(checkpoints, tmp_path, origin_public_key_pem=ORIGIN_PEM).status == "fail"


def test_missing_operator_configuration_does_not_create_quorum(tmp_path):
    checkpoints = [_checkpoint(1)]
    key = Ed25519PrivateKey.generate()
    checkpoints[0]["witnesses"] = [{"name": "auditor.one", "signature_hex": key.sign(checkpoint_prefix_bytes(checkpoints, 0)).hex()}]
    assert verify_remote_witnesses(checkpoints, tmp_path, origin_public_key_pem=ORIGIN_PEM).status == "unknown"


def test_render_trust_configuration_accepts_public_keys_only(tmp_path):
    checkpoints = [_checkpoint(1)]
    first = Ed25519PrivateKey.generate()
    second = Ed25519PrivateKey.generate()
    payload = checkpoint_prefix_bytes(checkpoints, 0)
    configuration = {}
    for name, domain, key in (("auditor.one", "operator-one", first), ("auditor.two", "operator-two", second)):
        configuration[name] = {
            "public_key_pem": key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode(),
            "trust_domain": domain,
        }
    checkpoints[0]["witnesses"] = [
        {"name": "auditor.one", "signature_hex": first.sign(payload).hex()},
        {"name": "auditor.two", "signature_hex": second.sign(payload).hex()},
    ]
    result = verify_remote_witnesses(checkpoints, tmp_path, origin_public_key_pem=ORIGIN_PEM, trust_config_json=json.dumps(configuration))
    assert result.status == "pass"


@pytest.mark.asyncio
async def test_live_anchor_endpoint_uses_pinned_external_witnesses(client_auditor, mock_db_session, monkeypatch, tmp_path):
    from api.config import get_settings
    from api.routers import audits

    checkpoint = _checkpoint(1)
    first = Ed25519PrivateKey.generate()
    second = Ed25519PrivateKey.generate()
    _configure(tmp_path, "auditor.one", "operator-one", first)
    _configure(tmp_path, "auditor.two", "operator-two", second)
    payload = checkpoint_prefix_bytes([checkpoint], 0)
    checkpoint["witnesses"] = [
        {"name": "auditor.one", "signature_hex": first.sign(payload).hex()},
        {"name": "auditor.two", "signature_hex": second.sign(payload).hex()},
    ]
    settings = get_settings().model_copy(update={
        "ANCHOR_STORE": "github_repo", "GITHUB_ANCHOR_REPOSITORY": "owner/anchors",
        "GITHUB_ANCHOR_TOKEN": "read-only-test-token", "GITHUB_ANCHOR_MIN_SEQUENCE": 1,
        "WITNESS_PUBLIC_KEYS_DIR": str(tmp_path),
        "CHECKPOINT_PUBLIC_KEYS_DIR": str(tmp_path),
    })
    (tmp_path / "origin-key.pem").write_text(ORIGIN_PEM, encoding="utf-8")
    monkeypatch.setattr(audits, "get_settings", lambda: settings)
    monkeypatch.setattr(audits, "fetch_manifest", lambda *args: {"schema_version": 1, "published_at": datetime.now(timezone.utc).isoformat(), "checkpoints": [checkpoint]})

    latest = MagicMock()
    latest.first.return_value = (1, 25, "a" * 64, datetime.now(timezone.utc), "origin-key")
    tail = MagicMock()
    tail.first.return_value = (25,)
    schedule = MagicMock()
    schedule.first.return_value = (False, 25)
    database_rows = MagicMock()
    database_rows.all.return_value = [(1, 25, "a" * 64, "b" * 64, bytes.fromhex("c" * 128), "origin-key")]
    mock_db_session.execute.side_effect = [latest, tail, schedule, database_rows]

    response = await client_auditor.get("/api/anchor/status")
    assert response.status_code == 200
    report = response.json()["witness_report"]
    assert report["verification_status"] == "pass"
    assert report["independent_trust_domains"] is True
    assert report["cosigned_witnesses"] == 2
