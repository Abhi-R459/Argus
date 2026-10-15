"""Prepare a PII-free anchor manifest from a verified Argus evidence pack.

The resulting anchors.json belongs in a separately controlled private GitHub
repository. The API only reads it; this operator command never pushes or logs in.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import zipfile

from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.services.remote_anchor import compare_manifest  # noqa: E402
from db.cli.checkpoint_store import compute_checkpoint_hash  # noqa: E402
from db.cli.merkle_tree import ArgusMerkleTree  # noqa: E402
from db.cli.verify_standalone import verify_bundle  # noqa: E402


def prepare_manifest(bundle_path: Path, trusted_public_key_path: Path, existing: dict | None = None) -> dict:
    result, _report = verify_bundle(bundle_path)
    if result != 0:
        raise ValueError("The evidence pack failed standalone verification.")

    trusted = serialization.load_pem_public_key(trusted_public_key_path.read_bytes())
    trusted_raw = trusted.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    with zipfile.ZipFile(bundle_path) as archive:
        export_manifest = json.loads(archive.read("manifest.json"))
        if export_manifest.get("public_key_hex") != trusted_raw.hex():
            raise ValueError("The evidence pack uses a different signing key than the trusted key.")
        checkpoints = json.loads(archive.read("checkpoints.json"))
        events = [json.loads(line) for line in archive.read("events.jsonl").decode("utf-8").splitlines() if line.strip()]

    restored = []
    for event in events:
        record = {key: value for key, value in event.items() if key not in ("old_value_text", "new_value_text", "created_at_text")}
        record["old_value"] = json.loads(event["old_value_text"]) if event["old_value_text"] else None
        record["new_value"] = json.loads(event["new_value_text"]) if event["new_value_text"] else None
        record["created_at"] = datetime.fromisoformat(event["created_at_text"])
        restored.append(record)

    public_checkpoints = []
    previous_sequence = 0
    for checkpoint in checkpoints:
        end_sequence = checkpoint["sequence_id"]
        interval = [row for row in restored if previous_sequence < row["sequence_id"] <= end_sequence]
        if not interval or len(interval) != checkpoint["merkle_leaf_count"]:
            raise ValueError("A checkpoint does not cover the expected audit events.")
        if compute_checkpoint_hash([row["entry_hash"] for row in interval]) != checkpoint["checkpoint_hash"]:
            raise ValueError("An audit interval does not match its checkpoint hash.")
        if ArgusMerkleTree.build(interval).root != checkpoint["merkle_root"]:
            raise ValueError("An audit interval does not match its Merkle root.")
        trusted.verify(
            bytes.fromhex(checkpoint["signature_hex"]),
            f"{checkpoint['checkpoint_hash']}:{checkpoint['merkle_root']}".encode("utf-8"),
        )
        public_checkpoints.append({
            "checkpoint_id": checkpoint["checkpoint_id"],
            "sequence_id": end_sequence,
            "checkpoint_hash": checkpoint["checkpoint_hash"],
            "merkle_root": checkpoint["merkle_root"],
            "signature_hex": checkpoint["signature_hex"],
            "key_id": checkpoint["key_id"] or "",
        })
        previous_sequence = end_sequence

    if not public_checkpoints:
        raise ValueError("The evidence pack contains no signed checkpoints.")
    if existing is not None:
        comparison = compare_manifest(public_checkpoints, existing)
        if comparison.status != "pass" and comparison.detail != "New signed checkpoints are awaiting publication to the private anchor.":
            raise ValueError("Existing anchors cannot be safely extended from this evidence pack.")

    return {
        "schema_version": 1,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "checkpoints": public_checkpoints,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a private, PII-free Argus checkpoint anchor")
    parser.add_argument("--bundle", type=Path, required=True, help="Auditor-exported .arguspack file")
    parser.add_argument("--trusted-public-key", type=Path, default=ROOT / "keys/production/public_key.pem")
    parser.add_argument("--output", type=Path, required=True, help="Private repository's anchors.json")
    arguments = parser.parse_args()

    previous = json.loads(arguments.output.read_text(encoding="utf-8")) if arguments.output.exists() else None
    manifest = prepare_manifest(arguments.bundle, arguments.trusted_public_key, previous)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = arguments.output.with_name(arguments.output.name + ".tmp")
    try:
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, arguments.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        f"Prepared {len(manifest['checkpoints'])} private checkpoint anchors "
        f"through sequence {manifest['checkpoints'][-1]['sequence_id']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
