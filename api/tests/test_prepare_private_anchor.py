"""Publishing never copies personnel events into the private anchor repository."""

import json
from pathlib import Path
from unittest.mock import patch
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from db.cli.checkpoint_store import compute_checkpoint_hash
from db.cli.merkle_tree import ArgusMerkleTree
from scripts.prepare_private_anchor import prepare_manifest


def test_prepared_anchor_is_pii_free_and_rejects_changed_evidence(tmp_path: Path):
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    key_path = tmp_path / "trusted.pem"
    key_path.write_bytes(public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    event = {
        "sequence_id": 1, "actor_user_id": 1, "employee_id": 2,
        "action": "INSERT", "table_name": "employees", "row_id": 2,
        "old_value": None, "new_value": {"full_name": "Sensitive Person"},
        "severity": "INFO", "entry_hash": "a" * 64,
        "previous_hash": "0" * 64, "created_at": "2026-10-15 00:00:00+00:00",
    }
    checkpoint_hash = compute_checkpoint_hash([event["entry_hash"]])
    root = ArgusMerkleTree.build([event]).root
    checkpoint = {
        "checkpoint_id": 1, "sequence_id": 1,
        "checkpoint_hash": checkpoint_hash, "merkle_root": root,
        "merkle_leaf_count": 1, "key_id": "local:ed25519:v1",
        "signature_hex": private_key.sign(f"{checkpoint_hash}:{root}".encode()).hex(),
    }
    exported_event = {key: value for key, value in event.items() if key not in ("old_value", "new_value", "created_at")}
    exported_event.update({
        "old_value_text": None,
        "new_value_text": json.dumps(event["new_value"]),
        "created_at_text": event["created_at"],
    })
    bundle = tmp_path / "evidence.arguspack"
    export_manifest = {
        "public_key_hex": public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        ).hex(),
    }
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("manifest.json", json.dumps(export_manifest))
        archive.writestr("events.jsonl", json.dumps(exported_event) + "\n")
        archive.writestr("checkpoints.json", json.dumps([checkpoint]))

    with patch("scripts.prepare_private_anchor.verify_bundle", return_value=(0, {})):
        manifest = prepare_manifest(bundle, key_path)
        encoded = json.dumps(manifest)
        assert "Sensitive Person" not in encoded
        assert "full_name" not in encoded
        assert manifest["checkpoints"][0]["checkpoint_hash"] == checkpoint_hash

        with pytest.raises(ValueError, match="safely extended"):
            prepare_manifest(bundle, key_path, {"schema_version": 1, "checkpoints": []})

        changed = {**checkpoint, "checkpoint_hash": "f" * 64}
        with zipfile.ZipFile(bundle, "w") as archive:
            archive.writestr("manifest.json", json.dumps(export_manifest))
            archive.writestr("events.jsonl", json.dumps(exported_event) + "\n")
            archive.writestr("checkpoints.json", json.dumps([changed]))
        with pytest.raises(ValueError, match="checkpoint hash"):
            prepare_manifest(bundle, key_path)
