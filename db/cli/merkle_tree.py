#!/usr/bin/env python3
"""Argus RFC 6962 / RFC 9162 Merkle Tree Engine (NOVEL-009-B).

Implements a balanced binary Merkle Hash Tree (MHT) constructed per checkpoint
with strict RFC 6962 domain separation prefixes:
  - Leaf hash:     SHA-256(0x00 || canonical_json_bytes)
  - Internal node: SHA-256(0x01 || left_hash_bytes || right_hash_bytes)

Key Security Guarantees:
  1. Second-preimage resistance via domain separation (0x00 vs 0x01).
  2. Odd-leaf promotion (unpaired rightmost node promoted without duplication,
     preventing Bitcoin CVE-2012-2459 duplicate-leaf malleability).
  3. O(log2 K) audit inclusion proofs allowing selective disclosure of a single
     audit record without leaking sibling transactions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Union


# ---------------------------------------------------------------------------
# Canonical Serialization
# ---------------------------------------------------------------------------

def canonical_json_serialize(record: Dict[str, Any]) -> str:
    """Deterministically serialize a dictionary into canonical JSON.

    Enforces alphabetical key ordering, minimal separators (',', ':'),
    and string conversion for non-JSON native types (e.g. datetimes, UUIDs).
    """
    return json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)


def compute_leaf_hash(record: Dict[str, Any]) -> str:
    """Compute RFC 6962 leaf hash: SHA-256(0x00 || canonical_bytes)."""
    canonical_bytes = canonical_json_serialize(record).encode("utf-8")
    return hashlib.sha256(b"\x00" + canonical_bytes).hexdigest()


def compute_parent_hash(left_hex: str, right_hex: str) -> str:
    """Compute RFC 6962 internal parent hash: SHA-256(0x01 || left || right)."""
    left_bytes = bytes.fromhex(left_hex)
    right_bytes = bytes.fromhex(right_hex)
    return hashlib.sha256(b"\x01" + left_bytes + right_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AuditPathStep:
    """A single step along the Merkle inclusion audit path."""
    level: int
    direction: str  # "left" or "right" (sibling position relative to current)
    sibling_hash: str


@dataclass
class MerkleInclusionProof:
    """Cryptographic proof demonstrating record inclusion in a Merkle root."""
    sequence_id: int
    leaf_index: int
    leaf_hash: str
    merkle_root: str
    tree_size: int
    audit_path: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core Merkle Tree Engine
# ---------------------------------------------------------------------------

class ArgusMerkleTree:
    """RFC 6962-compliant Merkle Hash Tree over a slice of audit log records."""

    def __init__(self, records: Sequence[Dict[str, Any]]) -> None:
        if not records:
            raise ValueError("Cannot build Merkle tree over empty audit record slice.")

        self.records: List[Dict[str, Any]] = [dict(r) for r in records]
        self.leaf_count: int = len(self.records)
        self.levels: List[List[str]] = []
        self.seq_to_index: Dict[int, int] = {}

        self._build_tree()

    @classmethod
    def build(cls, records: Sequence[Dict[str, Any]]) -> ArgusMerkleTree:
        """Factory method to construct an ArgusMerkleTree."""
        return cls(records)

    def _build_tree(self) -> None:
        """Construct the balanced Merkle tree with odd-leaf promotion."""
        # Level 0: Leaf hashes (0x00 domain prefix)
        leaf_hashes: List[str] = []
        for idx, record in enumerate(self.records):
            l_hash = compute_leaf_hash(record)
            leaf_hashes.append(l_hash)
            if "sequence_id" in record and record["sequence_id"] is not None:
                self.seq_to_index[int(record["sequence_id"])] = idx

        self.levels.append(leaf_hashes)

        # Build higher levels until root is reached
        current_level = leaf_hashes
        while len(current_level) > 1:
            next_level: List[str] = []
            n = len(current_level)

            for i in range(0, n, 2):
                left_hash = current_level[i]
                if i + 1 < n:
                    right_hash = current_level[i + 1]
                    parent_hash = compute_parent_hash(left_hash, right_hash)
                else:
                    # Odd-leaf promotion (no duplicate hashing, mitigates CVE-2012-2459)
                    parent_hash = left_hash

                next_level.append(parent_hash)

            self.levels.append(next_level)
            current_level = next_level

    @property
    def root(self) -> str:
        """Hex-encoded SHA-256 Merkle root hash."""
        return self.levels[-1][0]

    @property
    def tree_height(self) -> int:
        """Number of levels in the tree (leaves = level 0)."""
        return len(self.levels)

    def get_root(self) -> str:
        """Return the Merkle root hash."""
        return self.root

    def generate_proof(self, sequence_id: int) -> MerkleInclusionProof:
        """Generate an O(log2 K) audit path for a specific sequence ID.

        Args:
            sequence_id: The target sequence_id to generate a proof for.

        Returns:
            MerkleInclusionProof containing the audit path and expected root.

        Raises:
            KeyError: If sequence_id is not in the tree.
        """
        if sequence_id not in self.seq_to_index:
            raise KeyError(f"Sequence ID {sequence_id} not found in this Merkle tree slice.")

        index = self.seq_to_index[sequence_id]
        return self.generate_proof_by_index(index, sequence_id=sequence_id)

    def generate_proof_by_index(
        self, index: int, sequence_id: Optional[int] = None
    ) -> MerkleInclusionProof:
        """Generate an audit path by zero-based leaf index.

        Args:
            index: Zero-based position in the leaf list.
            sequence_id: Optional sequence ID to embed in the proof.

        Returns:
            MerkleInclusionProof.
        """
        if index < 0 or index >= self.leaf_count:
            raise IndexError(f"Leaf index {index} out of range (0 to {self.leaf_count - 1}).")

        leaf_hash = self.levels[0][index]
        audit_path: List[Dict[str, Any]] = []

        curr_idx = index
        # Traverse from level 0 up to level len(levels) - 2
        for lvl in range(len(self.levels) - 1):
            level_nodes = self.levels[lvl]
            is_right = (curr_idx % 2 == 1)

            if is_right:
                # We are the right child, sibling is to our left
                sibling_hash = level_nodes[curr_idx - 1]
                audit_path.append({
                    "level": lvl,
                    "direction": "left",
                    "sibling_hash": sibling_hash,
                })
            else:
                # We are the left child, check if right sibling exists
                if curr_idx + 1 < len(level_nodes):
                    sibling_hash = level_nodes[curr_idx + 1]
                    audit_path.append({
                        "level": lvl,
                        "direction": "right",
                        "sibling_hash": sibling_hash,
                    })
                else:
                    # Promoted directly with no sibling at this level
                    pass

            curr_idx = curr_idx // 2

        seq = sequence_id if sequence_id is not None else int(
            self.records[index].get("sequence_id", index)
        )

        return MerkleInclusionProof(
            sequence_id=seq,
            leaf_index=index,
            leaf_hash=leaf_hash,
            merkle_root=self.root,
            tree_size=self.leaf_count,
            audit_path=audit_path,
        )

    @staticmethod
    def verify_proof(
        record: Dict[str, Any],
        proof: Union[MerkleInclusionProof, Dict[str, Any]],
        expected_root: Optional[str] = None,
    ) -> bool:
        """Verify an RFC 6962 Merkle inclusion proof independently.

        This method operates without access to the full tree or database.

        Args:
            record: The actual audit event dictionary.
            proof: The MerkleInclusionProof or equivalent dict.
            expected_root: Optional expected root. If None, checks against proof's merkle_root.

        Returns:
            True if the record cryptographically hashes to the Merkle root via the path.
        """
        proof_dict = proof.to_dict() if isinstance(proof, MerkleInclusionProof) else proof

        # 1. Compute leaf hash with 0x00 domain separator
        computed_leaf = compute_leaf_hash(record)
        if computed_leaf != proof_dict.get("leaf_hash"):
            return False

        # 2. Walk audit path up the tree using 0x01 domain separator
        current_hash = computed_leaf
        for step in proof_dict.get("audit_path", []):
            direction = step.get("direction")
            sibling_hex = step.get("sibling_hash")
            if not sibling_hex:
                return False

            if direction == "left":
                # Sibling is left of current
                current_hash = compute_parent_hash(sibling_hex, current_hash)
            elif direction == "right":
                # Sibling is right of current
                current_hash = compute_parent_hash(current_hash, sibling_hex)
            else:
                return False

        target_root = expected_root or proof_dict.get("merkle_root")
        return current_hash == target_root
