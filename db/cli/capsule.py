#!/usr/bin/env python3
"""Argus Forensic Merkle Capsule Generator (NOVEL-009-D).

Generates portable `.arguscap` selective disclosure evidence bundles.
Enables proving that a specific audit event occurred within an Ed25519-signed checkpoint
without disclosing any sibling records in the same checkpoint window.

Bundle Structure (.arguscap - ZIP archive):
  ├── evidence_row.json      # Complete canonical JSON of the single target event
  ├── merkle_proof.json      # O(log2 K) Merkle audit path and intermediate hashes
  ├── checkpoint.json        # Checkpoint envelope metadata, root, and Ed25519 signature
  ├── public_key.pem         # Ed25519 public key corresponding to signing key
  └── verify_capsule.py      # Zero-dependency standalone Python verification script
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union
import zipfile

import psycopg2
import psycopg2.extras

from db.cli.merkle_tree import ArgusMerkleTree, canonical_json_serialize
from db.cli.checkpoint_store import compute_checkpoint_hash
from db.cli.hash_verifier import verify_chain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CapsuleError(Exception):
    """Base exception for capsule generation errors."""
    pass


class SequenceNotFoundError(CapsuleError, ValueError):
    """Raised when sequence_id is not found in audit_log."""
    pass


class UncheckpointedTailError(CapsuleError, ValueError):
    """Raised when sequence_id has not yet been sealed in a checkpoint."""
    pass


class PreMerkleCheckpointError(CapsuleError, ValueError):
    """Raised when the checkpoint covering sequence_id lacks a Merkle root."""
    pass


class RetrospectiveAttestationError(CapsuleError, ValueError):
    """Raised when current ledger state cannot safely be attested for a legacy checkpoint."""
    pass


# ---------------------------------------------------------------------------
# Public Key Resolution
# ---------------------------------------------------------------------------

def resolve_public_key_pem() -> str:
    """Resolve active Ed25519 public key PEM content."""
    candidate_paths = [
        Path("keys/public_key.pem"),
        Path(__file__).resolve().parent.parent.parent / "keys" / "public_key.pem",
        Path.home() / ".argus" / "public_key.pem",
    ]

    for p in candidate_paths:
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                pass

    # Try resolving via keygen if installed
    try:
        from db.cli.keygen import get_default_key_dir
        def_path = Path(get_default_key_dir()) / "public_key.pem"
        if def_path.is_file():
            return def_path.read_text(encoding="utf-8")
    except Exception:
        pass

    # Fallback default hardcoded PEM for standalone tests
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        "MCowBQYDK2VwAyEAV33qkLfpW6ddBp9Ac9ApkkEC7vnxnn5ncsahRoMHOTg=\n"
        "-----END PUBLIC KEY-----\n"
    )


# ---------------------------------------------------------------------------
# Capsule Generator
# ---------------------------------------------------------------------------

def generate_capsule(
    conn: Any,
    seq_id: int,
    output_path: Optional[Union[str, Path]] = None,
    public_key_pem: Optional[str] = None,
    retrospective_signer: Any | None = None,
    public_keys_dir: Optional[Union[str, Path]] = None,
) -> bytes:
    """Generate a self-contained .arguscap Merkle evidence capsule for a single record.

    Args:
        conn: psycopg2 database connection.
        seq_id: The target sequence_id to encapsulate.
        output_path: Optional file path to write the .arguscap file to.
        public_key_pem: Optional explicit public key PEM string.
        retrospective_signer: Optional local/demo signer used only to issue a
            clearly labeled, newly signed attestation for a legacy checkpoint.

    Returns:
        bytes: Raw bytes of the generated .arguscap ZIP archive.

    Raises:
        SequenceNotFoundError: If seq_id does not exist in audit_log.
        UncheckpointedTailError: If seq_id is in uncheckpointed tail.
        PreMerkleCheckpointError: If the checkpoint was created before Merkle roots.
    """
    # 1. Verify sequence_id exists in audit_log
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT sequence_id, actor_user_id, employee_id, action, table_name, row_id, "
            "old_value, new_value, severity, entry_hash, previous_hash, created_at "
            "FROM audit_log WHERE sequence_id = %s",
            (seq_id,),
        )
        target_row = cur.fetchone()

    if target_row is None:
        raise SequenceNotFoundError(f"Sequence ID {seq_id} not found in audit_log.")

    # Preserve database-native values while hashing. The Merkle tree canonicalizer
    # converts datetime objects with ``str``; converting only the capsule copy to
    # ISO-8601 changes the leaf bytes and makes an otherwise valid proof fail.
    target_dict = dict(target_row)

    # 2. Find the enclosing checkpoint: lowest sequence_id >= seq_id
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Check if merkle columns exist
        try:
            cur.execute(
                "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, key_id, "
                "merkle_root, merkle_leaf_count, created_at "
                "FROM chain_checkpoints "
                "WHERE sequence_id >= %s "
                "ORDER BY sequence_id ASC LIMIT 1",
                (seq_id,),
            )
            cp_row = cur.fetchone()
        except Exception:
            conn.rollback()
            # Legacy table fallback
            cur.execute(
                "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
                "FROM chain_checkpoints "
                "WHERE sequence_id >= %s "
                "ORDER BY sequence_id ASC LIMIT 1",
                (seq_id,),
            )
            cp_row = cur.fetchone()

    if cp_row is None:
        raise UncheckpointedTailError(
            f"Sequence ID {seq_id} is in the uncheckpointed tail and has not yet been sealed in a checkpoint."
        )

    cp_dict = dict(cp_row)
    is_retrospective = cp_dict.get("merkle_root") is None
    if is_retrospective and retrospective_signer is None:
        raise PreMerkleCheckpointError(
            f"Checkpoint #{cp_dict.get('checkpoint_id')} for sequence ID {seq_id} "
            "is pre-Merkle (merkle_root is null)."
        )

    target_cp_seq = cp_dict["sequence_id"]

    # 3. Find preceding checkpoint to establish range (prev_cp_seq, target_cp_seq]
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT sequence_id FROM chain_checkpoints "
            "WHERE sequence_id < %s "
            "ORDER BY sequence_id DESC LIMIT 1",
            (target_cp_seq,),
        )
        prev_cp = cur.fetchone()

    prev_cp_seq = prev_cp["sequence_id"] if prev_cp else 0

    # 4. Fetch all rows in checkpoint interval
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT sequence_id, actor_user_id, employee_id, action, table_name, row_id, "
            "old_value, new_value, severity, entry_hash, previous_hash, created_at "
            "FROM audit_log "
            "WHERE sequence_id > %s AND sequence_id <= %s "
            "ORDER BY sequence_id ASC",
            (prev_cp_seq, target_cp_seq),
        )
        interval_rows = cur.fetchall()

    rows = []
    for r in interval_rows:
        rows.append(dict(r))

    # 5. Legacy checkpoints need a separately signed, current-time attestation.
    # Never retrofit their original checkpoint row or claim the derived root
    # was present when that checkpoint was first signed.
    retrospective_payload = None
    retrospective_signature_hex = None
    if is_retrospective:
        verification = verify_chain(conn, end_seq=int(target_cp_seq))
        if not verification.is_valid or verification.last_sequence_id != int(target_cp_seq):
            raise RetrospectiveAttestationError(
                "The audit chain through this legacy checkpoint is not intact; no retrospective proof was issued."
            )

        computed_checkpoint_hash = compute_checkpoint_hash(
            [str(row["entry_hash"]) for row in rows]
        )
        if computed_checkpoint_hash != str(cp_dict["checkpoint_hash"]):
            raise RetrospectiveAttestationError(
                "The legacy checkpoint hash does not match its current audit interval; no retrospective proof was issued."
            )

        original_signature = cp_dict.get("signature")
        if isinstance(original_signature, memoryview):
            original_signature = original_signature.tobytes()
        if not isinstance(original_signature, (bytes, bytearray)) or not retrospective_signer.verify(
            str(cp_dict["checkpoint_hash"]).encode("utf-8"), bytes(original_signature)
        ):
            raise RetrospectiveAttestationError(
                "The original legacy checkpoint signature could not be verified with the configured signer; no retrospective proof was issued."
            )

    # 6. Build Merkle tree and generate proof for seq_id
    tree = ArgusMerkleTree.build(rows)
    proof = tree.generate_proof(seq_id)

    if is_retrospective:
        retrospective_payload = {
            "attestation_type": "ARGUS_RETROSPECTIVE_MERKLE_ATTESTATION",
            "version": 1,
            "checkpoint_id": int(cp_dict["checkpoint_id"]),
            "checkpoint_hash": str(cp_dict["checkpoint_hash"]),
            "checkpoint_created_at": (
                cp_dict["created_at"].isoformat()
                if hasattr(cp_dict.get("created_at"), "isoformat")
                else str(cp_dict.get("created_at", ""))
            ),
            "start_sequence_id": int(prev_cp_seq) + 1,
            "end_sequence_id": int(target_cp_seq),
            "merkle_root": tree.root,
            "merkle_leaf_count": tree.leaf_count,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "key_id": retrospective_signer.key_id,
            "chain_verified_through_sequence_id": int(target_cp_seq),
            "checkpoint_hash_matches_current_interval": True,
            "original_checkpoint_signature_verified": True,
        }
        signed_payload = (
            b"ARGUS_RETROSPECTIVE_MERKLE_ATTESTATION_V1\n"
            + canonical_json_serialize(retrospective_payload).encode("utf-8")
        )
        retrospective_signature_hex = retrospective_signer.sign(signed_payload).hex()

    # 7. Read standalone verifier code
    verifier_path = Path(__file__).resolve().parent / "verify_capsule.py"
    if verifier_path.is_file():
        verifier_content = verifier_path.read_text(encoding="utf-8")
    else:
        verifier_content = "# Argus Standalone Capsule Verifier\n"

    # 8. Format signature hex
    raw_sig = cp_dict.get("signature")
    if isinstance(raw_sig, memoryview):
        raw_sig = raw_sig.tobytes()
    sig_hex = raw_sig.hex() if isinstance(raw_sig, (bytes, bytearray)) else (str(raw_sig) if raw_sig else "")

    checkpoint_payload = {
        "checkpoint_id": cp_dict["checkpoint_id"],
        "start_sequence_id": prev_cp_seq + 1,
        "end_sequence_id": cp_dict["sequence_id"],
        "checkpoint_hash": cp_dict["checkpoint_hash"],
        "merkle_root": cp_dict.get("merkle_root"),
        "merkle_leaf_count": (
            tree.leaf_count if is_retrospective else cp_dict.get("merkle_leaf_count", len(rows))
        ),
        "key_id": cp_dict.get("key_id", "local:ed25519:v1"),
        "signature_hex": sig_hex,
        "created_at": (
            cp_dict["created_at"].isoformat()
            if hasattr(cp_dict.get("created_at"), "isoformat")
            else str(cp_dict.get("created_at", ""))
        ),
    }
    if is_retrospective:
        checkpoint_payload["retrospective_merkle_root"] = tree.root
        checkpoint_payload["retrospective_attestation_issued_at"] = retrospective_payload["issued_at"]

    # 9. Resolve the public key that verifies the retrospective statement.
    if public_key_pem:
        active_pub_pem = public_key_pem
    elif is_retrospective:
        from cryptography.hazmat.primitives import serialization
        active_pub_pem = retrospective_signer.get_public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
    elif public_keys_dir is not None:
        from urllib.parse import quote
        key_id = cp_dict.get('key_id')
        filename = 'public_key.pem' if not key_id or key_id == 'local:ed25519:v1' else f'{quote(str(key_id), safe="")}.pem'
        active_pub_pem = (Path(public_keys_dir) / filename).read_text(encoding='utf-8')
    else:
        active_pub_pem = resolve_public_key_pem()

    # 10. Build .arguscap ZIP archive
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "evidence_row.json",
            json.dumps(target_dict, indent=2, default=str),
        )
        zf.writestr(
            "merkle_proof.json",
            json.dumps(proof.to_dict(), indent=2),
        )
        zf.writestr(
            "checkpoint.json",
            json.dumps(checkpoint_payload, indent=2),
        )
        if is_retrospective:
            zf.writestr(
                "retrospective_attestation.json",
                json.dumps(
                    {
                        "payload": retrospective_payload,
                        "signature_hex": retrospective_signature_hex,
                    },
                    indent=2,
                ),
            )
        zf.writestr(
            "public_key.pem",
            active_pub_pem,
        )
        zf.writestr(
            "verify_capsule.py",
            verifier_content,
        )

    bundle_bytes = zip_buffer.getvalue()

    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bundle_bytes)
        logger.info("Saved .arguscap bundle for seq %d to %s", seq_id, p)

    return bundle_bytes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Argus Forensic Merkle Capsule Generator (NOVEL-009-D)"
    )
    parser.add_argument(
        "--seq",
        type=int,
        required=True,
        help="Sequence ID of the target record to encapsulate",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output path for the .arguscap file (defaults to proof_seq<ID>.arguscap)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection string",
    )

    args = parser.parse_args()
    if not args.db_url:
        parser.error("provide --db-url or set DATABASE_URL")
    out_file = args.output or f"proof_seq{args.seq}.arguscap"

    try:
        conn = psycopg2.connect(args.db_url)
    except Exception as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        return 1

    try:
        generate_capsule(conn, args.seq, output_path=out_file)
        print(f"Successfully generated forensic capsule: {out_file}")
        return 0
    except Exception as e:
        print(f"Capsule generation failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
