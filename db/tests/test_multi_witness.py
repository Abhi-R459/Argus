"""Unit tests for Argus RFC 9162 Multi-Witness Anchoring & Fork Detection (NOVEL-010-A, B, E)."""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from db.cli.anchor_store import (
    LocalFileAnchorStore,
    MultiWitnessAnchorStore,
)
from db.cli.witness_protocol import (
    CheckpointNote,
    ProofOfMisbehavior,
    QuorumNotMetError,
    WitnessSignature,
    WitnessedCheckpoint,
    verify_witness_quorum,
)
from db.cli.keygen import generate_keypair
from db.cli.signer import sign_checkpoint
from db.cli.witness_config import load_origin_public_key, load_public_keys, resolve_witness_store_path


def _simulated_witness_keys(count=3):
    """Build explicit test-only signers; production code must configure real witnesses."""
    signers = {}
    for index in range(count):
        private_key, _ = generate_keypair()
        signers[f"witness.{index + 1}"] = private_key
    return signers


def _simulated_origin_key():
    """Provide an explicit test-only origin key."""
    private_key, _ = generate_keypair()
    return private_key


def test_api_and_cli_resolve_the_same_witness_store_and_trusted_keys(tmp_path, monkeypatch):
    anchor_file = tmp_path / "anchor" / "chain_anchor.log"
    explicit_store = tmp_path / "anchor" / "multi_witness"
    witness_keys = tmp_path / "witness-keys"
    checkpoint_keys = tmp_path / "checkpoint-keys"
    witness_keys.mkdir(parents=True)
    checkpoint_keys.mkdir(parents=True)
    (witness_keys / "witness%2Eone.pem").write_text("witness-public", encoding="utf-8")
    (checkpoint_keys / "local%3Ademo%3Aed25519%3Av1.pem").write_text("origin-public", encoding="utf-8")

    monkeypatch.setenv("ANCHOR_FILE_PATH", str(anchor_file))
    monkeypatch.delenv("WITNESS_STORE_PATH", raising=False)
    assert resolve_witness_store_path() == anchor_file.parent / "multi_witness"
    monkeypatch.setenv("WITNESS_STORE_PATH", str(explicit_store))
    assert resolve_witness_store_path() == explicit_store
    assert resolve_witness_store_path(str(anchor_file)) == explicit_store
    assert load_public_keys(witness_keys) == {"witness.one": "witness-public"}
    assert load_origin_public_key("local:demo:ed25519:v1", checkpoint_keys) == "origin-public"
    assert load_origin_public_key("untrusted-key-id", checkpoint_keys) is None


def test_multi_witness_store_never_invents_a_quorum(tmp_path):
    store = MultiWitnessAnchorStore(
        threshold=2,
        base_path=str(tmp_path / "empty"),
        origin_signer=_simulated_origin_key(),
    )

    assert store.witness_signers == {}
    assert store.witness_public_keys == {}
    with pytest.raises(QuorumNotMetError):
        store.push(1, json.dumps({"sequence_id": 1, "merkle_root": "a" * 64}))


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_checkpoint_note_serialization():
    """Test RFC 9162 Note body produces canonical deterministic whitespace-sensitive text."""
    note1 = CheckpointNote(
        sequence_id=50,
        merkle_root="a" * 64,
        origin="argus.enterprise/v1/checkpoint",
        timestamp="2026-09-25T12:00:00Z",
        metadata={"checkpoint_id": 2, "entries_count": 25},
    )
    note2 = CheckpointNote(
        sequence_id=50,
        merkle_root="a" * 64,
        origin="argus.enterprise/v1/checkpoint",
        timestamp="2026-09-25T12:00:00Z",
        metadata={"entries_count": 25, "checkpoint_id": 2},  # Reordered keys
    )

    # Must produce identical serialization despite key ordering in metadata
    assert note1.serialize_body() == note2.serialize_body()
    assert note1.body_bytes() == note2.body_bytes()

    # Roundtrip from text
    parsed = CheckpointNote.from_body_text(note1.serialize_body())
    assert parsed.sequence_id == 50
    assert parsed.merkle_root == "a" * 64
    assert parsed.metadata["checkpoint_id"] == 2


def test_witness_signature_rfc9162_formatting():
    """Test RFC 9162 cosignature line formatting and parsing."""
    priv, pub = generate_keypair()
    body = b"sample note body\n"
    sig_bytes = sign_checkpoint(priv, body)

    sig = WitnessSignature(
        witness_name="witness.s3worm.aws/v1",
        signature_bytes=sig_bytes,
        public_key_pem=pub.decode("utf-8"),
    )

    line = sig.format_line()
    assert line.startswith("— witness.s3worm.aws/v1 ")

    parsed_sig = WitnessSignature.from_line(line, public_key_pem=pub.decode("utf-8"))
    assert parsed_sig.witness_name == "witness.s3worm.aws/v1"
    assert parsed_sig.signature_bytes == sig_bytes


def test_quorum_evaluation_2_of_3():
    """Test 2-of-3 threshold quorum evaluation."""
    note = CheckpointNote(sequence_id=10, merkle_root="root1")
    origin_sig = WitnessSignature("argus.origin", b"\x01" * 64)

    witnessed = WitnessedCheckpoint(
        note=note,
        origin_signature=origin_sig,
        witness_signatures=[],
    )
    assert witnessed.quorum_satisfied(threshold=2) is False

    # Add 1 witness signature
    witnessed.add_witness_signature(WitnessSignature("witness.1", b"\x02" * 64))
    assert witnessed.quorum_satisfied(threshold=2) is False

    # Add 2nd witness signature
    witnessed.add_witness_signature(WitnessSignature("witness.2", b"\x03" * 64))
    assert witnessed.quorum_satisfied(threshold=2) is True

    # Adding duplicate witness name does not inflate count
    witnessed.add_witness_signature(WitnessSignature("witness.1", b"\x04" * 64))
    assert len(witnessed.witness_signatures) == 2
    assert witnessed.quorum_satisfied(threshold=2) is True


def test_detect_fork_proof_of_misbehavior():
    """Test that two divergent Merkle roots for the same sequence trigger ProofOfMisbehavior."""
    note_a = CheckpointNote(
        sequence_id=25,
        merkle_root="000000000000000000000000000000000000000000000000000000000000000a",
    )
    note_b = CheckpointNote(
        sequence_id=25,
        merkle_root="000000000000000000000000000000000000000000000000000000000000000b",
    )

    with pytest.raises(ProofOfMisbehavior) as excinfo:
        note_a.detect_fork(note_b)

    assert "CRITICAL CRYPTOGRAPHIC FORK DETECTED" in str(excinfo.value)
    assert excinfo.value.sequence_id == 25
    assert excinfo.value.root_a != excinfo.value.root_b


def test_multi_witness_store_push_and_verify(tmp_path):
    """Test full MultiWitnessAnchorStore flow with 3 witnesses and 2-of-3 quorum."""
    sub1 = LocalFileAnchorStore(str(tmp_path / "sub1"))
    sub2 = LocalFileAnchorStore(str(tmp_path / "sub2"))
    sub3 = LocalFileAnchorStore(str(tmp_path / "sub3"))

    mw_store = MultiWitnessAnchorStore(
        witnesses=[sub1, sub2, sub3],
        threshold=2,
        base_path=str(tmp_path / "mw"),
        witness_signers=_simulated_witness_keys(),
        origin_signer=_simulated_origin_key(),
    )

    payload = json.dumps({
        "checkpoint_id": 1,
        "sequence_id": 25,
        "checkpoint_hash": "cphash" + "0" * 58,
        "merkle_root": "merkle" + "1" * 58,
        "created_at": "2026-09-25T12:00:00Z",
    })

    ref = mw_store.push(1, payload)
    assert "multi_witness://3_of_3/1" in ref

    # Verify both files created
    assert (tmp_path / "mw" / "1.note").is_file()
    assert (tmp_path / "mw" / "1.json").is_file()

    # Sub-stores also received the anchor payload
    assert (tmp_path / "sub1" / "1.json").is_file()
    assert (tmp_path / "sub2" / "1.json").is_file()
    assert (tmp_path / "sub3" / "1.json").is_file()

    # Verify method succeeds
    assert mw_store.verify(1) is True

    # Check witness report
    report = mw_store.get_witness_report(1)
    assert report["checkpoint_id"] == 1
    assert report["quorum_satisfied"] is True
    assert report["cosigned_witnesses"] == 3
    assert len(report["per_witness"]) == 3
    for w in report["per_witness"]:
        assert w["status"] == "VALID"


def test_multi_witness_store_quorum_failure_when_witnesses_fail(tmp_path):
    """Test that disabling witnesses such that count < threshold raises QuorumNotMetError."""
    mw_store = MultiWitnessAnchorStore(
        witnesses=[],
        threshold=3,  # Requires 3
        base_path=str(tmp_path / "mw_fail"),
        witness_signers=_simulated_witness_keys(),
        origin_signer=_simulated_origin_key(),
    )

    # Deliberately remove 2 witness keys so only 1 can cosign
    keys = list(mw_store.witness_signers.keys())
    del mw_store.witness_signers[keys[1]]
    del mw_store.witness_signers[keys[2]]

    payload = json.dumps({
        "checkpoint_id": 1,
        "sequence_id": 25,
        "checkpoint_hash": "abc",
        "merkle_root": "def",
    })

    with pytest.raises(QuorumNotMetError) as excinfo:
        mw_store.push(1, payload)

    assert excinfo.value.collected == 1
    assert excinfo.value.required == 3


def test_multi_witness_store_detects_fork_on_push(tmp_path):
    """Test that pushing a conflicting root for the same sequence raises ProofOfMisbehavior."""
    mw_store = MultiWitnessAnchorStore(
        witnesses=[],
        threshold=2,
        base_path=str(tmp_path / "mw_fork"),
        witness_signers=_simulated_witness_keys(),
        origin_signer=_simulated_origin_key(),
    )

    payload_a = json.dumps({
        "checkpoint_id": 1,
        "sequence_id": 25,
        "merkle_root": "1111111111111111111111111111111111111111111111111111111111111111",
    })
    mw_store.push(1, payload_a)

    # Second conflicting push for the exact same sequence ID 25
    payload_b = json.dumps({
        "checkpoint_id": 2,
        "sequence_id": 25,
        "merkle_root": "2222222222222222222222222222222222222222222222222222222222222222",
    })

    with pytest.raises(ProofOfMisbehavior):
        mw_store.push(2, payload_b)


def test_verifier_report_includes_witness_quorum(capsys):
    """Test that _print_verification_report formats witness quorum correctly."""
    from db.cli.verifier import _print_verification_report
    from types import SimpleNamespace

    dummy_result = SimpleNamespace(
        total_entries=100,
        mismatches=[],
        gaps=[],
        orphans=[],
        is_valid=True,
    )
    witness_report = {
        "quorum_satisfied": True,
        "cosigned_witnesses": 3,
        "total_witnesses": 3,
        "required_threshold": 2,
    }

    _print_verification_report(dummy_result, mode="sequential", witness_report=witness_report)
    out = capsys.readouterr().out
    assert "Witness Quorum         : 3/3 VALID (Threshold: 2)" in out
    assert "VALID" in out

