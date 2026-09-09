"""Chain locking helper module.

Provides a context manager to acquire a row-level lock (FOR UPDATE) on the
singleton chain_state row (id=1) to serialize hash chain mutations.
"""

from contextlib import contextmanager
from typing import Any


@contextmanager
def chain_lock(conn: Any):
    """Context manager that executes SELECT ... FOR UPDATE on chain_state (id=1).
    
    Args:
        conn: DBAPI connection, cursor, or SQLAlchemy Connection/Session.
    
    Yields:
        The locked row sequence / connection.
    """
    # Determine dialect if available
    is_sqlite = False
    if hasattr(conn, "engine") and conn.engine.dialect.name == "sqlite":
        is_sqlite = True
    elif hasattr(conn, "dialect") and conn.dialect.name == "sqlite":
        is_sqlite = True

    lock_sql = "SELECT id FROM chain_state WHERE id = 1" if is_sqlite else "SELECT id FROM chain_state WHERE id = 1 FOR UPDATE"

    if hasattr(conn, "execute"):
        # SQLAlchemy Connection / Engine or DBAPI cursor
        from sqlalchemy import text
        conn.execute(text(lock_sql))
    elif hasattr(conn, "cursor"):
        # DBAPI connection (e.g. psycopg2)
        with conn.cursor() as cur:
            cur.execute(lock_sql)
    else:
        raise ValueError("Unsupported connection object provided to chain_lock")
    
    try:
        yield conn
    finally:
        # Lock is automatically released upon transaction COMMIT / ROLLBACK by PostgreSQL
        pass
