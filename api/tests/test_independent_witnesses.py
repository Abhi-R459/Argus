"""Independent readback must bind two signatures to the database prefix."""

import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from api.services import independent_witnesses
from api.services.remote_witness import RemoteWitnessResult, checkpoint_prefix_bytes
from scripts import publish_witness_quorum


def _pem(key):
    return key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()


def _setup():
    origin = Ed25519PrivateKey.generate()
    witnesses = {"operator.one": Ed25519PrivateKey.generate(),
                 "operator.two": Ed25519PrivateKey.generate()}
    checkpoints = []
    for identifier in (1, 2):
        checkpoint_hash = f"{identifier:064x}"
        merkle_root = f"{identifier + 10:064x}"
        checkpoints.append({
            "checkpoint_id": identifier, "sequence_id": identifier * 25,
            "checkpoint_hash": checkpoint_hash, "merkle_root": merkle_root,
            "signature_hex": origin.sign(f"{checkpoint_hash}:{merkle_root}".encode()).hex(),
            "key_id": "local:ed25519:v1",
        })
    services = [{"name": name, "url": f"https://{name}.example", "token": name * 10}
                for name in witnesses]
    trust = {name: {"public_key_pem": _pem(key), "trust_domain": name}
             for name, key in witnesses.items()}
    return _pem(origin), witnesses, checkpoints, json.dumps(services), json.dumps(trust)


def _transport(checkpoints, witnesses, *, fork=False, lag=False, publish_tokens=None,
               read_tokens=None):
    async def respond(request):
        name = request.url.host.removesuffix(".example")
        if request.method == "POST":
            if publish_tokens is not None and request.headers.get("authorization") != f"Bearer {publish_tokens[name]}":
                return httpx.Response(401)
            return httpx.Response(200, json={"accepted": True})
        if read_tokens is not None and request.headers.get("authorization") != f"Bearer {read_tokens[name]}":
            return httpx.Response(401)
        rows = checkpoints[:-1] if lag and name == "operator.two" else [dict(row) for row in checkpoints]
        if fork and name == "operator.two":
            rows[0]["checkpoint_hash"] = "f" * 64
        payload = checkpoint_prefix_bytes(rows, len(rows) - 1)
        return httpx.Response(200, json={
            "schema_version": 1, "name": name, "checkpoints": rows,
            "signature_hex": witnesses[name].sign(payload).hex(),
            "prefix_sha256": hashlib.sha256(payload).hexdigest(),
        })
    return httpx.MockTransport(respond)


@pytest.mark.asyncio
async def test_two_witnesses_pass_and_fork_or_lag_fails_closed(monkeypatch):
    origin_pem, witnesses, rows, endpoints, trust = _setup()
    real_client = httpx.AsyncClient
    for fork, lag, expected in ((False, False, "pass"), (True, False, "fail"), (False, True, "unknown")):
        transport = _transport(rows, witnesses, fork=fork, lag=lag)
        monkeypatch.setattr(independent_witnesses.httpx, "AsyncClient",
                            lambda **kwargs: real_client(transport=transport, **kwargs))
        result = await independent_witnesses.compare_independent_witnesses(
            rows, endpoints_json=endpoints, trust_json=trust,
            origin_public_key_pem=origin_pem, threshold=2, minimum_sequence=25,
        )
        assert result.status == expected
        assert result.witnesses.independent_trust_domains is (expected == "pass")


@pytest.mark.asyncio
async def test_new_partial_checkpoint_does_not_displace_completed_witness_head(monkeypatch):
    origin_pem, witnesses, rows, endpoints, trust = _setup()
    partial = {**rows[-1], "checkpoint_id": 3, "sequence_id": 60}
    real_client = httpx.AsyncClient
    transport = _transport(rows, witnesses)
    monkeypatch.setattr(independent_witnesses.httpx, "AsyncClient",
                        lambda **kwargs: real_client(transport=transport, **kwargs))
    result = await independent_witnesses.compare_independent_witnesses(
        rows + [partial], endpoints_json=endpoints, trust_json=trust,
        origin_public_key_pem=origin_pem, threshold=2,
        minimum_sequence=25, rolling_interval=25,
    )
    assert result.status == "pass"
    assert result.anchored_sequence == 50


@pytest.mark.asyncio
async def test_same_witness_host_cannot_count_as_two_independent_services():
    origin_pem, _, rows, endpoints, trust = _setup()
    configured = json.loads(endpoints)
    configured[1]["url"] = configured[0]["url"]
    result = await independent_witnesses.compare_independent_witnesses(
        rows, endpoints_json=json.dumps(configured), trust_json=trust,
        origin_public_key_pem=origin_pem, threshold=2,
    )
    assert result.status == "unknown"
    assert not result.witnesses.independent_trust_domains


@pytest.mark.asyncio
async def test_publisher_checks_signed_readback_before_reporting_success(monkeypatch):
    origin_pem, witnesses, rows, endpoints, trust = _setup()
    publish_services = json.loads(endpoints)
    read_services = [{**service, "token": "read-" + service["token"]}
                     for service in publish_services]
    read_endpoints = json.dumps(read_services)
    publish_tokens = {service["name"]: service["token"] for service in publish_services}
    read_tokens = {service["name"]: service["token"] for service in read_services}

    async def fake_database(_url):
        return rows

    monkeypatch.setattr(publish_witness_quorum, "database_checkpoints", fake_database)
    async with httpx.AsyncClient(transport=_transport(
            rows, witnesses, publish_tokens=publish_tokens, read_tokens=read_tokens)) as client:
        result = await publish_witness_quorum.publish_once(
            database_url="unused", origin_pem=origin_pem, services_raw=endpoints,
            read_services_raw=read_endpoints, trust_raw=trust, client=client,
        )
    assert "2 witnesses retained checkpoint sequence 50" in result

    async with httpx.AsyncClient(transport=_transport(
            rows, witnesses, fork=True, publish_tokens=publish_tokens,
            read_tokens=read_tokens)) as client:
        with pytest.raises(ValueError, match="readback"):
            await publish_witness_quorum.publish_once(
                database_url="unused", origin_pem=origin_pem, services_raw=endpoints,
                read_services_raw=read_endpoints, trust_raw=trust, client=client,
            )

    async with httpx.AsyncClient(transport=_transport(rows, witnesses)) as client:
        with pytest.raises(ValueError, match="separate read token"):
            await publish_witness_quorum.publish_once(
                database_url="unused", origin_pem=origin_pem, services_raw=endpoints,
                read_services_raw=endpoints, trust_raw=trust, client=client,
            )


@pytest.mark.asyncio
async def test_oversized_witness_readback_is_rejected():
    async def oversized(_request):
        return httpx.Response(200, content=b"x" * 1_000_001)

    async with httpx.AsyncClient(transport=httpx.MockTransport(oversized)) as client:
        with pytest.raises(ValueError, match="size limit"):
            await independent_witnesses.fetch_witness_head(
                client, "https://operator.example", "read-token-for-test-0123456789abcdef",
            )


@pytest.mark.asyncio
async def test_anchor_status_uses_independent_witness_readback(client_auditor, mock_db_session, monkeypatch, tmp_path):
    from api.config import get_settings
    from api.routers import audits

    origin_pem, _, rows, endpoints, trust = _setup()
    (tmp_path / "public_key.pem").write_text(origin_pem, encoding="utf-8")
    settings = get_settings().model_copy(update={
        "ANCHOR_STORE": "witness_services",
        "WITNESS_READ_ENDPOINTS_JSON": endpoints,
        "WITNESS_TRUST_CONFIG_JSON": trust,
        "WITNESS_MIN_SEQUENCE": 25,
        "CHECKPOINT_PUBLIC_KEYS_DIR": str(tmp_path),
    })
    monkeypatch.setattr(audits, "get_settings", lambda: settings)
    async def fake_compare(*args, **kwargs):
        return independent_witnesses.IndependentWitnessComparison(
            "pass", "Two retained prefixes match.", 50,
            RemoteWitnessResult("pass", "Two signatures verified.", 2, 2, True, []),
        )
    monkeypatch.setattr(audits, "compare_independent_witnesses", fake_compare)
    latest = MagicMock()
    latest.first.return_value = (2, 50, rows[-1]["checkpoint_hash"], datetime.now(timezone.utc), rows[-1]["key_id"])
    tail = MagicMock()
    tail.first.return_value = (50,)
    schedule = MagicMock()
    schedule.first.return_value = (True, 25)
    checkpoint_rows = MagicMock()
    checkpoint_rows.all.return_value = [
        (row["checkpoint_id"], row["sequence_id"], row["checkpoint_hash"], row["merkle_root"],
         bytes.fromhex(row["signature_hex"]), row["key_id"]) for row in rows
    ]
    mock_db_session.execute.side_effect = [latest, tail, schedule, checkpoint_rows]
    result = await client_auditor.get("/api/anchor/status")
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "ANCHORED"
    assert body["witness_report"]["quorum_satisfied"] is True
    assert body["witness_report"]["independent_trust_domains"] is True
