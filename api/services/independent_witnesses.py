"""Read and verify independently retained checkpoint prefixes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_public_key

from .remote_witness import RemoteWitnessResult, checkpoint_prefix_bytes, verify_remote_witnesses


def validate_services(raw: str, trust_raw: str, origin_pem: str) -> list[dict]:
    services = json.loads(raw)
    trust = json.loads(trust_raw)
    if not isinstance(services, list) or not 2 <= len(services) <= 20 or not isinstance(trust, dict):
        raise ValueError("At least two witness services and pinned public keys are required.")
    origin = load_pem_public_key(origin_pem.encode("utf-8"))
    if not isinstance(origin, Ed25519PublicKey):
        raise ValueError("The origin key must be Ed25519.")
    names: set[str] = set()
    domains: set[str] = set()
    hosts: set[str] = set()
    tokens: set[str] = set()
    keys: set[bytes] = {origin.public_bytes(Encoding.Raw, PublicFormat.Raw)}
    for item in services:
        if not isinstance(item, dict) or set(item) != {"name", "url", "token"}:
            raise ValueError("Witness endpoint configuration is invalid.")
        name, url, token = item["name"], item["url"], item["token"]
        parsed = urlsplit(url) if isinstance(url, str) else None
        if (not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", name)
                or name in names or parsed is None or parsed.scheme != "https"
                or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or parsed.hostname.casefold() in hosts
                or not isinstance(token, str) or len(token) < 32 or token in tokens):
            raise ValueError("Each witness needs a distinct HTTPS origin and a long access token.")
        entry = trust.get(name)
        if not isinstance(entry, dict):
            raise ValueError("A pinned witness key and custody domain are required.")
        domain = entry.get("trust_domain")
        if not isinstance(domain, str) or not domain.strip() or domain.strip().casefold() in domains:
            raise ValueError("Witness custody domains must be distinct.")
        key = load_pem_public_key(str(entry.get("public_key_pem", "")).encode("utf-8"))
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("A witness key must be Ed25519.")
        raw_key = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        if raw_key in keys:
            raise ValueError("Witness keys must differ from each other and the origin.")
        names.add(name)
        domains.add(domain.strip().casefold())
        hosts.add(parsed.hostname.casefold())
        tokens.add(token)
        keys.add(raw_key)
    return services


@dataclass(frozen=True)
class IndependentWitnessComparison:
    status: str  # pass | unknown | fail
    detail: str
    anchored_sequence: int
    witnesses: RemoteWitnessResult


def _unknown(detail: str, sequence: int = 0) -> IndependentWitnessComparison:
    return IndependentWitnessComparison("unknown", detail, sequence,
        RemoteWitnessResult("unknown", detail, 0, 0, False, []))


def _fail(detail: str, sequence: int = 0) -> IndependentWitnessComparison:
    return IndependentWitnessComparison("fail", detail, sequence,
        RemoteWitnessResult("fail", detail, 0, 0, False, []))


async def fetch_witness_head(client: httpx.AsyncClient, url: str, token: str) -> dict[str, Any]:
    """Bound remote evidence before JSON parsing; never follow redirects."""
    raw = bytearray()
    async with client.stream("GET", url.rstrip("/") + "/v1/head",
                             headers={"Authorization": f"Bearer {token}"},
                             follow_redirects=False) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            raw.extend(chunk)
            if len(raw) > 1_000_000:
                raise ValueError("Witness response exceeds the size limit.")
    head = json.loads(raw)
    if not isinstance(head, dict):
        raise ValueError("Witness response is malformed.")
    return head


async def compare_independent_witnesses(
    database_checkpoints: Sequence[Mapping[str, Any]],
    *, endpoints_json: str, trust_json: str, origin_public_key_pem: str,
    threshold: int, minimum_sequence: int = 0, rolling_interval: int | None = None,
) -> IndependentWitnessComparison:
    """Require a pinned, distinct quorum on the latest completed DB prefix.

    A remote fork is a failure; a missing or lagging service is unknown. Status
    never becomes pass merely because the application database contains rows.
    """
    try:
        endpoints = json.loads(endpoints_json)
        if not isinstance(endpoints, list) or len(endpoints) < threshold or len(endpoints) > 20:
            return _unknown("Independent witness endpoints are not configured.")
        names = [item.get("name") for item in endpoints if isinstance(item, dict)]
        if len(names) != len(endpoints) or any(not isinstance(name, str) for name in names) or len(set(names)) != len(names):
            return _unknown("Independent witness identities are invalid.")
    except (TypeError, ValueError):
        return _unknown("Independent witness endpoints are not configured.")
    rows = list(database_checkpoints)
    if rolling_interval and rolling_interval > 0:
        completed = [row["sequence_id"] for row in rows if row["sequence_id"] % rolling_interval == 0]
        rows = [row for row in rows if row["sequence_id"] <= completed[-1]] if completed else []
    if not rows:
        return _unknown("No completed signed checkpoint is ready for witnesses.")
    latest_sequence = int(rows[-1]["sequence_id"])
    if latest_sequence < minimum_sequence:
        return _unknown("The minimum independently witnessed sequence is not available.")
    payload = checkpoint_prefix_bytes(rows, len(rows) - 1)
    digest = hashlib.sha256(payload).hexdigest()
    signatures = []
    failures = []
    async with httpx.AsyncClient(timeout=6.0, trust_env=False) as client:
        for endpoint in endpoints:
            name, url, token = endpoint.get("name"), endpoint.get("url"), endpoint.get("token")
            parsed = urlsplit(url) if isinstance(url, str) else None
            if (not isinstance(name, str) or not isinstance(token, str) or not token
                    or parsed is None or parsed.scheme != "https" or not parsed.hostname
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path not in ("", "/")):
                failures.append("A witness endpoint configuration is invalid.")
                continue
            try:
                head = await fetch_witness_head(client, url, token)
                if head.get("schema_version") != 1 or head.get("name") != name:
                    raise ValueError("Witness identity or schema differs from its pinned configuration.")
                published = head.get("checkpoints")
                if not isinstance(published, list) or len(published) > len(rows):
                    raise ValueError("Witness history is malformed or exceeds the database history.")
                if published != rows[:len(published)]:
                    return _fail(f"Witness {name} retained a checkpoint history that disagrees with the database.", latest_sequence)
                if len(published) != len(rows):
                    failures.append(f"Witness {name} has not retained the latest checkpoint.")
                    continue
                if head.get("prefix_sha256") != digest:
                    raise ValueError("Witness prefix digest differs.")
                signatures.append({"name": name, "signature_hex": head.get("signature_hex")})
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                failures.append(f"Witness {name} could not be read and verified.")
    verified_rows = [dict(row) for row in rows]
    verified_rows[-1]["witnesses"] = signatures
    try:
        result = verify_remote_witnesses(
            verified_rows, "", origin_public_key_pem=origin_public_key_pem,
            threshold=threshold, trust_config_json=trust_json,
        )
    except (ValueError, TypeError, KeyError):
        return _unknown("Pinned witness public keys are unavailable.", latest_sequence)
    if result.status == "fail":
        return IndependentWitnessComparison("fail", result.message, latest_sequence, result)
    if result.status != "pass":
        detail = failures[0] if failures else result.message
        return IndependentWitnessComparison("unknown", detail, latest_sequence, result)
    return IndependentWitnessComparison("pass", result.message, latest_sequence, result)
