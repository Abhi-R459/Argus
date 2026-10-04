"""Unit and integration tests for Counterfactual 'What-If' Provenance Replay (NOVEL-011).

Tests:
1. `test_counterfactual_single_skip`: Skip one fraudulent salary increase, verify salary reverts to previous.
2. `test_counterfactual_multi_skip`: Skip multiple events (e.g. role change + salary change), verify cumulative blast radius.
3. `test_counterfactual_empty_skip_raises`: Empty skip list raises ValueError.
4. `test_counterfactual_missing_seq_id_raises`: Non-existent sequence IDs raise ValueError.
5. `test_counterfactual_no_modification_to_real_chain`: Read-only guarantee — no INSERT/UPDATE/DELETE executed.
6. `test_counterfactual_blast_radius_math`: Mathematical precision of annual delta and tenure-scaled cumulative overpayment.
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, call
import pytest

from db.cli.counterfactual import (
    BlastRadius,
    CounterfactualResult,
    SkippedEventInfo,
    counterfactual_replay,
)


def _create_mock_row(seq_id, action, table_name, old_val, new_val, created_at, actor_id=1, severity="INFO"):
    """Helper to generate mock database row matching DictCursor or dict interface."""
    return {
        "sequence_id": seq_id,
        "actor_user_id": actor_id,
        "action": action,
        "table_name": table_name,
        "row_id": 42,
        "old_value": old_val,
        "new_value": new_val,
        "severity": severity,
        "created_at": created_at,
    }


class TestCounterfactualReplayUnit:
    """Unit tests for in-memory virtual provenance replay."""

    def test_counterfactual_single_skip(self):
        """Simulate Alice (emp 42) receiving legitimate salary 80k at seq 10,

        fraudulent salary 250k at seq 71. Skipping seq 71 must revert salary to 80k.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        t1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        as_of = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Mock responses
        # 1. Validation query (seq 71 exists)
        mock_cur.fetchall.side_effect = [
            [(71,)],  # found_rows for seq_id validation
            [         # chronological audit_rows for emp 42
                _create_mock_row(
                    1, "INSERT", "employees", None,
                    {"id": 42, "full_name": "Alice Chen", "email": "alice@example.com", "role_id": 2, "department_id": 1, "is_active": True},
                    t1
                ),
                _create_mock_row(
                    10, "INSERT", "salary_history", None,
                    {"id": 100, "employee_id": 42, "amount": 80000.0, "effective_date": "2024-01-01"},
                    t1
                ),
                _create_mock_row(
                    71, "INSERT", "salary_history", None,
                    {"id": 105, "employee_id": 42, "amount": 250000.0, "effective_date": "2024-06-01"},
                    t2, severity="CRITICAL"
                ),
            ],
            [(2, "Analyst", 1)],       # roles cache
            [(1, "Finance")],          # departments cache
        ]

        result = counterfactual_replay(mock_conn, employee_id=42, skip_sequence_ids=[71], as_of=as_of)

        assert isinstance(result, CounterfactualResult)
        assert result.employee_id == 42
        assert result.actual_state["salary"] == 250000.0
        assert result.counterfactual_state["salary"] == 80000.0
        assert result.actual_state["full_name"] == "Alice Chen"
        assert result.counterfactual_state["full_name"] == "Alice Chen"
        assert result.blast_radius.salary_actual == 250000.0
        assert result.blast_radius.salary_counterfactual == 80000.0
        assert result.blast_radius.salary_overpaid_annual == 170000.0
        assert result.blast_radius.skipped_events_count == 1
        assert len(result.skipped_events) == 1
        assert result.skipped_events[0].sequence_id == 71

    def test_counterfactual_multi_skip(self):
        """Skip multiple fraudulent mutations: role promotion at seq 70 and salary bump at seq 71."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        t0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        as_of = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

        mock_cur.fetchall.side_effect = [
            [(70,), (71,)],  # found_rows for seq validation
            [
                _create_mock_row(1, "INSERT", "employees", None, {"id": 42, "role_id": 1, "department_id": 1}, t0),
                _create_mock_row(2, "INSERT", "salary_history", None, {"employee_id": 42, "amount": 60000.0}, t0),
                _create_mock_row(70, "UPDATE", "employees", {"role_id": 1}, {"role_id": 5}, t1),
                _create_mock_row(71, "INSERT", "salary_history", None, {"employee_id": 42, "amount": 160000.0}, t1),
            ],
            [(1, "Junior Dev", 1), (5, "VP Engineering", 1)],  # roles
            [(1, "Engineering")],                               # depts
        ]

        result = counterfactual_replay(mock_conn, employee_id=42, skip_sequence_ids=[70, 71], as_of=as_of)

        assert result.actual_state["role_title"] == "VP Engineering"
        assert result.actual_state["salary"] == 160000.0

        assert result.counterfactual_state["role_title"] == "Junior Dev"
        assert result.counterfactual_state["salary"] == 60000.0

        assert result.blast_radius.salary_overpaid_annual == 100000.0
        assert result.blast_radius.skipped_events_count == 2
        assert [e.sequence_id for e in result.skipped_events] == [70, 71]

    def test_counterfactual_empty_skip_raises(self):
        """Passing an empty skip list must raise ValueError."""
        mock_conn = MagicMock()
        with pytest.raises(ValueError, match="skip_sequence_ids must contain at least one sequence ID"):
            counterfactual_replay(mock_conn, employee_id=42, skip_sequence_ids=[])

    def test_counterfactual_missing_seq_id_raises(self):
        """Passing sequence IDs that do not exist in audit_log must raise ValueError."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Mock DB returning only 71 when [71, 999] was requested
        mock_cur.fetchall.return_value = [(71,)]

        with pytest.raises(ValueError, match="Sequence IDs not found in audit log: \\[999\\]"):
            counterfactual_replay(mock_conn, employee_id=42, skip_sequence_ids=[71, 999])

    def test_counterfactual_no_modification_to_real_chain(self):
        """Verify that counterfactual_replay issues zero INSERT, UPDATE, DELETE, or DDL statements."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            [(71,)],
            [
                _create_mock_row(1, "INSERT", "employees", None, {"id": 42}, datetime.now(timezone.utc)),
                _create_mock_row(71, "INSERT", "salary_history", None, {"amount": 200000.0}, datetime.now(timezone.utc)),
            ],
            [],
            [],
        ]

        counterfactual_replay(mock_conn, employee_id=42, skip_sequence_ids=[71])

        # Inspect all executed SQL statements
        executed_sqls = [call_args[0][0].strip().upper() for call_args in mock_cur.execute.call_args_list]
        for sql in executed_sqls:
            assert sql.startswith("SELECT"), f"Non-SELECT statement executed: {sql}"
            assert "INSERT" not in sql or "FROM" in sql
            assert "UPDATE" not in sql
            assert "DELETE" not in sql
            assert "DROP" not in sql
            assert "ALTER" not in sql

    def test_counterfactual_blast_radius_math(self):
        """Verify exact blast radius math with known elapsed months."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # 2 years exactly: 2024-01-01 to 2026-01-01 (731 days -> ~24.0 months)
        t_fraud = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        as_of = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        mock_cur.fetchall.side_effect = [
            [(50,)],
            [
                _create_mock_row(10, "INSERT", "salary_history", None, {"amount": 100000.0}, t_fraud),
                _create_mock_row(50, "INSERT", "salary_history", None, {"amount": 200000.0}, t_fraud),
            ],
            [],
            [],
        ]

        result = counterfactual_replay(mock_conn, employee_id=1, skip_sequence_ids=[50], as_of=as_of)
        br = result.blast_radius

        # Annual delta: 200k - 100k = 100k
        assert br.salary_overpaid_annual == 100000.0
        # Tenure ~ 24.0 months (2 years)
        assert 23.5 <= br.tenure_months <= 24.5
        # Cumulative overpayment ~ 100k * 2 years = ~200k
        assert 195000.0 <= br.salary_overpaid_cumulative <= 205000.0

    def test_to_dict_serialization(self):
        """Verify result serialization to dict is JSON safe."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        now = datetime.now(timezone.utc)
        mock_cur.fetchall.side_effect = [
            [(1,)],
            [_create_mock_row(1, "INSERT", "employees", None, {"id": 10}, now)],
            [],
            [],
        ]

        result = counterfactual_replay(mock_conn, employee_id=10, skip_sequence_ids=[1])
        res_dict = result.to_dict()

        json_str = json.dumps(res_dict)
        assert json_str is not None
        assert "blast_radius" in res_dict
        assert "skipped_events" in res_dict
