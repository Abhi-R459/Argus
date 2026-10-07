#!/usr/bin/env python3
"""Argus Counterfactual "What-If" Provenance Replay Engine (NOVEL-011-A).

This engine extends Argus's descriptive time-travel capability into a prescriptive
forensic simulation engine (Novelty 11).

Auditors can specify an employee ID and a set of fraudulent or anomalous audit log
sequence IDs to exclude. The engine executes a virtual, in-memory replay of the
historical delta stream without mutating or locking the underlying PostgreSQL database.

Outputs:
  - Actual historical/present state (with all mutations applied)
  - Counterfactual state (with designated sequence IDs skipped)
  - Quantified Blast Radius:
      * Annual salary discrepancy: (Actual Salary - Counterfactual Salary)
      * Cumulative overpayment over the elapsed fraud tenure
      * List of skipped events with contextual forensic attribution
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Union

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import psycopg2
import psycopg2.extras

logger = logging.getLogger("argus.counterfactual")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SkippedEventInfo:
    """Forensic metadata for an excluded historical audit event."""
    sequence_id: int
    actor_user_id: int
    action: str
    table_name: str
    created_at: str
    severity: str
    delta_summary: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None


@dataclass
class BlastRadius:
    """Quantified financial and operational impact of skipped transactions."""
    salary_actual: float
    salary_counterfactual: float
    salary_overpaid_annual: float
    salary_overpaid_cumulative: float
    tenure_months: float
    skipped_events_count: int
    skipped_sequence_ids: List[int]
    first_fraud_event_timestamp: Optional[str] = None
    as_of_timestamp: Optional[str] = None


@dataclass
class CounterfactualResult:
    """Complete simulation result comparing actual vs counterfactual state."""
    employee_id: int
    as_of: str
    skip_sequence_ids: List[int]
    actual_state: Optional[Dict[str, Any]]
    counterfactual_state: Optional[Dict[str, Any]]
    blast_radius: BlastRadius
    skipped_events: List[SkippedEventInfo]
    applied_events_count: int
    simulation_duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class _ReplayTrack:
    """Employee attributes plus the effective-dated salary rows at a replay point."""

    employee: Optional[Dict[str, Any]] = None
    salaries: Dict[int, Dict[str, Any]] = field(default_factory=dict)


def _effective_date(value: Any, fallback: datetime) -> date:
    """Parse a salary row's effective date, using its audit time for legacy payloads."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    return fallback.date()


def _salary_at(track: _ReplayTrack, as_of_date: date) -> float:
    """Return the salary row effective on as_of_date (0 when none is effective)."""
    eligible = [
        record for record in track.salaries.values()
        if record["effective_date"] <= as_of_date
    ]
    if not eligible:
        return 0.0
    current = max(eligible, key=lambda record: (record["effective_date"], record["salary_history_id"]))
    return float(current["amount"])


def _apply_event(
    track: _ReplayTrack,
    *,
    action: str,
    table_name: str,
    row_id: int,
    old_value: Dict[str, Any],
    new_value: Dict[str, Any],
    event_time: datetime,
) -> None:
    """Apply one audit mutation to a replay track."""
    if table_name == "employees":
        if action == "INSERT":
            track.employee = dict(new_value)
        elif action == "UPDATE":
            if track.employee is None:
                track.employee = dict(new_value)
            else:
                track.employee.update(new_value)
        elif action == "DELETE":
            track.employee = None
        return

    if table_name != "salary_history":
        return

    if action == "DELETE":
        salary_id = old_value.get("salary_history_id", row_id)
        try:
            track.salaries.pop(int(salary_id), None)
        except (TypeError, ValueError):
            pass
        return

    if action not in ("INSERT", "UPDATE") or "amount" not in new_value:
        return

    salary_id = new_value.get("salary_history_id", row_id)
    try:
        salary_id = int(salary_id)
        amount = float(new_value["amount"])
    except (TypeError, ValueError):
        return

    track.salaries[salary_id] = {
        "salary_history_id": salary_id,
        "amount": amount,
        "effective_date": _effective_date(new_value.get("effective_date"), event_time),
    }


def _salary_impact(
    actual: _ReplayTrack,
    counterfactual: _ReplayTrack,
    as_of_date: date,
) -> tuple[float, float, float]:
    """Return actual and counterfactual annual salary rates at a date."""
    salary_actual = _salary_at(actual, as_of_date)
    salary_counterfactual = _salary_at(counterfactual, as_of_date)
    annual_delta = max(0.0, salary_actual - salary_counterfactual)
    return salary_actual, salary_counterfactual, annual_delta


def _integrate_salary_impact(
    actual: _ReplayTrack,
    counterfactual: _ReplayTrack,
    start_date: date,
    end_date: date,
) -> tuple[float, int]:
    """Integrate positive annual salary differences over one audit-event interval."""
    if end_date <= start_date:
        return 0.0, 0

    boundaries = sorted({
        start_date,
        end_date,
        *(
            record["effective_date"]
            for track in (actual, counterfactual)
            for record in track.salaries.values()
            if start_date < record["effective_date"] < end_date
        ),
    })
    actual_schedule = sorted(
        (record["effective_date"], record["salary_history_id"], float(record["amount"]))
        for record in actual.salaries.values()
        if record["effective_date"] <= end_date
    )
    counterfactual_schedule = sorted(
        (record["effective_date"], record["salary_history_id"], float(record["amount"]))
        for record in counterfactual.salaries.values()
        if record["effective_date"] <= end_date
    )
    cumulative = 0.0
    positive_days = 0
    actual_index = 0
    counterfactual_index = 0
    actual_salary = 0.0
    counterfactual_salary = 0.0
    for start, end in zip(boundaries, boundaries[1:]):
        while actual_index < len(actual_schedule) and actual_schedule[actual_index][0] <= start:
            actual_salary = actual_schedule[actual_index][2]
            actual_index += 1
        while counterfactual_index < len(counterfactual_schedule) and counterfactual_schedule[counterfactual_index][0] <= start:
            counterfactual_salary = counterfactual_schedule[counterfactual_index][2]
            counterfactual_index += 1
        days = (end - start).days
        if days <= 0:
            continue
        interval_delta = max(0.0, actual_salary - counterfactual_salary)
        if interval_delta:
            cumulative += interval_delta * days / 365.2425
            positive_days += days

    return cumulative, positive_days


# ---------------------------------------------------------------------------
# Database URL & Connection Helpers
# ---------------------------------------------------------------------------

def resolve_db_url(db_url: Optional[str] = None) -> str:
    """Resolve a configured database URL without falling back to credentials."""
    try:
        from db.cli.db_url import resolve_db_url as resolve
    except ImportError:
        from db_url import resolve_db_url as resolve  # type: ignore[no-redef]
    return resolve(db_url)

def get_connection(db_url: Optional[str] = None) -> Any:
    """Create a psycopg2 connection."""
    url = resolve_db_url(db_url)
    return psycopg2.connect(url)


# ---------------------------------------------------------------------------
# Core Replay Engine
# ---------------------------------------------------------------------------

def _parse_payload(payload: Any) -> Dict[str, Any]:
    """Parse JSONB payload if returned as string."""
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, str):
        try:
            val = json.loads(payload)
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}
    return {}


def _summarize_delta(action: str, table_name: str, old_val: Dict[str, Any], new_val: Dict[str, Any]) -> str:
    """Generate concise human-readable delta explanation for skipped event."""
    if table_name == "salary_history":
        old_amt = old_val.get("amount")
        new_amt = new_val.get("amount")
        if old_amt is not None and new_amt is not None:
            return f"Salary modified: {old_amt} -> {new_amt}"
        elif new_amt is not None:
            return f"Salary inserted: {new_amt}"
        return f"{action} on salary_history"
    elif table_name == "employees":
        changes = []
        for k in ("role_id", "department_id", "is_active", "full_name"):
            if k in new_val and (k not in old_val or old_val[k] != new_val[k]):
                changes.append(f"{k}: {old_val.get(k)} -> {new_val.get(k)}")
        if changes:
            return f"Employee updated ({', '.join(changes)})"
        return f"{action} on employees"
    return f"{action} on {table_name}"


def counterfactual_replay(
    conn: Any,
    employee_id: int,
    skip_sequence_ids: Sequence[int],
    as_of: Optional[datetime] = None,
) -> CounterfactualResult:
    """Execute in-memory counterfactual replay for a target employee.

    Args:
        conn: psycopg2 connection or object providing .cursor().
        employee_id: Target employee identifier.
        skip_sequence_ids: List or set of sequence_ids to exclude from replay.
        as_of: Target point-in-time timestamp (defaults to current time in UTC).

    Returns:
        CounterfactualResult with actual state, counterfactual state, and blast radius.

    Raises:
        ValueError: If skip_sequence_ids is empty, non-existent, or outside the
            target employee's replay stream at ``as_of``.
    """
    start_time = time.perf_counter()

    if not skip_sequence_ids:
        raise ValueError("skip_sequence_ids must contain at least one sequence ID.")

    skip_set: Set[int] = {int(s) for s in skip_sequence_ids}

    # Normalize as_of timestamp
    if as_of is None:
        target_dt = datetime.now(timezone.utc)
    else:
        target_dt = as_of
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)

    # Use dict cursor if psycopg2
    cursor_kwargs = {}
    if hasattr(psycopg2, "extras") and hasattr(psycopg2.extras, "DictCursor"):
        cursor_kwargs["cursor_factory"] = psycopg2.extras.DictCursor

    with conn.cursor(**cursor_kwargs) as cur:
        # Step 1: Validate that all requested skip_sequence_ids exist in audit_log
        cur.execute(
            """
            SELECT sequence_id
            FROM audit_log
            WHERE sequence_id = ANY(%s);
            """,
            (list(skip_set),),
        )
        found_rows = cur.fetchall()
        found_ids = {int(r[0] if not isinstance(r, dict) else r["sequence_id"]) for r in found_rows}
        missing_ids = skip_set - found_ids
        if missing_ids:
            raise ValueError(f"Sequence IDs not found in audit log: {sorted(missing_ids)}")

        # Step 2: Fetch chronological mutation stream for the employee up to target_dt
        cur.execute(
            """
            SELECT
                sequence_id,
                actor_user_id,
                action,
                table_name,
                row_id,
                old_value,
                new_value,
                severity,
                created_at
            FROM audit_log
            WHERE (
                employee_id = %(emp_id)s
                OR (table_name = 'employees' AND row_id = %(emp_id)s)
                OR (table_name = 'salary_history' AND (new_value->>'employee_id')::INT = %(emp_id)s)
                OR (table_name = 'salary_history' AND (old_value->>'employee_id')::INT = %(emp_id)s)
            )
            AND created_at <= %(as_of)s
            ORDER BY sequence_id ASC;
            """,
            {"emp_id": employee_id, "as_of": target_dt},
        )
        audit_rows = cur.fetchall()

        # Step 3: Fetch organizational metadata (Role & Department lookup caches)
        cur.execute("SELECT role_id, title, department_id FROM roles;")
        roles_cache = {}
        for r in cur.fetchall():
            rid = r[0] if not isinstance(r, dict) else r["role_id"]
            title = r[1] if not isinstance(r, dict) else r["title"]
            dept_id = r[2] if not isinstance(r, dict) else r["department_id"]
            roles_cache[rid] = {"title": title, "department_id": dept_id}

        cur.execute("SELECT department_id, name FROM departments;")
        depts_cache = {}
        for r in cur.fetchall():
            did = r[0] if not isinstance(r, dict) else r["department_id"]
            name = r[1] if not isinstance(r, dict) else r["name"]
            depts_cache[did] = name

    # Step 4: Replay state in memory (both actual and counterfactual tracks)
    actual_track = _ReplayTrack()
    cf_track = _ReplayTrack()
    skipped_events_list: List[SkippedEventInfo] = []
    applied_count = 0
    first_skipped_dt: Optional[datetime] = None
    replayed_sequence_ids: Set[int] = set()
    previous_event_date: Optional[date] = None
    cumulative_impact = 0.0
    impact_days = 0

    for row in audit_rows:
        seq_id = int(row["sequence_id"])
        action = str(row["action"])
        table_name = str(row["table_name"])
        actor_id = int(row["actor_user_id"])
        created_at_val = row["created_at"]
        severity = str(row["severity"])

        old_val = _parse_payload(row["old_value"])
        new_val = _parse_payload(row["new_value"])

        created_at_dt = created_at_val
        if isinstance(created_at_dt, str):
            try:
                created_at_dt = datetime.fromisoformat(created_at_dt)
            except Exception:
                created_at_dt = target_dt
        if created_at_dt.tzinfo is None:
            created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)

        event_date = created_at_dt.date()
        if previous_event_date is not None:
            interval_amount, interval_days = _integrate_salary_impact(
                actual_track, cf_track, previous_event_date, event_date
            )
            cumulative_impact += interval_amount
            impact_days += interval_days

        replayed_sequence_ids.add(seq_id)
        _apply_event(
            actual_track,
            action=action,
            table_name=table_name,
            row_id=int(row["row_id"]),
            old_value=old_val,
            new_value=new_val,
            event_time=created_at_dt,
        )

        # Apply to Counterfactual State (skips seq_id if in skip_set)
        if seq_id in skip_set:
            if first_skipped_dt is None or created_at_dt < first_skipped_dt:
                first_skipped_dt = created_at_dt

            summary = _summarize_delta(action, table_name, old_val, new_val)
            skipped_events_list.append(
                SkippedEventInfo(
                    sequence_id=seq_id,
                    actor_user_id=actor_id,
                    action=action,
                    table_name=table_name,
                    created_at=created_at_dt.isoformat(),
                    severity=severity,
                    delta_summary=summary,
                    old_value=old_val or None,
                    new_value=new_val or None,
                )
            )
        else:
            applied_count += 1
            _apply_event(
                cf_track,
                action=action,
                table_name=table_name,
                row_id=int(row["row_id"]),
                old_value=old_val,
                new_value=new_val,
                event_time=created_at_dt,
            )
        previous_event_date = event_date

    unmatched_skip_ids = skip_set - replayed_sequence_ids
    if unmatched_skip_ids:
        raise ValueError(
            "Sequence IDs not in the target employee replay stream at the requested as_of: "
            f"{sorted(unmatched_skip_ids)}"
        )

    actual_state = actual_track.employee or ({"employee_id": employee_id} if actual_track.salaries else None)
    cf_state = cf_track.employee or ({"employee_id": employee_id} if cf_track.salaries else None)
    target_date = target_dt.date()
    if previous_event_date is not None:
        interval_amount, interval_days = _integrate_salary_impact(
            actual_track, cf_track, previous_event_date, target_date
        )
        cumulative_impact += interval_amount
        impact_days += interval_days
    salary_actual, salary_counterfactual, sal_delta_annual = _salary_impact(
        actual_track, cf_track, target_date
    )

    # Step 5: Enrich states with organizational titles
    def _enrich_state(s: Optional[Dict[str, Any]]) -> None:
        if s is None:
            return
        rid = s.get("role_id")
        if rid is not None and rid in roles_cache:
            s["role_title"] = roles_cache[rid]["title"]
            dept_id = roles_cache[rid].get("department_id")
            if dept_id and dept_id in depts_cache:
                s["department_name"] = depts_cache[dept_id]
        if "department_id" in s and s["department_id"] in depts_cache:
            s["department_name"] = depts_cache[s["department_id"]]
        if "salary" not in s or s["salary"] is None:
            s["salary"] = 0.0

    if actual_state is not None:
        actual_state["salary"] = salary_actual
    if cf_state is not None:
        cf_state["salary"] = salary_counterfactual
    _enrich_state(actual_state)
    _enrich_state(cf_state)

    # Step 6: Compute Blast Radius
    tenure_months = impact_days / 30.4375

    blast_radius = BlastRadius(
        salary_actual=salary_actual,
        salary_counterfactual=salary_counterfactual,
        salary_overpaid_annual=sal_delta_annual,
        salary_overpaid_cumulative=round(cumulative_impact, 2),
        tenure_months=round(tenure_months, 1),
        skipped_events_count=len(skipped_events_list),
        skipped_sequence_ids=sorted(list(skip_set)),
        first_fraud_event_timestamp=first_skipped_dt.isoformat() if first_skipped_dt else None,
        as_of_timestamp=target_dt.isoformat(),
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return CounterfactualResult(
        employee_id=employee_id,
        as_of=target_dt.isoformat(),
        skip_sequence_ids=sorted(list(skip_set)),
        actual_state=actual_state,
        counterfactual_state=cf_state,
        blast_radius=blast_radius,
        skipped_events=skipped_events_list,
        applied_events_count=applied_count,
        simulation_duration_ms=round(elapsed_ms, 2),
    )


# ---------------------------------------------------------------------------
# CLI Formatting & Entry Point
# ---------------------------------------------------------------------------

def _format_table(result: CounterfactualResult) -> str:
    """Format side-by-side comparison table."""
    lines = []
    lines.append("=" * 80)
    lines.append(f" ARGUS COUNTERFACTUAL PROVENANCE REPLAY (Employee #{result.employee_id})")
    lines.append("=" * 80)
    lines.append(f"As Of:             {result.as_of}")
    lines.append(f"Skipped Sequences: {result.skip_sequence_ids}")
    lines.append(f"Simulation Time:   {result.simulation_duration_ms:.2f} ms")
    lines.append("-" * 80)

    act = result.actual_state or {}
    cf = result.counterfactual_state or {}

    # All unique keys
    all_keys = ["full_name", "email", "role_title", "department_name", "is_active", "salary"]
    for k in sorted(set(list(act.keys()) + list(cf.keys()))):
        if k not in all_keys and not k.endswith("_encrypted") and k != "national_id_blind_index":
            all_keys.append(k)

    header = f"{'Field':<22} | {'Actual State':<25} | {'Counterfactual State':<25}"
    lines.append(header)
    lines.append("-" * len(header))

    for k in all_keys:
        v_act = act.get(k, "null")
        v_cf = cf.get(k, "null")

        if k == "salary":
            str_act = f"${float(v_act):,.2f}" if isinstance(v_act, (int, float)) else str(v_act)
            str_cf = f"${float(v_cf):,.2f}" if isinstance(v_cf, (int, float)) else str(v_cf)
            delta_str = f" (Δ -${float(v_act)-float(v_cf):,.2f})" if v_act != v_cf else ""
            str_cf += delta_str
        else:
            str_act = str(v_act)[:24]
            str_cf = str(v_cf)[:24]

        marker = " " if v_act == cf.get(k, "null") else "*"
        lines.append(f"{marker} {k:<20} | {str_act:<25} | {str_cf:<25}")

    lines.append("-" * 80)
    br = result.blast_radius
    lines.append(f"💥 BLAST RADIUS (Financial Impact):")
    lines.append(f"   * Annual Salary Delta:        ${br.salary_overpaid_annual:,.2f} / year")
    lines.append(f"   * Elapsed Fraud Tenure:       {br.tenure_months:.1f} months")
    lines.append(f"   * Cumulative Overpayment:     ${br.salary_overpaid_cumulative:,.2f}")
    lines.append(f"   * Excluded Audit Events:      {br.skipped_events_count} event(s)")
    lines.append("=" * 80)

    if result.skipped_events:
        lines.append("\nExcluded Audit Log Entries:")
        for ev in result.skipped_events:
            lines.append(f"  - Seq #{ev.sequence_id} [{ev.action} on {ev.table_name}] at {ev.created_at}: {ev.delta_summary}")

    return "\n".join(lines)


def main() -> int:
    """CLI entry point for counterfactual replay."""
    parser = argparse.ArgumentParser(
        description="Argus Counterfactual Replay Engine — Replay history skipping fraudulent mutations (NOVEL-011)."
    )
    parser.add_argument("--employee-id", type=int, required=True, help="Target employee ID")
    parser.add_argument(
        "--skip-seq-ids",
        type=str,
        required=True,
        help="Comma-separated sequence IDs to exclude (e.g. 71,72)",
    )
    parser.add_argument("--as-of", type=str, default=None, help="Target ISO timestamp (defaults to current time)")
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL connection string")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    try:
        skip_ids = [int(s.strip()) for s in args.skip_seq_ids.split(",") if s.strip()]
    except ValueError:
        sys.stderr.write("Error: --skip-seq-ids must be a comma-separated list of integers.\n")
        return 2

    as_of_dt = None
    if args.as_of:
        try:
            clean_ts = args.as_of.strip()
            if " " in clean_ts and "+" not in clean_ts:
                clean_ts = clean_ts.replace(" ", "+")
            as_of_dt = datetime.fromisoformat(clean_ts)
        except Exception as e:
            sys.stderr.write(f"Error parsing --as-of timestamp '{args.as_of}': {e}\n")
            return 2

    try:
        conn = get_connection(args.db_url)
        with conn:
            result = counterfactual_replay(conn, args.employee_id, skip_ids, as_of_dt)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(_format_table(result))
        return 0
    except Exception as e:
        sys.stderr.write(f"Counterfactual replay error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
