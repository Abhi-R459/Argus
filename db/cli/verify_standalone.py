#!/usr/bin/env python3
"""Argus Standalone Evidence Verifier (PACK-001).

Zero-dependency verification tool for .arguspack portable evidence archives.
Designed for air-gapped compliance auditors and independent third parties.
Requires only standard Python 3.10+ (no pip packages required).

Exit Codes:
    0: SUCCESS — Hash chain unbroken, sequence continuous, signature valid.
    1: HASH_BREAK / SEQUENCE_GAP — Tampered payload, modified hash, or gap.
    2: SIGNATURE_INVALID — Ed25519 signature verification failure.
    3: MALFORMED_BUNDLE — Missing manifest, missing files, or corrupted format.

Usage:
    python verify_standalone.py <path_to_bundle_directory_or_zip>
    python -m db.cli.verify_standalone <path_to_bundle>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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


def verify_signature_standalone(public_key_bytes: bytes, message: bytes, signature_bytes: bytes) -> bool:
    """Attempt fast verification via cryptography if available, else pure Python."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519

        pub = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        pub.verify(signature_bytes, message)
        return True
    except ImportError:
        return verify_ed25519_pure(public_key_bytes, message, signature_bytes)
    except Exception:
        return False


# ==============================================================================
# Bundle Reader (Directory or Zip)
# ==============================================================================

class BundleReader:
    """Reads evidence bundle contents transparently from directory or zip archive."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.is_zip = self.path.is_file() and (
            self.path.suffix.lower() in [".zip", ".arguspack"] or zipfile.is_zipfile(self.path)
        )
        self._zip: Optional[zipfile.ZipFile] = None

    def __enter__(self) -> "BundleReader":
        if self.is_zip:
            self._zip = zipfile.ZipFile(self.path, "r")
        elif not self.path.is_dir():
            raise FileNotFoundError(f"Bundle path '{self.path}' is neither a directory nor a zip archive.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._zip:
            self._zip.close()

    def has_file(self, filename: str) -> bool:
        if self.is_zip:
            assert self._zip is not None
            return filename in self._zip.namelist()
        return (self.path / filename).is_file()

    def read_bytes(self, filename: str) -> bytes:
        if self.is_zip:
            assert self._zip is not None
            with self._zip.open(filename) as f:
                return f.read()
        with open(self.path / filename, "rb") as f:
            return f.read()

    def read_text(self, filename: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(filename).decode(encoding)


# ==============================================================================
# Canonical Hash Recomputation
# ==============================================================================

def recompute_event_hash(row: Dict[str, Any], prev_hash: str) -> str:
    """Recompute SHA-256 hash according to SETUP-002 serialization contract.

    Contract:
      sequence_id | actor_user_id | action | table_name | row_id |
      old_value_str | new_value_str | created_at_str
    Concatenated with prev_hash and hashed with SHA-256.
    """
    seq_str = str(row.get("sequence_id", ""))
    actor_str = str(row.get("actor_user_id", 0))
    action_str = str(row.get("action", ""))
    table_str = str(row.get("table_name", ""))
    row_id_str = str(row.get("row_id", row.get("employee_id", "")))

    old_val = row.get("old_value_text")
    if old_val is None:
        if "old_value" in row and row["old_value"] is not None:
            old_val = json.dumps(row["old_value"], sort_keys=True, separators=(",", ":"))
        else:
            old_val = "null"

    new_val = row.get("new_value_text")
    if new_val is None:
        if "new_value" in row and row["new_value"] is not None:
            new_val = json.dumps(row["new_value"], sort_keys=True, separators=(",", ":"))
        else:
            new_val = "null"

    created_at_str = str(row.get("created_at_text") or row.get("created_at") or "")

    serialized = (
        f"{seq_str}|{actor_str}|{action_str}|{table_str}|{row_id_str}|"
        f"{old_val}|{new_val}|{created_at_str}"
    )

    return hashlib.sha256((serialized + prev_hash).encode("utf-8")).hexdigest()


# ==============================================================================
# Verification Logic
# ==============================================================================

def verify_bundle(bundle_path: Path | str) -> Tuple[int, Dict[str, Any]]:
    """Verify an .arguspack bundle and return (exit_code, report_dict).

    Exit codes:
        0: SUCCESS
        1: HASH_BREAK / SEQUENCE_GAP
        2: SIGNATURE_INVALID
        3: MALFORMED_BUNDLE
    """
    report: Dict[str, Any] = {
        "status": "UNKNOWN",
        "total_events": 0,
        "mismatches": [],
        "gaps": [],
        "orphans": [],
        "signature_valid": False,
        "errors": [],
    }

    # Step 1: Open bundle and check mandatory files
    try:
        reader = BundleReader(bundle_path)
    except FileNotFoundError as exc:
        report["status"] = "MALFORMED_BUNDLE"
        report["errors"].append(str(exc))
        return 3, report

    with reader:
        mandatory_files = ["manifest.json", "events.jsonl", "signature.sig"]
        missing = [f for f in mandatory_files if not reader.has_file(f)]
        if missing:
            report["status"] = "MALFORMED_BUNDLE"
            report["errors"].append(f"Missing mandatory bundle file(s): {', '.join(missing)}")
            return 3, report

        # Step 2: Parse manifest
        try:
            manifest_data = json.loads(reader.read_text("manifest.json"))
            report["manifest"] = manifest_data
        except Exception as exc:
            report["status"] = "MALFORMED_BUNDLE"
            report["errors"].append(f"Failed to parse manifest.json: {exc}")
            return 3, report

        # Extract public key from manifest
        pub_key_hex = manifest_data.get("public_key_hex")
        if not pub_key_hex and "public_key" in manifest_data:
            pub_key_hex = manifest_data["public_key"]

        if not pub_key_hex or not isinstance(pub_key_hex, str):
            report["status"] = "MALFORMED_BUNDLE"
            report["errors"].append("manifest.json missing 'public_key_hex' field")
            return 3, report

        try:
            pub_key_bytes = bytes.fromhex(pub_key_hex)
            if len(pub_key_bytes) != 32:
                raise ValueError("Public key must be 32 bytes (64 hex characters)")
        except Exception as exc:
            report["status"] = "MALFORMED_BUNDLE"
            report["errors"].append(f"Invalid public key hex: {exc}")
            return 3, report

        # Step 3: Read and check events.jsonl
        events_bytes = reader.read_bytes("events.jsonl")
        events_sha256 = hashlib.sha256(events_bytes).hexdigest()

        # Step 4: Verify detached signature
        sig_raw = reader.read_bytes("signature.sig")
        if len(sig_raw) == 64:
            sig_bytes = sig_raw
        elif len(sig_raw) == 128:
            try:
                sig_bytes = bytes.fromhex(sig_raw.decode("ascii"))
            except Exception:
                sig_bytes = sig_raw
        else:
            try:
                text_content = sig_raw.decode("utf-8").strip()
                sig_bytes = bytes.fromhex(text_content)
            except Exception:
                sig_bytes = sig_raw

        if len(sig_bytes) != 64:
            report["status"] = "SIGNATURE_INVALID"
            report["errors"].append(f"signature.sig must be 64 bytes (found {len(sig_bytes)} bytes)")
            return 2, report

        # Validate signature over events_sha256 string bytes (standard across Argus)
        # Also fall back to raw events_bytes if applicable
        sig_ok = verify_signature_standalone(pub_key_bytes, events_sha256.encode("utf-8"), sig_bytes)
        if not sig_ok:
            sig_ok = verify_signature_standalone(pub_key_bytes, events_bytes, sig_bytes)

        report["signature_valid"] = sig_ok
        if not sig_ok:
            report["status"] = "SIGNATURE_INVALID"
            report["errors"].append("Ed25519 signature verification failed")
            return 2, report

        # Verify events_sha256 against manifest declaration if present
        declared_events_sha256 = manifest_data.get("events_sha256")
        if declared_events_sha256 and declared_events_sha256 != events_sha256:
            report["status"] = "SIGNATURE_INVALID"
            report["errors"].append(
                f"events.jsonl hash mismatch: declared {declared_events_sha256}, computed {events_sha256}"
            )
            return 2, report

        # Step 5: Verify Hash Chain and Sequence Continuity in events.jsonl
        lines = [line.strip() for line in reader.read_text("events.jsonl").splitlines() if line.strip()]
        report["total_events"] = len(lines)

        current_hash = "0" * 64
        expected_seq = 1

        for line_idx, line in enumerate(lines, start=1):
            try:
                row = json.loads(line)
            except Exception as exc:
                report["status"] = "MALFORMED_BUNDLE"
                report["errors"].append(f"JSON syntax error on line {line_idx}: {exc}")
                return 3, report

            seq = row.get("sequence_id")
            if seq is None:
                report["status"] = "MALFORMED_BUNDLE"
                report["errors"].append(f"Line {line_idx} missing 'sequence_id'")
                return 3, report

            # Check sequence continuity
            if line_idx == 1 and seq != 1:
                # If first row doesn't start at 1, bootstrap sequence
                expected_seq = seq

            if seq != expected_seq:
                report["gaps"].append({
                    "line": line_idx,
                    "expected_seq": expected_seq,
                    "actual_seq": seq,
                })

            # Check previous_hash chain continuity
            prev_hash_in_row = row.get("previous_hash", "")
            if line_idx == 1:
                # First row: if not 0*64, bootstrap from row's previous_hash
                if current_hash == "0" * 64 and prev_hash_in_row != current_hash:
                    current_hash = prev_hash_in_row

            if prev_hash_in_row != current_hash:
                report["orphans"].append({
                    "line": line_idx,
                    "sequence_id": seq,
                    "expected_prev": current_hash,
                    "actual_prev": prev_hash_in_row,
                })

            # Recompute entry hash
            recomputed = recompute_event_hash(row, prev_hash_in_row)
            entry_hash_in_row = row.get("entry_hash", "")
            if recomputed != entry_hash_in_row:
                report["mismatches"].append({
                    "line": line_idx,
                    "sequence_id": seq,
                    "expected_hash": entry_hash_in_row,
                    "recomputed_hash": recomputed,
                })

            current_hash = recomputed
            expected_seq = seq + 1

        # Check tail hash against manifest if specified
        declared_tail = manifest_data.get("tail_hash")
        if declared_tail and len(lines) > 0 and declared_tail != current_hash:
            report["mismatches"].append({
                "line": len(lines),
                "sequence_id": "tail",
                "expected_hash": declared_tail,
                "recomputed_hash": current_hash,
            })

        # Step 6: Determine overall outcome
        has_anomalies = (
            len(report["mismatches"]) > 0 or len(report["gaps"]) > 0 or len(report["orphans"]) > 0
        )

        if has_anomalies:
            report["status"] = "HASH_BREAK" if report["mismatches"] else "SEQUENCE_GAP"
            return 1, report

        report["status"] = "SUCCESS"
        report["last_verified_sequence_id"] = expected_seq - 1
        report["tail_hash"] = current_hash
        return 0, report


# ==============================================================================
# CLI Entry Point
# ==============================================================================

def main() -> None:
    # Ensure stdout handles UTF-8 on Windows
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="verify_standalone",
        description="Argus Standalone Evidence Verifier (Zero pip dependencies).",
    )
    parser.add_argument(
        "bundle_path",
        help="Path to an unpacked .arguspack directory or a .zip / .arguspack file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full verification report as JSON to stdout.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Display detailed verification progress.",
    )

    args = parser.parse_args()

    exit_code, report = verify_bundle(args.bundle_path)

    if args.json:
        print(json.dumps(report, indent=2))
        sys.exit(exit_code)

    # Standard human-readable terminal report
    sig_status = "[VALID]" if report.get("signature_valid") else "[INVALID]"
    print("\n" + "=" * 65)
    print("ARGUS STANDALONE EVIDENCE VERIFIER (.arguspack)")
    print("=" * 65)
    print(f"Target Bundle      : {args.bundle_path}")
    print(f"Total Events       : {report.get('total_events', 0)}")
    print(f"Signature Valid    : {sig_status}")
    print(f"Hash Mismatches    : {len(report.get('mismatches', []))}")
    print(f"Sequence Gaps      : {len(report.get('gaps', []))}")
    print(f"Orphan Breaks      : {len(report.get('orphans', []))}")

    status_str = "[PASS] INTEGRITY VERIFIED (SUCCESS)" if exit_code == 0 else f"[FAIL] VERIFICATION FAILED ({report['status']})"
    print(f"Overall Status     : {status_str}")
    print("=" * 65)

    if report.get("errors"):
        print("\nERRORS:")
        for err in report["errors"]:
            print(f"  - {err}")

    if report.get("mismatches"):
        print("\nHASH BREAKS / PAYLOAD TAMPERING:")
        for m in report["mismatches"]:
            print(
                f"  - Line {m.get('line')}, seq={m.get('sequence_id')}: "
                f"expected={m.get('expected_hash', '')[:16]}... recomputed={m.get('recomputed_hash', '')[:16]}..."
            )

    if report.get("gaps"):
        print("\nSEQUENCE GAPS (DELETED ROWS):")
        for g in report["gaps"]:
            print(f"  - Line {g.get('line')}: expected seq={g.get('expected_seq')}, found seq={g.get('actual_seq')}")

    if report.get("orphans"):
        print("\nORPHANED CHAIN BREAKS:")
        for o in report["orphans"]:
            print(
                f"  - Line {o.get('line')}, seq={o.get('sequence_id')}: "
                f"expected_prev={o.get('expected_prev', '')[:16]}... actual_prev={o.get('actual_prev', '')[:16]}..."
            )

    print()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
