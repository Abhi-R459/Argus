"""Hash verification engine module.

Provides chain integrity verification functions used by both the sequential
and parallel verification paths.

Functions
---------
recompute_hash        — Recomputes the SHA-256 digest for one audit_log row.
verify_chain          — Sequential chain walk with optional segment bounds.
verify_segment        — Top-level picklable worker for ProcessPoolExecutor.
merge_results         — Combines VerificationResult objects from parallel workers.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from db.cli.chain_walker import walk_chain
except ImportError:
    from .chain_walker import walk_chain  # type: ignore[no-redef]


@dataclass
class VerificationResult:
    """Represents the result of a chain verification.

    Attributes:
        is_valid: True only when mismatches, gaps, and orphans are all empty.
        total_entries: Number of audit_log rows examined.
        mismatches: Rows where the recomputed hash differs from the stored hash.
        gaps: Points where ``sequence_id`` skips (deleted rows).
        orphans: Rows where ``previous_hash`` breaks the chain link.
        last_computed_hash: The hash that was produced for the *last* row in
            the verified range.  Used by the parallel merger to perform
            cross-segment continuity checks after all workers finish.
        last_sequence_id: The ``sequence_id`` of the last row examined.
            ``-1`` when no rows were examined.
    """

    is_valid: bool
    total_entries: int
    mismatches: list[dict] = field(default_factory=list)
    gaps: list[dict] = field(default_factory=list)
    orphans: list[dict] = field(default_factory=list)
    last_computed_hash: str = "0" * 64
    last_sequence_id: int = -1


def recompute_hash(row: dict, prev_hash: str) -> str:
    """Recomputes the SHA-256 hash for an audit log entry.

    Mirrors the exact serialization contract defined in SETUP-002 and
    implemented by the PostgreSQL triggers (Decision #11).

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


def verify_chain(
    conn: Any,
    start_seq: int = 0,
    page_size: int = 500,
    end_seq: Optional[int] = None,
    seed_hash: Optional[str] = None,
) -> VerificationResult:
    """Verifies the integrity of the audit_log chain (or a bounded segment).

    Walks the chain from ``start_seq`` to ``end_seq`` (inclusive), recomputing
    each row's hash and checking for gaps, orphans, and mismatches.

    Args:
        conn: psycopg2 connection object.
        start_seq: The sequence ID to start from (exclusive lower bound).
        page_size: The number of rows to fetch per page.
        end_seq: Optional inclusive upper bound.  ``None`` means read to end.
        seed_hash: The known-good hash to use as the ``previous_hash`` seed
            for the first row in the range.  Defaults to ``'0' * 64`` when
            ``start_seq == 0`` (genesis), or to the stored ``previous_hash``
            of the first row encountered for mid-chain segments.

    Returns:
        A VerificationResult containing the results of the verification,
        including the ``last_computed_hash`` of the final row for cross-
        segment continuity checks.
    """
    total_entries = 0
    mismatches: list[dict] = []
    gaps: list[dict] = []
    orphans: list[dict] = []

    expected_next_seq = start_seq + 1
    # Genesis seed when verifying from the very beginning of the chain.
    last_computed_hash: str = seed_hash if seed_hash is not None else ('0' * 64 if start_seq == 0 else '')
    last_sequence_id = -1

    for batch in walk_chain(conn, start_seq, page_size, end_seq=end_seq):
        for row in batch:
            seq = row['sequence_id']

            # For mid-chain segments with no explicit seed, bootstrap from the
            # stored previous_hash of the first row we encounter.
            if last_computed_hash == '':
                last_computed_hash = row['previous_hash']
                expected_next_seq = seq

            # Check gap
            if seq != expected_next_seq:
                gaps.append({
                    'expected_seq': expected_next_seq,
                    'actual_seq': seq
                })

            # Check orphan — previous_hash must continue from the last row.
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
            last_sequence_id = seq
            expected_next_seq = seq + 1
            total_entries += 1

    is_valid = len(mismatches) == 0 and len(gaps) == 0 and len(orphans) == 0

    return VerificationResult(
        is_valid=is_valid,
        total_entries=total_entries,
        mismatches=mismatches,
        gaps=gaps,
        orphans=orphans,
        last_computed_hash=last_computed_hash,
        last_sequence_id=last_sequence_id,
    )


def verify_segment(
    db_url: str,
    start_seq: int,
    end_seq: Optional[int],
    seed_hash: str,
    page_size: int,
) -> VerificationResult:
    """Top-level picklable worker function for ProcessPoolExecutor.

    Opens its own database connection (connections cannot be shared across
    processes), verifies the chain segment ``(start_seq, end_seq]``, and
    returns the result.  Must be a module-level function so that the
    ``multiprocessing`` ``pickle`` mechanism can serialise it.

    Args:
        db_url: PostgreSQL connection string passed from the parent process.
        start_seq: Exclusive lower bound sequence ID for this segment.
        end_seq: Inclusive upper bound sequence ID (``None`` = to end of log).
        seed_hash: The ``last_computed_hash`` from the preceding segment (or
            ``'0' * 64`` for the very first segment).
        page_size: Batch size for keyset pagination.

    Returns:
        VerificationResult for this segment, including ``last_computed_hash``
        so the parent process can check cross-segment continuity.
    """
    import psycopg2  # local import — subprocess has its own import context

    conn = psycopg2.connect(db_url)
    try:
        return verify_chain(
            conn,
            start_seq=start_seq,
            page_size=page_size,
            end_seq=end_seq,
            seed_hash=seed_hash,
        )
    finally:
        conn.close()


def merge_results(results: list[VerificationResult]) -> VerificationResult:
    """Merges per-segment VerificationResult objects into one unified report.

    Combines mismatches, gaps, and orphans from all segments.  ``total_entries``
    is the sum.  ``is_valid`` is ``True`` only when *all* segments are valid.
    ``last_computed_hash`` and ``last_sequence_id`` reflect the final segment.

    Args:
        results: List of VerificationResult objects, one per segment, ordered
            by ascending segment start sequence.

    Returns:
        A single merged VerificationResult.  Returns an empty valid result
        when ``results`` is empty.
    """
    if not results:
        return VerificationResult(
            is_valid=True,
            total_entries=0,
            last_computed_hash='0' * 64,
            last_sequence_id=-1,
        )

    total_entries = 0
    all_mismatches: list[dict] = []
    all_gaps: list[dict] = []
    all_orphans: list[dict] = []

    for r in results:
        total_entries += r.total_entries
        all_mismatches.extend(r.mismatches)
        all_gaps.extend(r.gaps)
        all_orphans.extend(r.orphans)

    # Sort combined anomaly lists by sequence_id for a clean report.
    all_mismatches.sort(key=lambda x: x.get('sequence_id', 0))
    all_gaps.sort(key=lambda x: x.get('actual_seq', 0))
    all_orphans.sort(key=lambda x: x.get('sequence_id', 0))

    is_valid = len(all_mismatches) == 0 and len(all_gaps) == 0 and len(all_orphans) == 0
    last = results[-1]

    return VerificationResult(
        is_valid=is_valid,
        total_entries=total_entries,
        mismatches=all_mismatches,
        gaps=all_gaps,
        orphans=all_orphans,
        last_computed_hash=last.last_computed_hash,
        last_sequence_id=last.last_sequence_id,
    )
