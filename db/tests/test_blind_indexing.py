"""Phase 7 Acceptance Suite: HMAC Blind Indexing (TEST-007 / 7.D.1).

Validates HMAC blind indexing creation, trigger execution, functional B-tree
indexing, and search without plaintext PII leakage.
"""

from db.tests.test_blind_indexing_db import (
    memory_engine,
    test_migration_010_upgrade_and_downgrade,
    test_compute_blind_index_algorithm,
    test_mask_employee_payload_preserves_privacy,
)
