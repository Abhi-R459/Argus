"""Tests for Argus RFC 6962 Merkle Tree Engine (NOVEL-009-B & NOVEL-009-H)."""

import hashlib
import json
import pytest

from db.cli.merkle_tree import (
    ArgusMerkleTree,
    canonical_json_serialize,
    compute_leaf_hash,
    compute_parent_hash,
)


@pytest.fixture
def sample_rows():
    """Generate 25 sample audit rows matching Argus schema."""
    rows = []
    for i in range(1, 26):
        rows.append({
            "sequence_id": i,
            "actor_user_id": 1,
            "employee_id": 42,
            "action": "UPDATE" if i % 2 == 0 else "INSERT",
            "table_name": "employees",
            "row_id": 42,
            "old_value": {"salary": 80000 + (i - 1) * 1000},
            "new_value": {"salary": 80000 + i * 1000},
            "severity": "INFO",
            "created_at": f"2026-09-25T12:{i:02d}:00+00:00",
        })
    return rows


class TestArgusMerkleTree:
    """Test suite for ArgusMerkleTree."""

    def test_root_determinism(self, sample_rows):
        """Same input rows must yield identical root; single byte mutation changes root."""
        tree1 = ArgusMerkleTree.build(sample_rows)
        tree2 = ArgusMerkleTree.build(sample_rows)
        assert tree1.root == tree2.root
        assert len(tree1.root) == 64

        # Mutate single value in row 5
        mutated_rows = [dict(r) for r in sample_rows]
        mutated_rows[4] = dict(mutated_rows[4])
        mutated_rows[4]["new_value"] = {"salary": 999999}
        tree_mutated = ArgusMerkleTree.build(mutated_rows)

        assert tree_mutated.root != tree1.root

    def test_proof_valid_all_leaves(self, sample_rows):
        """Inclusion proof must verify to True for every leaf in the tree."""
        tree = ArgusMerkleTree.build(sample_rows)
        for row in sample_rows:
            proof = tree.generate_proof(row["sequence_id"])
            assert proof.merkle_root == tree.root
            assert ArgusMerkleTree.verify_proof(row, proof) is True

    def test_tampered_row_detected(self, sample_rows):
        """Mutated record must fail verification against valid proof."""
        tree = ArgusMerkleTree.build(sample_rows)
        target_row = sample_rows[10]
        proof = tree.generate_proof(target_row["sequence_id"])

        # Tampered record
        tampered_row = dict(target_row)
        tampered_row["new_value"] = {"salary": 1234567}

        assert ArgusMerkleTree.verify_proof(tampered_row, proof) is False

    def test_tampered_proof_path_detected(self, sample_rows):
        """Corrupted sibling hash in proof must fail verification."""
        tree = ArgusMerkleTree.build(sample_rows)
        proof = tree.generate_proof(sample_rows[0]["sequence_id"])
        proof_dict = proof.to_dict()

        if proof_dict["audit_path"]:
            proof_dict["audit_path"][0]["sibling_hash"] = "0" * 64
            assert ArgusMerkleTree.verify_proof(sample_rows[0], proof_dict) is False

    def test_odd_leaf_promotion(self):
        """Trees with odd leaf counts (1, 3, 5, 7, 13) must promote unpaired node and verify."""
        for count in [1, 3, 5, 7, 13, 21]:
            rows = [{"sequence_id": i, "payload": f"test_{i}"} for i in range(1, count + 1)]
            tree = ArgusMerkleTree.build(rows)
            assert tree.leaf_count == count
            for row in rows:
                proof = tree.generate_proof(row["sequence_id"])
                assert ArgusMerkleTree.verify_proof(row, proof) is True

    def test_domain_separation_rfc6962(self):
        """Leaf hashes must use 0x00 prefix; internal parent hashes must use 0x01 prefix."""
        record = {"a": 1, "b": "test"}
        canonical_bytes = canonical_json_serialize(record).encode("utf-8")

        # True leaf hash
        expected_leaf = hashlib.sha256(b"\x00" + canonical_bytes).hexdigest()
        assert compute_leaf_hash(record) == expected_leaf

        # Contrast with naive SHA256 (no domain separator)
        naive_hash = hashlib.sha256(canonical_bytes).hexdigest()
        assert compute_leaf_hash(record) != naive_hash

        # Internal node hash
        h1 = "a" * 64
        h2 = "b" * 64
        expected_parent = hashlib.sha256(b"\x01" + bytes.fromhex(h1) + bytes.fromhex(h2)).hexdigest()
        assert compute_parent_hash(h1, h2) == expected_parent

    def test_proof_size_logarithmic(self, sample_rows):
        """For K=25 leaves, proof length must be <= ceil(log2(25)) = 5 hashes."""
        tree = ArgusMerkleTree.build(sample_rows)
        for row in sample_rows:
            proof = tree.generate_proof(row["sequence_id"])
            assert len(proof.audit_path) <= 5

    def test_empty_slice_raises(self):
        """Building tree on empty list must raise ValueError."""
        with pytest.raises(ValueError, match="Cannot build Merkle tree over empty"):
            ArgusMerkleTree.build([])

    def test_missing_sequence_id_raises(self, sample_rows):
        """Requesting proof for non-existent sequence_id must raise KeyError."""
        tree = ArgusMerkleTree.build(sample_rows)
        with pytest.raises(KeyError, match="not found in this Merkle tree slice"):
            tree.generate_proof(99999)
