"""Intermediate Test Gate 4: Standalone Evidence Verifier (PACK-001).

Validates the 5-scenario tamper matrix and air-gapped standalone verification:
1. Clean bundle -> Exit Code 0 (SUCCESS).
2. Modified event payload in events.jsonl -> Exit Code 1 (HASH_BREAK) with exact line number.
3. Truncated or deleted event -> Exit Code 1 (SEQUENCE_GAP).
4. Modified Ed25519 signature in signature.sig -> Exit Code 2 (SIGNATURE_INVALID).
5. Missing mandatory file in bundle -> Exit Code 3 (MALFORMED_BUNDLE).
6. Direct .zip / .arguspack file verification.
7. Subprocess CLI invocation asserting exit codes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import pytest

from db.cli.verify_standalone import (
    verify_bundle,
    recompute_event_hash,
    verify_ed25519_pure,
    verify_signature_standalone,
)
from db.cli.keygen import generate_keypair, save_keypair, load_private_key, load_public_key
from db.cli.signer import sign_checkpoint
from cryptography.hazmat.primitives import serialization


@pytest.fixture
def keypair(tmp_path):
    """Generate and return private key, public key, and raw 32-byte public key bytes."""
    priv_bytes, pub_bytes = generate_keypair()
    priv_path, pub_path = save_keypair(priv_bytes, pub_bytes, str(tmp_path))
    priv_key = load_private_key(priv_path)
    pub_key = load_public_key(pub_path)
    raw_pub_bytes = pub_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return priv_key, pub_key, raw_pub_bytes


def build_synthetic_bundle(target_dir: Path, priv_key, raw_pub_bytes, num_events: int = 10) -> dict:
    """Helper to build a valid, canonical synthetic .arguspack bundle directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    prev_hash = "0" * 64
    rows = []
    lines = []

    now_str = "2026-09-12T10:00:00+00:00"

    for seq in range(1, num_events + 1):
        row = {
            "sequence_id": seq,
            "actor_user_id": 1,
            "employee_id": 100 + seq,
            "action": "INSERT" if seq == 1 else "UPDATE",
            "table_name": "employees",
            "row_id": 100 + seq,
            "old_value_text": None if seq == 1 else json.dumps({"status": "PROBATION"}),
            "new_value_text": json.dumps({"status": "ACTIVE", "seq": seq}),
            "severity": "INFO",
            "previous_hash": prev_hash,
            "created_at_text": now_str,
        }
        entry_hash = recompute_event_hash(row, prev_hash)
        row["entry_hash"] = entry_hash
        rows.append(row)
        lines.append(json.dumps(row))
        prev_hash = entry_hash

    events_content = "\n".join(lines) + "\n"
    events_bytes = events_content.encode("utf-8")
    (target_dir / "events.jsonl").write_bytes(events_bytes)

    events_sha256 = hashlib.sha256(events_bytes).hexdigest()
    sig_bytes = sign_checkpoint(priv_key, events_sha256)
    (target_dir / "signature.sig").write_bytes(sig_bytes)

    manifest = {
        "bundle_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "hash_algorithm": "SHA-256",
        "signature_algorithm": "Ed25519",
        "public_key_hex": raw_pub_bytes.hex(),
        "total_events": num_events,
        "tail_hash": prev_hash,
        "events_sha256": events_sha256,
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    checkpoints = [
        {
            "sequence_id": num_events,
            "checkpoint_hash": hashlib.sha256("test-checkpoint".encode("utf-8")).hexdigest(),
        }
    ]
    (target_dir / "checkpoints.json").write_text(json.dumps(checkpoints, indent=2), encoding="utf-8")

    return {
        "manifest": manifest,
        "events": rows,
        "tail_hash": prev_hash,
        "events_sha256": events_sha256,
    }


class TestVerifyStandalone:
    """Tamper Matrix Test Suite for Standalone Verifier (PACK-001)."""

    def test_clean_bundle_passes(self, tmp_path, keypair):
        """Case 1: Untampered bundle returns exit code 0 (SUCCESS)."""
        priv_key, _, raw_pub_bytes = keypair
        bundle_dir = tmp_path / "bundle_clean"
        build_synthetic_bundle(bundle_dir, priv_key, raw_pub_bytes, num_events=5)

        exit_code, report = verify_bundle(bundle_dir)
        assert exit_code == 0
        assert report["status"] == "SUCCESS"
        assert report["signature_valid"] is True
        assert len(report["mismatches"]) == 0
        assert len(report["gaps"]) == 0
        assert len(report["orphans"]) == 0
        assert report["total_events"] == 5

    def test_modified_event_payload_fails(self, tmp_path, keypair):
        """Case 2: Modified event payload in events.jsonl returns exit code 1 (HASH_BREAK) with exact line."""
        priv_key, _, raw_pub_bytes = keypair
        bundle_dir = tmp_path / "bundle_tampered_event"
        meta = build_synthetic_bundle(bundle_dir, priv_key, raw_pub_bytes, num_events=5)

        # Tamper with line 3 in events.jsonl
        lines = (bundle_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        tampered_row = json.loads(lines[2])
        tampered_row["new_value_text"] = json.dumps({"status": "COMPROMISED", "seq": 3})
        lines[2] = json.dumps(tampered_row)
        tampered_events_bytes = ("\n".join(lines) + "\n").encode("utf-8")
        (bundle_dir / "events.jsonl").write_bytes(tampered_events_bytes)

        # Re-sign the tampered events file to isolate hash-chain tamper detection from signature failure
        new_events_sha256 = hashlib.sha256(tampered_events_bytes).hexdigest()
        (bundle_dir / "signature.sig").write_bytes(sign_checkpoint(priv_key, new_events_sha256))
        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["events_sha256"] = new_events_sha256
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        exit_code, report = verify_bundle(bundle_dir)
        assert exit_code == 1
        assert report["status"] == "HASH_BREAK"
        assert report["signature_valid"] is True
        assert len(report["mismatches"]) >= 1
        # Asserts line 3 is flagged
        assert any(m["line"] == 3 for m in report["mismatches"])

    def test_sequence_gap_detected(self, tmp_path, keypair):
        """Case 3: Deleted event produces a sequence gap and returns exit code 1 (SEQUENCE_GAP)."""
        priv_key, _, raw_pub_bytes = keypair
        bundle_dir = tmp_path / "bundle_sequence_gap"
        build_synthetic_bundle(bundle_dir, priv_key, raw_pub_bytes, num_events=6)

        # Delete line 4 (seq=4)
        lines = (bundle_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        del lines[3]  # delete seq 4
        new_events_bytes = ("\n".join(lines) + "\n").encode("utf-8")
        (bundle_dir / "events.jsonl").write_bytes(new_events_bytes)

        # Re-sign so signature passes and gap is specifically flagged
        new_events_sha256 = hashlib.sha256(new_events_bytes).hexdigest()
        (bundle_dir / "signature.sig").write_bytes(sign_checkpoint(priv_key, new_events_sha256))
        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["events_sha256"] = new_events_sha256
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        exit_code, report = verify_bundle(bundle_dir)
        assert exit_code == 1
        assert len(report["gaps"]) >= 1
        gap = report["gaps"][0]
        assert gap["expected_seq"] == 4
        assert gap["actual_seq"] == 5

    def test_invalid_signature_fails(self, tmp_path, keypair):
        """Case 4: Corrupted or forged signature returns exit code 2 (SIGNATURE_INVALID)."""
        priv_key, _, raw_pub_bytes = keypair
        bundle_dir = tmp_path / "bundle_bad_sig"
        build_synthetic_bundle(bundle_dir, priv_key, raw_pub_bytes, num_events=5)

        # Corrupt signature bytes
        sig = (bundle_dir / "signature.sig").read_bytes()
        corrupted = bytearray(sig)
        corrupted[0] ^= 0xFF
        (bundle_dir / "signature.sig").write_bytes(bytes(corrupted))

        exit_code, report = verify_bundle(bundle_dir)
        assert exit_code == 2
        assert report["status"] == "SIGNATURE_INVALID"
        assert report["signature_valid"] is False

    def test_missing_mandatory_file_fails(self, tmp_path, keypair):
        """Case 5: Missing manifest or events file returns exit code 3 (MALFORMED_BUNDLE)."""
        priv_key, _, raw_pub_bytes = keypair
        bundle_dir = tmp_path / "bundle_missing_file"
        build_synthetic_bundle(bundle_dir, priv_key, raw_pub_bytes, num_events=3)

        # Delete manifest.json
        (bundle_dir / "manifest.json").unlink()

        exit_code, report = verify_bundle(bundle_dir)
        assert exit_code == 3
        assert report["status"] == "MALFORMED_BUNDLE"
        assert any("manifest.json" in err for err in report["errors"])

    def test_zip_bundle_verification(self, tmp_path, keypair):
        """Direct .zip / .arguspack archive verification."""
        priv_key, _, raw_pub_bytes = keypair
        bundle_dir = tmp_path / "bundle_dir_for_zip"
        build_synthetic_bundle(bundle_dir, priv_key, raw_pub_bytes, num_events=5)

        zip_path = tmp_path / "evidence.arguspack"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for item in bundle_dir.iterdir():
                zf.write(item, arcname=item.name)

        exit_code, report = verify_bundle(zip_path)
        assert exit_code == 0
        assert report["status"] == "SUCCESS"
        assert report["total_events"] == 5

    def test_cli_subprocess_exit_codes(self, tmp_path, keypair):
        """Invoke verify_standalone.py via subprocess to verify standard exit codes."""
        priv_key, _, raw_pub_bytes = keypair
        bundle_dir = tmp_path / "bundle_cli"
        build_synthetic_bundle(bundle_dir, priv_key, raw_pub_bytes, num_events=3)

        script_path = Path("db/cli/verify_standalone.py").resolve()

        # Test Exit Code 0
        res = subprocess.run(
            [sys.executable, str(script_path), str(bundle_dir)],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0
        assert "INTEGRITY VERIFIED (SUCCESS)" in res.stdout

        # Test Exit Code 2 with bad signature
        (bundle_dir / "signature.sig").write_bytes(b"\x00" * 64)
        res_bad_sig = subprocess.run(
            [sys.executable, str(script_path), str(bundle_dir)],
            capture_output=True,
            text=True,
        )
        assert res_bad_sig.returncode == 2

    def test_pure_python_ed25519_verification(self):
        """Verify pure Python Ed25519 math functions directly without external libs."""
        from db.cli.keygen import generate_keypair, save_keypair, load_private_key, load_public_key

        with tempfile.TemporaryDirectory() as td:
            priv_bytes, pub_bytes = generate_keypair()
            priv_p, pub_p = save_keypair(priv_bytes, pub_bytes, td)
            priv = load_private_key(priv_p)
            pub = load_public_key(pub_p)

            raw_pub = pub.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )

            msg = b"Compliance Audit Record 2026"
            sig = priv.sign(msg)

            # Test pure Python math verification
            assert verify_ed25519_pure(raw_pub, msg, sig) is True
            # Tamper message
            assert verify_ed25519_pure(raw_pub, b"Tampered Message", sig) is False
            # Tamper signature
            bad_sig = bytearray(sig)
            bad_sig[10] ^= 0x55
            assert verify_ed25519_pure(raw_pub, msg, bytes(bad_sig)) is False
