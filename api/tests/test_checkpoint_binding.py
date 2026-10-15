"""A valid hash chain must also match its signed checkpoint contents."""

from datetime import datetime, timezone

from api.services.checkpoint_binding import verify_checkpoint_bindings
from db.cli.checkpoint_store import compute_checkpoint_hash
from db.cli.merkle_tree import ArgusMerkleTree


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.query = ""
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, query, parameters=None):
        self.query = query
        self.parameters = parameters

    def fetchall(self):
        if "FROM chain_checkpoints" in self.query:
            return self.connection.checkpoints
        lower, upper = self.parameters
        return [row for row in self.connection.records if lower < row["sequence_id"] <= upper]


class FakeConnection:
    def __init__(self, records, checkpoints):
        self.records = records
        self.checkpoints = checkpoints

    def cursor(self, **_kwargs):
        return FakeCursor(self)


def _record(seq, entry_hash):
    return {
        "sequence_id": seq, "actor_user_id": 1, "employee_id": 2,
        "action": "UPDATE", "table_name": "employees", "row_id": 2,
        "old_value": {"name": "Before"}, "new_value": {"name": "After"},
        "severity": "INFO", "entry_hash": entry_hash,
        "previous_hash": "0" * 64, "created_at": datetime(2026, 10, 15, tzinfo=timezone.utc),
    }


def test_checkpoint_binding_detects_rewritten_ledger_even_when_chain_is_valid():
    records = [_record(1, "a" * 64), _record(2, "b" * 64)]
    checkpoint = (
        1, 2, compute_checkpoint_hash([row["entry_hash"] for row in records]),
        ArgusMerkleTree.build(records).root, 2,
    )
    conn = FakeConnection(records, [checkpoint])
    assert verify_checkpoint_bindings(conn).status == "pass"

    conn.records = [{**records[0], "entry_hash": "c" * 64}, records[1]]
    assert verify_checkpoint_bindings(conn).status == "fail"

    conn.records = [{**records[0], "new_value": {"name": "Altered"}}, records[1]]
    assert verify_checkpoint_bindings(conn).status == "fail"

    conn.records = records[:1]
    assert verify_checkpoint_bindings(conn).status == "fail"
