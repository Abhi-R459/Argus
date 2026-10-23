"""Offline witness cosigning of a verified Argus evidence pack.

Run this on a witness-operated machine. Keep the private key and state file off
Argus, its Render services, and the private anchor repository. This command
updates a local anchors.json copy; publication remains an operator action.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.services.remote_witness import checkpoint_prefix_bytes, checkpoint_prefix_digest  # noqa: E402
from scripts.prepare_private_anchor import prepare_manifest  # noqa: E402


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def cosign(
    *, bundle: Path, trusted_origin_key: Path, anchor_manifest: Path,
    witness_private_key: Path, state_path: Path, witness_name: str,
) -> tuple[int, str]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,100}", witness_name):
        raise ValueError("Witness name must be 2-101 lowercase letters, numbers, dots, underscores or dashes.")
    if not anchor_manifest.is_file():
        raise ValueError("Fetch the current private anchors.json before cosigning.")
    existing = json.loads(anchor_manifest.read_text(encoding="utf-8"))
    manifest = prepare_manifest(bundle, trusted_origin_key, existing)
    checkpoints = manifest["checkpoints"]
    latest_index = len(checkpoints) - 1
    latest = checkpoints[latest_index]
    latest_digest = checkpoint_prefix_digest(checkpoints, latest_index)

    if state_path.is_file():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        previous_id = previous.get("checkpoint_id")
        matching = next((i for i, row in enumerate(checkpoints) if row["checkpoint_id"] == previous_id), None)
        if matching is None or checkpoint_prefix_digest(checkpoints, matching) != previous.get("prefix_sha256"):
            raise ValueError("The evidence pack conflicts with this witness's retained checkpoint state.")
        if matching > latest_index:
            raise ValueError("The private anchor has been rolled back behind witness state.")

    key = load_pem_private_key(witness_private_key.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("The witness private key must be Ed25519.")
    signature_hex = key.sign(checkpoint_prefix_bytes(checkpoints, latest_index)).hex()
    witnesses = latest.setdefault("witnesses", [])
    if not isinstance(witnesses, list):
        raise ValueError("The existing witness signature list is malformed.")
    prior = next((item for item in witnesses if isinstance(item, dict) and item.get("name") == witness_name), None)
    if prior and prior.get("signature_hex") != signature_hex:
        raise ValueError("An existing signature for this witness conflicts with the verified checkpoint.")
    if not prior:
        witnesses.append({"name": witness_name, "signature_hex": signature_hex})
    _atomic_json(anchor_manifest, manifest)
    _atomic_json(state_path, {"schema_version": 1, "checkpoint_id": latest["checkpoint_id"], "prefix_sha256": latest_digest})
    return latest["checkpoint_id"], key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cosign a verified private Argus checkpoint anchor")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--trusted-origin-key", type=Path, required=True)
    parser.add_argument("--anchor-manifest", type=Path, required=True)
    parser.add_argument("--witness-private-key", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    checkpoint_id, public_key = cosign(
        bundle=args.bundle, trusted_origin_key=args.trusted_origin_key,
        anchor_manifest=args.anchor_manifest, witness_private_key=args.witness_private_key,
        state_path=args.state, witness_name=args.name,
    )
    print(f"Witnessed checkpoint {checkpoint_id}. Publish the updated anchor manifest after review.")
    print("Register this witness public key in a separately reviewed trust configuration:\n" + public_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
