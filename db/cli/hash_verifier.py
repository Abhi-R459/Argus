"""Hash verification engine module."""

import hashlib
from dataclasses import dataclass, field
from typing import Any

try:
    from db.cli.chain_walker import walk_chain
except ImportError:
    from .chain_walker import walk_chain


@dataclass
class VerificationResult:
    """Represents the result of a chain verification."""
    is_valid: bool
    total_entries: int
    mismatches: list[dict] = field(default_factory=list)
    gaps: list[dict] = field(default_factory=list)
    orphans: list[dict] = field(default_factory=list)


def recompute_hash(row: dict, prev_hash: str) -> str:
    """Recomputes the SHA-256 hash for an audit log entry.

    Args:
        row: A dictionary containing the audit_log row data.
        prev_hash: The previous hash string.

    Returns:
        The recomputed SHA-256 hex digest.
    """
    old_value_str = row['old_value_text'] if row['old_value_text'] is not None else 'null'
    new_value_str = row['new_value_text'] if row['new_value_text'] is not None else 'null'
    
    serialized = (
        f"{str(row['sequence_id'])}|{str(row['actor_user_id'])}|"
        f"{row['action']}|{row['table_name']}|{str(row['row_id'])}|"
        f"{old_value_str}|{new_value_str}|{row['created_at_text']}"
    )
    
    return hashlib.sha256((serialized + prev_hash).encode('utf-8')).hexdigest()


def verify_chain(conn: Any, start_seq: int = 0, page_size: int = 500) -> VerificationResult:
    """Verifies the integrity of the audit_log chain.

    Args:
        conn: psycopg2 connection object.
        start_seq: The sequence ID to start from.
        page_size: The number of rows to fetch per page.

    Returns:
        A VerificationResult containing the results of the verification.
    """
    total_entries = 0
    mismatches = []
    gaps = []
    orphans = []
    
    expected_next_seq = start_seq + 1
    # The very first row's previous_hash should equal the initial chain seed
    last_computed_hash = '0' * 64 if start_seq == 0 else None
    
    for batch in walk_chain(conn, start_seq, page_size):
        for row in batch:
            seq = row['sequence_id']
            
            # Setup last_computed_hash for first element if not start_seq == 0
            if last_computed_hash is None:
                last_computed_hash = row['previous_hash']
                expected_next_seq = seq
            
            # Check gap
            if seq != expected_next_seq:
                gaps.append({
                    'expected_seq': expected_next_seq,
                    'actual_seq': seq
                })
            
            # Check orphan
            if row['previous_hash'] != last_computed_hash:
                orphans.append({
                    'sequence_id': seq,
                    'expected_prev': last_computed_hash,
                    'actual_prev': row['previous_hash']
                })
            
            # Recompute and check hash mismatch
            recomputed = recompute_hash(row, row['previous_hash'])
            if recomputed != row['entry_hash']:
                mismatches.append({
                    'sequence_id': seq,
                    'expected': row['entry_hash'],
                    'actual': recomputed,
                    'type': 'mismatch'
                })
            
            last_computed_hash = recomputed
            expected_next_seq = seq + 1
            total_entries += 1

    is_valid = len(mismatches) == 0 and len(gaps) == 0 and len(orphans) == 0
    
    return VerificationResult(
        is_valid=is_valid,
        total_entries=total_entries,
        mismatches=mismatches,
        gaps=gaps,
        orphans=orphans
    )
