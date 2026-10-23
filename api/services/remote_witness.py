"""Verify externally collected cosignatures on private checkpoint anchors.

The API holds only pinned public keys. Each signer must verify the evidence pack
and retain its own last-seen checkpoint outside Argus before signing.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_public_key

from db.cli.witness_config import load_public_keys


_FIELDS = ("checkpoint_id", "sequence_id", "checkpoint_hash", "merkle_root", "signature_hex", "key_id")
_PREFIX = b"argus.private-anchor-witness/v1\n"


def checkpoint_prefix_bytes(checkpoints: Sequence[Mapping[str, Any]], index: int) -> bytes:
    """Sign the whole immutable prefix, not just a single checkpoint row."""
    rows = [{name: checkpoint[name] for name in _FIELDS} for checkpoint in checkpoints[:index + 1]]
    return _PREFIX + json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")


def checkpoint_prefix_digest(checkpoints: Sequence[Mapping[str, Any]], index: int) -> str:
    return hashlib.sha256(checkpoint_prefix_bytes(checkpoints, index)).hexdigest()


def load_trust_domains(directory: str | Path) -> dict[str, str]:
    """A .domain file names the separately operated custody domain for a key."""
    from urllib.parse import unquote

    result: dict[str, str] = {}
    for path in Path(directory).glob("*.domain"):
        if path.is_file():
            domain = path.read_text(encoding="utf-8").strip()
            if domain and len(domain) <= 120:
                result[unquote(path.stem)] = domain
    return result


@dataclass(frozen=True)
class RemoteWitnessResult:
    status: str
    message: str
    total_witnesses: int
    valid_witnesses: int
    independent_trust_domains: bool
    per_witness: list[dict[str, Any]]


def verify_remote_witnesses(
    checkpoints: Sequence[Mapping[str, Any]],
    trust_directory: str | Path,
    *,
    origin_public_key_pem: str,
    threshold: int = 2,
    trust_config_json: str = "",
) -> RemoteWitnessResult:
    """Check signatures, pinned keys and distinct declared custody domains."""
    if not checkpoints:
        return RemoteWitnessResult("unknown", "No private checkpoint anchor is published.", 0, 0, False, [])
    try:
        origin_key = load_pem_public_key(origin_public_key_pem.encode("utf-8"))
        if not isinstance(origin_key, Ed25519PublicKey):
            raise ValueError("Expected an Ed25519 origin key")
        origin_identity = origin_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    except (AttributeError, TypeError, ValueError):
        return RemoteWitnessResult("unknown", "The trusted origin public key is unavailable.", 0, 0, False, [])
    if trust_config_json:
        configuration = json.loads(trust_config_json)
        if not isinstance(configuration, dict):
            raise ValueError("Witness trust configuration must be an object.")
        keys = {name: item.get("public_key_pem") for name, item in configuration.items() if isinstance(name, str) and isinstance(item, dict)}
        domains = {name: item.get("trust_domain") for name, item in configuration.items() if isinstance(name, str) and isinstance(item, dict)}
    else:
        keys = load_public_keys(trust_directory)
        domains = load_trust_domains(trust_directory)
    latest = checkpoints[-1]
    signatures = latest.get("witnesses", [])
    if not isinstance(signatures, list):
        return RemoteWitnessResult("fail", "Witness signatures in the private anchor are malformed.", 0, 0, False, [])
    if not signatures:
        return RemoteWitnessResult("unknown", "No independent witnesses have signed the latest published checkpoint.", 0, 0, False, [])
    if len(signatures) > 20:
        return RemoteWitnessResult("fail", "Too many witness signatures in the private anchor.", len(signatures), 0, False, [])

    payload = checkpoint_prefix_bytes(checkpoints, len(checkpoints) - 1)
    seen_names: set[str] = set()
    seen_keys: set[bytes] = {origin_identity}
    seen_domains: set[str] = set()
    details: list[dict[str, Any]] = []
    valid = 0
    missing_trust = False
    invalid = False
    for signature in signatures:
        name = signature.get("name") if isinstance(signature, dict) else None
        hex_value = signature.get("signature_hex") if isinstance(signature, dict) else None
        reason = ""
        key_pem = keys.get(name) if isinstance(name, str) else None
        configured_domain = domains.get(name) if isinstance(name, str) else None
        domain = configured_domain.strip().casefold() if isinstance(configured_domain, str) else None
        if not isinstance(name, str) or not name or name in seen_names or not isinstance(hex_value, str):
            reason = "Malformed or duplicate witness identity"
            invalid = True
        elif not isinstance(key_pem, str) or not key_pem or not isinstance(domain, str) or not domain:
            reason = "Trusted public key or custody domain is not configured"
            missing_trust = True
        else:
            try:
                key = load_pem_public_key(key_pem.encode("utf-8"))
                if not isinstance(key, Ed25519PublicKey):
                    raise ValueError("Expected an Ed25519 key")
                raw_key = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
                if raw_key in seen_keys or domain in seen_domains:
                    reason = "Signing key or custody domain is already counted"
                    invalid = True
                else:
                    key.verify(bytes.fromhex(hex_value), payload)
                    seen_keys.add(raw_key)
                    seen_domains.add(domain)
                    valid += 1
                    reason = "Signature verified"
            except Exception:
                # Verification failures are evidence failures; do not disclose key material.
                reason = "Invalid witness key or signature"
                invalid = True
        if isinstance(name, str):
            seen_names.add(name)
        details.append({"witness_name": name if isinstance(name, str) else "invalid", "status": "VALID" if reason == "Signature verified" else "UNKNOWN" if reason.startswith("Trusted public key") else "FAILED", "reason": reason, "signature_hex": hex_value if isinstance(hex_value, str) else None, "timestamp": None})

    if invalid:
        return RemoteWitnessResult("fail", "A published witness signature or identity failed verification.", len(signatures), valid, False, details)
    if missing_trust:
        return RemoteWitnessResult("unknown", "A witness public key or independent custody domain has not been configured.", len(signatures), valid, False, details)
    if valid < threshold:
        return RemoteWitnessResult("unknown", f"Only {valid} of {threshold} independent witness signatures are present.", len(signatures), valid, False, details)
    return RemoteWitnessResult("pass", f"{valid} independently configured witness signatures verified on the published checkpoint.", len(signatures), valid, True, details)
