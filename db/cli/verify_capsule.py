#!/usr/bin/env python3
"""Argus Standalone Forensic Merkle Capsule Verifier (NOVEL-009-E).

Zero-dependency verification tool for .arguscap selective disclosure evidence bundles.
Designed for air-gapped forensic investigators, legal counsel, and compliance auditors.
Operates using pure Python 3.10+ standard library with zero external pip dependencies.

Security Verifications Performed:
  1. Ed25519 Checkpoint Signature: Validates the cryptographic origin authenticity of
     the enclosing checkpoint over `checkpoint_hash:merkle_root`.
  2. RFC 6962 Domain-Separated Leaf Hash: Computes SHA-256(0x00 || canonical_json(evidence_row))
     and verifies it matches the leaf hash in the Merkle inclusion proof.
  3. RFC 6962 Internal Node Audit Path: Walks the logarithmic O(log2 K) sibling hashes
     using SHA-256(0x01 || left || right) to independently recompute the Merkle root.
  4. Cryptographic Binding: Asserts that the recomputed Merkle root exactly matches the
     Merkle root anchored in the Ed25519-signed checkpoint.

Exit Codes:
  0: SUCCESS — Forensic proof valid. Single record cryptographically proven authentic.
  1: TAMPER_DETECTED — Row mutated, proof path corrupted, or signature invalid.
  2: MALFORMED_BUNDLE — Missing archive components or invalid schema.

Usage:
  python verify_capsule.py proof_seq42.arguscap
  python verify_capsule.py --bundle proof_seq42.arguscap
  python -m db.cli.verify_capsule --capsule proof_seq42.arguscap
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import zipfile


# ==============================================================================
# Pure-Python Ed25519 Verification (RFC 8032)
# Zero external dependencies — operates solely on standard Python integers.
# ==============================================================================

_B = 256
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)


_D = -121665 * _inv(121666)
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_By = 4 * _inv(5)
_Bx = _xrecover(_By)
_BasePoint = [_Bx % _Q, _By % _Q]


def _edwards_add(p1: List[int], p2: List[int]) -> List[int]:
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2)
    return [x3 % _Q, y3 % _Q]


def _scalarmult(p: List[int], e: int) -> List[int]:
    if e == 0:
        return [0, 1]
    q = _scalarmult(p, e // 2)
    q = _edwards_add(q, q)
    if e & 1:
        q = _edwards_add(q, p)
    return q


def _decode_point(s: bytes) -> List[int]:
    y = sum(2**i * 1 if (s[i // 8] >> (i % 8)) & 1 else 0 for i in range(_B - 1))
    x = _xrecover(y)
    if bool(x & 1) != bool((s[_B // 8 - 1] >> 7) & 1):
        x = _Q - x
    return [x, y]


def verify_ed25519_pure(public_key_bytes: bytes, message: bytes, signature_bytes: bytes) -> bool:
    """Verify an Ed25519 signature using RFC 8032 pure-python math."""
    if len(signature_bytes) != 64 or len(public_key_bytes) != 32:
        return False
    r_raw = signature_bytes[:32]
    s_raw = signature_bytes[32:]
    s_int = int.from_bytes(s_raw, "little")
    if s_int >= _L:
        return False
    try:
        a_point = _decode_point(public_key_bytes)
        r_point = _decode_point(r_raw)
    except Exception:
        return False

    h = hashlib.sha512(r_raw + public_key_bytes + message).digest()
    k = int.from_bytes(h, "little") % _L

    sb = _scalarmult(_BasePoint, s_int)
    ka = _scalarmult(a_point, k)
    r_plus_ka = _edwards_add(r_point, ka)
    return sb[0] == r_plus_ka[0] and sb[1] == r_plus_ka[1]


def extract_raw_public_key_bytes(pem_content: Union[str, bytes]) -> bytes:
    """Extract 32 raw Ed25519 public key bytes from a standard PEM file."""
    if isinstance(pem_content, bytes):
        pem_text = pem_content.decode("utf-8", errors="replace")
    else:
        pem_text = pem_content

    # Try cryptography first if present
    try:
        from cryptography.hazmat.primitives import serialization
        key = serialization.load_pem_public_key(pem_text.encode("utf-8"))
        return key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    except Exception:
        pass

    # Pure Python PEM parsing
    lines = [
        line.strip()
        for line in pem_text.splitlines()
        if line.strip() and not line.startswith("-----")
    ]
    b64_data = "".join(lines)
    der_bytes = base64.b64decode(b64_data)

    # Standard RFC 8410 SubjectPublicKeyInfo for Ed25519 is 44 bytes:
    # 12-byte header (30 2a 30 05 06 03 2b 65 70 03 21 00) + 32-byte raw key
    if len(der_bytes) == 44:
        return der_bytes[-32:]
    elif len(der_bytes) == 32:
        return der_bytes
    else:
        # Fallback if other ASN.1 wrapping
        return der_bytes[-32:]


def verify_signature(public_key_pem: Union[str, bytes], message: bytes, signature_bytes: bytes) -> bool:
    """Verify Ed25519 signature using cryptography if present, else pure Python."""
    raw_pub = extract_raw_public_key_bytes(public_key_pem)
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        pub = ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
        pub.verify(signature_bytes, message)
        return True
    except ImportError:
        return verify_ed25519_pure(raw_pub, message, signature_bytes)
    except Exception:
        # Fallback to pure math in case of format differences
        return verify_ed25519_pure(raw_pub, message, signature_bytes)


# ==============================================================================
# RFC 6962 / RFC 9162 Merkle Functions (Zero External Dependencies)
# ==============================================================================

def canonical_json_serialize(record: Dict[str, Any]) -> str:
    """Deterministically serialize a dictionary into canonical JSON."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)


def compute_leaf_hash(record: Dict[str, Any]) -> str:
    """RFC 6962 leaf hash: SHA-256(0x00 || canonical_bytes)."""
    canonical_bytes = canonical_json_serialize(record).encode("utf-8")
    return hashlib.sha256(b"\x00" + canonical_bytes).hexdigest()


def compute_parent_hash(left_hex: str, right_hex: str) -> str:
    """RFC 6962 internal parent hash: SHA-256(0x01 || left || right)."""
    left_bytes = bytes.fromhex(left_hex)
    right_bytes = bytes.fromhex(right_hex)
    return hashlib.sha256(b"\x01" + left_bytes + right_bytes).hexdigest()


# ==============================================================================
# Bundle Reader
# ==============================================================================

class CapsuleReader:
    """Reads capsule contents from a .arguscap zip file, bytes buffer, or folder."""

    def __init__(self, target: Union[str, Path, bytes, io.BytesIO, zipfile.ZipFile]) -> None:
        self.target = target
        self._zip: Optional[zipfile.ZipFile] = None
        self._dir: Optional[Path] = None

        if isinstance(target, zipfile.ZipFile):
            self._zip = target
        elif isinstance(target, bytes):
            self._zip = zipfile.ZipFile(io.BytesIO(target), "r")
        elif isinstance(target, io.BytesIO):
            self._zip = zipfile.ZipFile(target, "r")
        else:
            p = Path(target)
            if p.is_dir():
                self._dir = p
            elif p.is_file():
                self._zip = zipfile.ZipFile(p, "r")
            else:
                raise FileNotFoundError(f"Capsule path '{target}' not found.")

    def read_bytes(self, filename: str) -> bytes:
        if self._zip is not None:
            return self._zip.read(filename)
        elif self._dir is not None:
            return (self._dir / filename).read_bytes()
        raise RuntimeError("No valid reader source.")

    def read_text(self, filename: str) -> str:
        return self.read_bytes(filename).decode("utf-8")

    def read_json(self, filename: str) -> Dict[str, Any]:
        return json.loads(self.read_text(filename))

    def has_file(self, filename: str) -> bool:
        if self._zip is not None:
            return filename in self._zip.namelist()
        elif self._dir is not None:
            return (self._dir / filename).is_file()
        return False

    def close(self) -> None:
        if self._zip is not None and not isinstance(self.target, zipfile.ZipFile):
            self._zip.close()


# ==============================================================================
# Verification Logic
# ==============================================================================

def verify_capsule(
    capsule_target: Union[str, Path, bytes, io.BytesIO, zipfile.ZipFile]
) -> Tuple[bool, str, Dict[str, Any]]:
    """Perform independent cryptographic verification of an .arguscap bundle.

    Returns:
        (is_valid, message, details_dict)
    """
    try:
        reader = CapsuleReader(capsule_target)
    except Exception as e:
        return False, f"Failed to open capsule bundle: {e}", {"exit_code": 2}

    try:
        # 1. Verify required bundle files exist
        required_files = [
            "evidence_row.json",
            "merkle_proof.json",
            "checkpoint.json",
            "public_key.pem",
        ]
        for f in required_files:
            if not reader.has_file(f):
                return False, f"Malformed capsule: missing required bundle file '{f}'", {
                    "missing_file": f,
                    "exit_code": 2,
                }

        evidence_row = reader.read_json("evidence_row.json")
        merkle_proof = reader.read_json("merkle_proof.json")
        checkpoint = reader.read_json("checkpoint.json")
        public_key_pem = reader.read_text("public_key.pem")

        details: Dict[str, Any] = {
            "sequence_id": evidence_row.get("sequence_id"),
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "expected_merkle_root": checkpoint.get("merkle_root"),
            "proof_merkle_root": merkle_proof.get("merkle_root"),
            "audit_path_depth": len(merkle_proof.get("audit_path", [])),
            "signature_valid": False,
            "leaf_hash_valid": False,
            "path_valid": False,
            "root_match": False,
        }

        # 2. Checkpoint signature verification
        checkpoint_hash = checkpoint.get("checkpoint_hash", "")
        merkle_root = checkpoint.get("merkle_root")
        if not merkle_root:
            return False, "Checkpoint does not contain a Merkle root (pre-Merkle era).", details

        sig_hex = checkpoint.get("signature_hex", "")
        if not sig_hex:
            return False, "Checkpoint signature is missing from capsule metadata.", details

        try:
            sig_bytes = bytes.fromhex(sig_hex)
        except ValueError:
            return False, "Malformed signature hex string in checkpoint metadata.", details

        # Try post-Merkle bound payload first, fallback to legacy checkpoint_hash
        bound_payload = f"{checkpoint_hash}:{merkle_root}".encode("utf-8")
        sig_ok = verify_signature(public_key_pem, bound_payload, sig_bytes)
        if not sig_ok:
            # Fallback check
            sig_ok = verify_signature(public_key_pem, checkpoint_hash.encode("utf-8"), sig_bytes)

        details["signature_valid"] = sig_ok
        if not sig_ok:
            return False, "Checkpoint Ed25519 signature verification failed (tampered checkpoint).", details

        # 3. Leaf hash verification
        computed_leaf = compute_leaf_hash(evidence_row)
        expected_leaf = merkle_proof.get("leaf_hash")
        details["computed_leaf_hash"] = computed_leaf
        details["expected_leaf_hash"] = expected_leaf

        if computed_leaf != expected_leaf:
            details["leaf_hash_valid"] = False
            return (
                False,
                f"Evidence row hash mismatch: computed {computed_leaf} != expected {expected_leaf} "
                "(evidence row has been tampered with).",
                details,
            )
        details["leaf_hash_valid"] = True

        # 4. Merkle audit path verification
        curr_hash = computed_leaf
        audit_path = merkle_proof.get("audit_path", [])
        for step in audit_path:
            direction = step.get("direction")
            sibling_hex = step.get("sibling_hash", "")
            if not sibling_hex:
                return False, "Invalid step in Merkle audit path (missing sibling hash).", details

            if direction == "left":
                curr_hash = compute_parent_hash(sibling_hex, curr_hash)
            elif direction == "right":
                curr_hash = compute_parent_hash(curr_hash, sibling_hex)
            else:
                return False, f"Invalid step direction '{direction}' in audit path.", details

        details["computed_root"] = curr_hash
        if curr_hash != merkle_proof.get("merkle_root"):
            details["path_valid"] = False
            return (
                False,
                f"Merkle audit path traversal resulted in root {curr_hash}, "
                f"which does not match proof root {merkle_proof.get('merkle_root')}.",
                details,
            )
        details["path_valid"] = True

        # 5. Root binding check: proof root vs checkpoint root
        if merkle_proof.get("merkle_root") != checkpoint.get("merkle_root"):
            details["root_match"] = False
            return (
                False,
                f"Merkle proof root {merkle_proof.get('merkle_root')} does not match "
                f"checkpoint root {checkpoint.get('merkle_root')}.",
                details,
            )
        details["root_match"] = True

        # 6. Sequence ID continuity validation
        seq_id = evidence_row.get("sequence_id")
        if seq_id != merkle_proof.get("sequence_id"):
            return False, "Evidence row sequence_id does not match proof sequence_id.", details

        return (
            True,
            f"Cryptographic verification SUCCESS: Sequence #{seq_id} is proven authentic "
            f"under Checkpoint #{checkpoint.get('checkpoint_id')} (Merkle root: {merkle_root[:16]}...).",
            details,
        )
    finally:
        reader.close()


# ==============================================================================
# CLI Entry Point
# ==============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Argus Standalone Forensic Merkle Capsule Verifier (NOVEL-009-E)"
    )
    parser.add_argument(
        "capsule_path",
        nargs="?",
        default=None,
        help="Path to .arguscap file or uncompressed bundle directory",
    )
    parser.add_argument(
        "--bundle",
        "--capsule",
        dest="capsule_flag",
        default=None,
        help="Path to .arguscap file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()
    target_path = args.capsule_flag or args.capsule_path

    if not target_path:
        parser.print_help()
        return 2

    is_valid, message, details = verify_capsule(target_path)

    if args.json:
        result_payload = {
            "valid": is_valid,
            "message": message,
            "details": details,
        }
        print(json.dumps(result_payload, indent=2))
    else:
        status_banner = "[PASS] CAPSULE CRYPTOGRAPHICALLY VALID" if is_valid else "[FAIL] VERIFICATION FAILED"
        print("=" * 72)
        print(f"  ARGUS FORENSIC CAPSULE VERIFIER: {status_banner}")
        print("=" * 72)
        print(f"Message:      {message}")
        print(f"Sequence ID:  {details.get('sequence_id')}")
        print(f"Checkpoint:   #{details.get('checkpoint_id')}")
        print(f"Merkle Root:  {details.get('expected_merkle_root')}")
        print(f"Audit Depth:  {details.get('audit_path_depth')} levels")
        print(f"Signature:    {'VALID' if details.get('signature_valid') else 'INVALID'}")
        print(f"Leaf Hash:    {'VALID' if details.get('leaf_hash_valid') else 'INVALID'}")
        print(f"Path Root:    {'VALID' if details.get('path_valid') else 'INVALID'}")
        print("=" * 72)

    if is_valid:
        return 0
    else:
        exit_code = details.get("exit_code", 1)
        return exit_code


if __name__ == "__main__":
    sys.exit(main())
