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
from scripts.cosign_private_anchor import cosign
from api.services.remote_witness import verify_remote_witnesses


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
        manifest["checkpoints"][0]["witnesses"] = [{"name": "auditor.one", "signature_hex": "ab" * 64}]
        extended = prepare_manifest(bundle, key_path, manifest)
        assert extended["checkpoints"][0]["witnesses"] == manifest["checkpoints"][0]["witnesses"]

        # Two witness operators cosign the same independently verified pack.
        manifest["checkpoints"][0].pop("witnesses")
        anchor_path = tmp_path / "anchors.json"
        anchor_path.write_text(json.dumps(manifest), encoding="utf-8")
        trust_dir = tmp_path / "trust"
        trust_dir.mkdir()
        for name, domain in (("auditor.one", "operator-one"), ("auditor.two", "operator-two")):
            witness_key = Ed25519PrivateKey.generate()
            private_path = tmp_path / f"{name}.private.pem"
            private_path.write_bytes(witness_key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
            _, witness_public = cosign(
                bundle=bundle, trusted_origin_key=key_path, anchor_manifest=anchor_path,
                witness_private_key=private_path, state_path=tmp_path / f"{name}.state.json",
                witness_name=name,
            )
            (trust_dir / f"{name}.pem").write_text(witness_public, encoding="utf-8")
            (trust_dir / f"{name}.domain").write_text(domain, encoding="utf-8")
        witnessed = json.loads(anchor_path.read_text(encoding="utf-8"))
        assert verify_remote_witnesses(
            witnessed["checkpoints"], trust_dir,
            origin_public_key_pem=key_path.read_text(encoding="utf-8"),
        ).status == "pass"
        assert "Sensitive Person" not in anchor_path.read_text(encoding="utf-8")

        with pytest.raises(ValueError, match="safely extended"):
            prepare_manifest(bundle, key_path, {"schema_version": 1, "checkpoints": []})

        changed = {**checkpoint, "checkpoint_hash": "f" * 64}
        with zipfile.ZipFile(bundle, "w") as archive:
            archive.writestr("manifest.json", json.dumps(export_manifest))
            archive.writestr("events.jsonl", json.dumps(exported_event) + "\n")
            archive.writestr("checkpoints.json", json.dumps([changed]))
        with pytest.raises(ValueError, match="checkpoint hash"):
            prepare_manifest(bundle, key_path)
