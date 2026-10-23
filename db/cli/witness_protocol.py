#!/usr/bin/env python3
"""Argus's local multi-signature checkpoint reference protocol.

This custom note format is inspired by transparency witnesses, but is not an
RFC 9162 or C2SP implementation. It can verify pinned signatures and detect
two different roots at one sequence; it cannot prove append-only consistency
or independent key custody on its own. Production uses the separately
operated private-anchor witness workflow in api.services.remote_witness.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("argus.witness_protocol")

# Standard Note Header
DEFAULT_NOTE_ORIGIN = "argus.enterprise/v1/checkpoint"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WitnessProtocolError(Exception):
    """Base exception for witness protocol errors."""
    pass


class QuorumNotMetError(WitnessProtocolError):
    """Raised when the collected witness signatures do not meet the required threshold."""
    def __init__(self, collected: int, required: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Witness quorum not met: collected {collected} valid signatures, "
            f"threshold requires at least {required}."
        )
        self.collected = collected
        self.required = required
        self.details = details or {}


class ProofOfMisbehavior(WitnessProtocolError):
    """Critical cryptographic exception raised when an active forking / split-view attack is detected.

    Equivocation occurs when an origin or adversary presents two conflicting
    checkpoint commitments (distinct Merkle roots) for the exact same sequence ID.
    """
    def __init__(
        self,
        sequence_id: int,
        root_a: str,
        root_b: str,
        note_a: Optional[CheckpointNote] = None,
        note_b: Optional[CheckpointNote] = None,
    ):
        message = (
            f"CRITICAL CRYPTOGRAPHIC FORK DETECTED at sequence #{sequence_id}: "
            f"Conflicting Merkle roots observed! "
            f"Branch A: {root_a} != Branch B: {root_b}. "
            f"Indisputable Proof-of-Misbehavior logged."
        )
        super().__init__(message)
        self.sequence_id = sequence_id
        self.root_a = root_a
        self.root_b = root_b
        self.note_a = note_a
        self.note_b = note_b


# ---------------------------------------------------------------------------
# Checkpoint Note Format (RFC 9162)
# ---------------------------------------------------------------------------

@dataclass
class CheckpointNote:
    """Canonical body for Argus's local reference checkpoint note."""
    sequence_id: int
    merkle_root: str
    origin: str = DEFAULT_NOTE_ORIGIN
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    checkpoint_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def serialize_body(self) -> str:
        """Produce the canonical, whitespace-sensitive Argus note body text.

        Format:
          <origin>\n
          <sequence_id>\n
          <merkle_root>\n
          <timestamp>\n
          <metadata_canonical_json>\n
        """
        meta_str = (
            json.dumps(self.metadata, sort_keys=True, separators=(",", ":"))
            if self.metadata
            else "{}"
        )
        lines = [
            self.origin.strip(),
            str(self.sequence_id),
            self.merkle_root.strip(),
            self.timestamp.strip(),
            meta_str,
        ]
        return "\n".join(lines) + "\n"

    def body_bytes(self) -> bytes:
        """Return UTF-8 encoded canonical bytes for cryptographic signing."""
        return self.serialize_body().encode("utf-8")

    @classmethod
    def from_body_text(cls, text_content: str) -> CheckpointNote:
        """Parse an Argus reference note body."""
        lines = [line.strip() for line in text_content.strip().splitlines() if line.strip()]
        if len(lines) < 3:
            raise ValueError(f"Malformed RFC 9162 note body (expected at least 3 lines, got {len(lines)}).")

        origin = lines[0]
        seq_id = int(lines[1])
        merkle_root = lines[2]
        timestamp = lines[3] if len(lines) > 3 else datetime.now(timezone.utc).isoformat()
        metadata = {}
        if len(lines) > 4:
            try:
                metadata = json.loads(lines[4])
            except Exception:
                metadata = {"raw": lines[4]}

        cp_hash = metadata.get("checkpoint_hash")
        return cls(
            origin=origin,
            sequence_id=seq_id,
            merkle_root=merkle_root,
            timestamp=timestamp,
            checkpoint_hash=cp_hash,
            metadata=metadata,
        )

    def detect_fork(self, other: Union[CheckpointNote, Any]) -> None:
        """Assert consistency with another observed checkpoint note for the same sequence.

        Raises:
            ProofOfMisbehavior: If sequence_id matches but merkle_root diverges.
        """
        other_note = other.note if hasattr(other, "note") else other
        if self.sequence_id == other_note.sequence_id:
            if self.merkle_root != other_note.merkle_root:
                raise ProofOfMisbehavior(
                    sequence_id=self.sequence_id,
                    root_a=self.merkle_root,
                    root_b=other_note.merkle_root,
                    note_a=self,
                    note_b=other_note,
                )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



# ---------------------------------------------------------------------------
# Witness Signature
# ---------------------------------------------------------------------------

@dataclass
class WitnessSignature:
    """A cryptographic signature over an Argus reference note."""
    witness_name: str
    signature_bytes: bytes
    public_key_pem: Optional[str] = None
    key_id: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def signature_b64(self) -> str:
        """Standard base64 encoded signature string."""
        return base64.b64encode(self.signature_bytes).decode("ascii")

    def signature_hex(self) -> str:
        """Hexadecimal encoded signature string."""
        return self.signature_bytes.hex()

    def format_line(self) -> str:
        """Cosignature line: '— <verifier_name> <signature_b64>'."""
        return f"— {self.witness_name} {self.signature_b64()}"

    @classmethod
    def from_line(
        cls, line: str, public_key_pem: Optional[str] = None
    ) -> WitnessSignature:
        """Parse an RFC 9162 signature line prefixed with '— ' or '-- '."""
        cleaned = re.sub(r"^[—\-]{1,2}\s*", "", line.strip())
        parts = cleaned.split(" ", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid witness signature line format: '{line}'")

        witness_name, sig_b64 = parts[0].strip(), parts[1].strip()
        sig_bytes = base64.b64decode(sig_b64)
        return cls(
            witness_name=witness_name,
            signature_bytes=sig_bytes,
            public_key_pem=public_key_pem,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "witness_name": self.witness_name,
            "signature_hex": self.signature_hex(),
            "signature_b64": self.signature_b64(),
            "key_id": self.key_id,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Witnessed Checkpoint
# ---------------------------------------------------------------------------

@dataclass
class WitnessedCheckpoint:
    """Complete multi-witness cosigned checkpoint envelope."""
    note: CheckpointNote
    origin_signature: WitnessSignature
    witness_signatures: List[WitnessSignature] = field(default_factory=list)

    def add_witness_signature(self, sig: WitnessSignature) -> None:
        """Add a witness signature, preventing duplicate witness identities."""
        for existing in self.witness_signatures:
            if existing.witness_name == sig.witness_name:
                # Update existing signature
                existing.signature_bytes = sig.signature_bytes
                existing.public_key_pem = sig.public_key_pem or existing.public_key_pem
                return
        self.witness_signatures.append(sig)

    def quorum_satisfied(self, threshold: int = 2) -> bool:
        """Check whether the number of distinct valid witness cosignatures meets threshold M."""
        distinct_witnesses = {w.witness_name for w in self.witness_signatures}
        return len(distinct_witnesses) >= threshold

    def detect_fork(self, other: Union[WitnessedCheckpoint, CheckpointNote]) -> None:
        """Assert consistency with another observed checkpoint note for the same sequence.

        Raises:
            ProofOfMisbehavior: If sequence_id matches but merkle_root diverges.
        """
        other_note = other.note if isinstance(other, WitnessedCheckpoint) else other
        if self.note.sequence_id == other_note.sequence_id:
            if self.note.merkle_root != other_note.merkle_root:
                raise ProofOfMisbehavior(
                    sequence_id=self.note.sequence_id,
                    root_a=self.note.merkle_root,
                    root_b=other_note.merkle_root,
                    note_a=self.note,
                    note_b=other_note,
                )

    def serialize(self) -> str:
        """Serialize the Argus reference note with all cosignatures."""
        lines = [self.note.serialize_body().rstrip("\n"), ""]
        lines.append(self.origin_signature.format_line())
        for w in self.witness_signatures:
            lines.append(w.format_line())
        return "\n".join(lines) + "\n"

    @classmethod
    def from_text(cls, text_content: str) -> WitnessedCheckpoint:
        """Parse an Argus reference multi-signature checkpoint note."""
        parts = text_content.strip().split("\n\n", 1)
        if len(parts) == 1:
            # Fallback if single newline separation
            body_lines = []
            sig_lines = []
            for line in text_content.splitlines():
                if line.strip().startswith(("—", "--")):
                    sig_lines.append(line.strip())
                elif not sig_lines and line.strip():
                    body_lines.append(line)
            body_text = "\n".join(body_lines) + "\n"
        else:
            body_text = parts[0] + "\n"
            sig_lines = [l.strip() for l in parts[1].splitlines() if l.strip()]

        note = CheckpointNote.from_body_text(body_text)

        if not sig_lines:
            raise ValueError("No signatures found in RFC 9162 checkpoint note.")

        origin_sig = WitnessSignature.from_line(sig_lines[0])
        witnesses: List[WitnessSignature] = []
        for line in sig_lines[1:]:
            witnesses.append(WitnessSignature.from_line(line))

        return cls(
            note=note,
            origin_signature=origin_sig,
            witness_signatures=witnesses,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note": self.note.to_dict(),
            "origin_signature": self.origin_signature.to_dict(),
            "witness_signatures": [w.to_dict() for w in self.witness_signatures],
            "witness_count": len(self.witness_signatures),
            "quorum_satisfied_m2": self.quorum_satisfied(threshold=2),
            "quorum_satisfied_m3": self.quorum_satisfied(threshold=3),
        }


# ---------------------------------------------------------------------------
# Verification Utilities
# ---------------------------------------------------------------------------

def verify_witness_quorum(
    witnessed: WitnessedCheckpoint,
    public_keys: Dict[str, str],
    threshold: int = 2,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Cryptographically verify origin and witness signatures against trusted public keys.

    Args:
        witnessed: The WitnessedCheckpoint envelope to verify.
        public_keys: Dictionary mapping witness_name to public key PEM string.
        threshold: Minimum required valid witness signatures (default: 2).

    Returns:
        (is_valid, message, report_dict)
    """
    from cryptography.hazmat.primitives.serialization import load_pem_public_key, Encoding, PublicFormat
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from db.cli.verify_capsule import verify_signature

    def key_identity(pem: str) -> bytes | None:
        try:
            key = load_pem_public_key(pem.encode("utf-8"))
            if isinstance(key, Ed25519PublicKey):
                return key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        except (TypeError, ValueError):
            pass
        return None

    body_bytes = witnessed.note.body_bytes()

    report: Dict[str, Any] = {
        "sequence_id": witnessed.note.sequence_id,
        "merkle_root": witnessed.note.merkle_root,
        "origin_valid": False,
        "required_threshold": threshold,
        "valid_witness_count": 0,
        "per_witness_status": {},
    }

    # 1. Verify Origin Signature
    origin_name = witnessed.origin_signature.witness_name
    origin_pem = public_keys.get(origin_name)
    if not origin_pem:
        return False, f"Missing trusted public key for origin '{origin_name}'", report

    origin_identity = key_identity(origin_pem)
    if origin_identity is None:
        return False, f"Invalid trusted public key for origin '{origin_name}'", report
    embedded_origin = witnessed.origin_signature.public_key_pem
    if embedded_origin and key_identity(embedded_origin) != origin_identity:
        return False, "Origin note key differs from the trusted public key.", report

    origin_ok = verify_signature(
        origin_pem, body_bytes, witnessed.origin_signature.signature_bytes
    )
    report["origin_valid"] = origin_ok
    if not origin_ok:
        return False, "Origin signature verification failed on checkpoint note.", report

    # 2. Verify Witness Cosignatures
    valid_count = 0
    observed: set[str] = set()
    counted_keys: set[bytes] = {origin_identity}

    for w in witnessed.witness_signatures:
        w_name = w.witness_name
        if w_name in observed:
            continue
        observed.add(w_name)

        w_pem = public_keys.get(w_name)
        if not w_pem:
            report["per_witness_status"][w_name] = {
                "valid": False,
                "reason": "Missing public key",
            }
            continue

        identity = key_identity(w_pem)
        if identity is None:
            report["per_witness_status"][w_name] = {
                "valid": False,
                "reason": "Invalid trusted public key",
            }
            continue
        if w.public_key_pem and key_identity(w.public_key_pem) != identity:
            report["per_witness_status"][w_name] = {
                "valid": False,
                "reason": "Embedded key differs from trusted public key",
            }
            continue
        if identity in counted_keys:
            report["per_witness_status"][w_name] = {
                "valid": False,
                "reason": "Duplicate trusted public key",
            }
            continue

        w_ok = verify_signature(w_pem, body_bytes, w.signature_bytes)
        report["per_witness_status"][w_name] = {
            "valid": w_ok,
            "reason": "Signature verified" if w_ok else "Invalid signature",
        }
        if w_ok:
            valid_count += 1
            counted_keys.add(identity)

    report["valid_witness_count"] = valid_count
    report["quorum_met"] = valid_count >= threshold

    if valid_count < threshold:
        return (
            False,
            f"Witness quorum not met: {valid_count} of {threshold} required signatures verified.",
            report,
        )

    return (
        True,
        f"Witness quorum satisfied: {valid_count} valid witness signatures (threshold: {threshold}).",
        report,
    )
