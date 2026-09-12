"""Adversary CLI Integration Test Suite (ADV-002 / Intermediate Test Gate 2).

Validates:
1. CLI argument parsing and help output across all subcommands.
2. Direct superuser SQL row tampering (dba-row-tamper) detection & healing.
3. Forward hash recalculation (recompute-and-hide) vs external anchor store detection & healing.
4. Checkpoint signature corruption (checkpoint-forgery) detection & healing.
5. Direct audit_log row deletion (delete-audit-row) gap detection & healing.
6. Subprocess execution roundtrip across CLI commands.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

import psycopg2

from db.cli.adversary import (
    get_admin_connection,
    resolve_db_url,
    attack_dba_row_tamper,
    attack_recompute_and_hide,
    attack_checkpoint_forgery,
    attack_delete_audit_row,
    heal_database,
    get_adversary_status,
    load_snapshot,
    build_parser,
)
from db.cli.hash_verifier import verify_chain
from db.cli.signer import verify_signature
from db.cli.keygen import load_public_key, get_default_key_dir


@pytest.fixture
def db_conn():
    """Create live administrative database connection."""
    url = resolve_db_url()
    try:
        conn = psycopg2.connect(url, connect_timeout=3)
    except psycopg2.Error as exc:
        pytest.skip(f"Database not reachable for live adversary tests: {exc}")

    yield conn
    conn.close()


@pytest.fixture
def isolated_snapshot(tmp_path):
    """Provide an isolated snapshot path to prevent test collisions."""
    snap_file = tmp_path / ".test_adversary_snapshot.json"
    yield str(snap_file)
    if snap_file.exists():
        snap_file.unlink()


def test_adversary_cli_parser():
    """Validate CLI argument parser subcommands and arguments."""
    parser = build_parser()
    
    # Test attack parser
    args_attack = parser.parse_args(["attack", "--scenario", "dba-row-tamper", "--sequence-id", "10"])
    assert args_attack.command == "attack"
    assert args_attack.scenario == "dba-row-tamper"
    assert args_attack.sequence_id == 10

    # Test heal parser with snapshot path
    args_heal = parser.parse_args(["heal", "--snapshot-path", "custom_snap.json"])
    assert args_heal.command == "heal"
    assert args_heal.snapshot_path == "custom_snap.json"

    # Test status parser with snapshot path
    args_status = parser.parse_args(["status", "--snapshot-path", "status_snap.json"])
    assert args_status.command == "status"
    assert args_status.snapshot_path == "status_snap.json"


def test_dba_row_tamper_and_heal_cycle(db_conn, isolated_snapshot):
    """Test scenario 1: dba-row-tamper detection and healing."""
    try:
        # 1. Execute attack
        attack_res = attack_dba_row_tamper(db_conn, snapshot_path=isolated_snapshot)
        assert attack_res["status"] == "success"
        target_seq = attack_res["target_sequence_id"]

        # Assert snapshot was created
        snap = load_snapshot(isolated_snapshot)
        assert snap is not None
        assert snap["scenario"] == "dba-row-tamper"

        # 2. Verify detection: hash_verifier must flag hash mismatch
        res = verify_chain(db_conn)
        assert res.is_valid is False
        assert len(res.mismatches) > 0
        mismatched_seqs = [m["sequence_id"] for m in res.mismatches]
        assert target_seq in mismatched_seqs

        # Assert status reflects active attack
        status = get_adversary_status(db_conn, snapshot_path=isolated_snapshot)
        assert status["attack_active"] is True
        assert status["chain_valid"] is False

    finally:
        # 3. Heal database back to pristine condition
        heal_res = heal_database(db_conn, snapshot_path=isolated_snapshot)
        assert heal_res["is_valid"] is True
        assert heal_res["mismatches"] == 0
        assert heal_res["gaps"] == 0
        assert heal_res["orphans"] == 0

        # Confirm post-heal verification
        post_verify = verify_chain(db_conn)
        assert post_verify.is_valid is True
        assert not os.path.exists(isolated_snapshot)


def test_recompute_and_hide_and_heal_cycle(db_conn, isolated_snapshot):
    """Test scenario 2: recompute-and-hide rewrites internal hashes but fails anchor validation."""
    try:
        # 1. Execute attack
        attack_res = attack_recompute_and_hide(db_conn, snapshot_path=isolated_snapshot)
        assert attack_res["status"] == "success"
        assert attack_res["recalculated_rows"] > 0

        # Assert internal chain walk is internally valid (attacker succeeded in faking hash chain)
        res = verify_chain(db_conn)
        assert res.is_valid is True

        # Assert status catches the discrepancy against external anchor store
        status = get_adversary_status(db_conn, snapshot_path=isolated_snapshot)
        assert status["attack_active"] is True
        if os.path.exists("anchor/2.json"):
            assert status["anchor_intact"] is False

    finally:
        # 2. Heal database back to pristine condition
        heal_res = heal_database(db_conn, snapshot_path=isolated_snapshot)
        assert heal_res["is_valid"] is True

        # Confirm post-heal verification and anchor match
        post_status = get_adversary_status(db_conn, snapshot_path=isolated_snapshot)
        assert post_status["attack_active"] is False
        assert post_status["chain_valid"] is True
        if os.path.exists("anchor/2.json"):
            assert post_status["anchor_intact"] is True


def test_checkpoint_forgery_and_heal_cycle(db_conn, isolated_snapshot):
    """Test scenario 3: checkpoint-forgery corrupts Ed25519 signature."""
    pub_key_path = "./keys/public_key.pem"
    if not os.path.exists(pub_key_path):
        pub_key_path = os.path.join(get_default_key_dir(), "public_key.pem")

    try:
        # 1. Execute attack
        attack_res = attack_checkpoint_forgery(db_conn, snapshot_path=isolated_snapshot)
        assert attack_res["status"] == "success"
        target_cp_id = attack_res["target_checkpoint_id"]

        # Query checkpoint and verify signature fails
        with db_conn.cursor() as cur:
            cur.execute("SELECT checkpoint_hash, signature FROM chain_checkpoints WHERE checkpoint_id = %s", (target_cp_id,))
            cp_hash, sig = cur.fetchone()

        if os.path.exists(pub_key_path):
            pub_key = load_public_key(pub_key_path)
            sig_valid = verify_signature(pub_key, cp_hash, bytes(sig))
            assert sig_valid is False

    finally:
        # 2. Heal database
        heal_res = heal_database(db_conn, snapshot_path=isolated_snapshot)
        assert heal_res["status"] == "healed"

        # Check that original signature is restored and passes
        with db_conn.cursor() as cur:
            cur.execute("SELECT checkpoint_hash, signature FROM chain_checkpoints WHERE checkpoint_id = %s", (target_cp_id,))
            cp_hash, restored_sig = cur.fetchone()

        if os.path.exists(pub_key_path):
            pub_key = load_public_key(pub_key_path)
            sig_valid = verify_signature(pub_key, cp_hash, bytes(restored_sig))
            assert sig_valid is True


def test_delete_audit_row_and_heal_cycle(db_conn, isolated_snapshot):
    """Test scenario 4: delete-audit-row triggers sequence gap and orphan detection."""
    try:
        # 1. Execute attack
        attack_res = attack_delete_audit_row(db_conn, snapshot_path=isolated_snapshot)
        assert attack_res["status"] == "success"
        deleted_seq = attack_res["deleted_sequence_id"]

        # 2. Verify detection: chain walk must flag gap or orphan
        res = verify_chain(db_conn)
        assert res.is_valid is False
        assert len(res.gaps) > 0 or len(res.orphans) > 0

    finally:
        # 3. Heal database back to pristine condition
        heal_res = heal_database(db_conn, snapshot_path=isolated_snapshot)
        assert heal_res["is_valid"] is True
        assert heal_res["gaps"] == 0
        assert heal_res["orphans"] == 0

        # Confirm post-heal verification
        post_verify = verify_chain(db_conn)
        assert post_verify.is_valid is True


def test_adversary_cli_subprocess():
    """Verify adversary CLI executes cleanly in a separate process."""
    # Test status command
    proc = subprocess.run(
        [sys.executable, "-m", "db.cli.adversary", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "Diagnosing Database and Verifier Integrity" in proc.stdout
