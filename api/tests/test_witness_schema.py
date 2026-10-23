"""The independent witness's database enforces append-only history itself."""

import sqlite3
from pathlib import Path

import pytest


SCHEMA = Path(__file__).resolve().parents[2] / "witness_service" / "cloudflare" / "schema.sql"


def _row(ordinal: int, checkpoint_id: int, sequence_id: int) -> tuple:
    return (
        ordinal, checkpoint_id, sequence_id, "a" * 64, "b" * 64,
        "c" * 128, "local:ed25519:v1",
    )


def test_witness_history_is_relational_and_append_only():
    with sqlite3.connect(":memory:") as db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        columns = [row[1] for row in db.execute("PRAGMA table_info(checkpoints)")]
        assert columns == [
            "ordinal", "checkpoint_id", "sequence_id", "checkpoint_hash",
            "merkle_root", "signature_hex", "key_id",
        ]

        insert = ("INSERT INTO checkpoints "
                  "(ordinal, checkpoint_id, sequence_id, checkpoint_hash, merkle_root, signature_hex, key_id) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?)")
        db.execute(insert, _row(1, 10, 25))
        db.execute(insert, _row(2, 20, 50))

        for bad in (
            _row(4, 30, 75),  # ordinal gap
            _row(3, 15, 75),  # checkpoint ID goes backwards
            _row(3, 30, 40),  # sequence goes backwards
            (3, 30, 75, "z" * 64, "b" * 64, "c" * 128, "key"),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(insert, bad)

        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE checkpoints SET sequence_id = 99 WHERE ordinal = 2")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM checkpoints WHERE ordinal = 2")
        assert db.execute("SELECT count(*) FROM checkpoints").fetchone()[0] == 2
