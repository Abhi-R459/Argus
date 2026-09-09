"""Chain walker module for iterating over the audit_log."""

from typing import Generator, Any, Optional
import psycopg2.extras


def walk_chain(
    conn: Any,
    start_seq: int = 0,
    page_size: int = 500,
    end_seq: Optional[int] = None,
) -> Generator[list[dict], None, None]:
    """Walks the audit_log chain using keyset pagination.

    Args:
        conn: psycopg2 connection object.
        start_seq: The sequence ID to start from (exclusive lower bound).
        page_size: The number of rows to fetch per page.
        end_seq: Optional inclusive upper bound on sequence_id.  When set,
            only rows with ``sequence_id <= end_seq`` are returned.  This is
            used by parallel segment workers so that each worker confines itself
            to its assigned checkpoint-bounded range.

    Yields:
        A list of dictionaries representing a batch of audit_log rows.
    """
    if end_seq is not None:
        query = (
            "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
            "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
            "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
            "FROM audit_log "
            "WHERE sequence_id > %s AND sequence_id <= %s "
            "ORDER BY sequence_id "
            "LIMIT %s"
        )
    else:
        query = (
            "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
            "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
            "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
            "FROM audit_log "
            "WHERE sequence_id > %s "
            "ORDER BY sequence_id "
            "LIMIT %s"
        )

    current_seq = start_seq
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        while True:
            if end_seq is not None:
                cursor.execute(query, (current_seq, end_seq, page_size))
            else:
                cursor.execute(query, (current_seq, page_size))

            batch = cursor.fetchall()
            if not batch:
                break

            # Since RealDictRow is a dict subclass, we can yield the list of dicts directly
            yield list(batch)

            current_seq = batch[-1]['sequence_id']
