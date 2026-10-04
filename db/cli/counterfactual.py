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


# ---------------------------------------------------------------------------
# Database URL & Connection Helpers
# ---------------------------------------------------------------------------

def resolve_db_url(db_url: Optional[str] = None) -> str:
    """Resolve PostgreSQL connection string with robust environment fallbacks."""
    if db_url:
        url = db_url
    else:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass
        url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_MIGRATIONS")

    if not url and os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL_MIGRATIONS="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
                    elif line.startswith("DATABASE_URL=") and not url:
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    if not url:
        url = "postgresql://postgres:password@localhost:5433/argus"

    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

    return url


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
        ValueError: If skip_sequence_ids is empty or contains non-existent sequence IDs.
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
    actual_state: Optional[Dict[str, Any]] = None
    cf_state: Optional[Dict[str, Any]] = None
    skipped_events_list: List[SkippedEventInfo] = []
    applied_count = 0
    first_skipped_dt: Optional[datetime] = None

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

        # Apply to Actual State (always applies all operations)
        if table_name == "employees":
            if action == "INSERT":
                actual_state = dict(new_val)
                actual_state["salary"] = actual_state.get("salary", 0.0)
            elif action == "UPDATE":
                if actual_state is None:
                    actual_state = dict(new_val)
                else:
                    actual_state.update(new_val)
            elif action == "DELETE":
                actual_state = None
        elif table_name == "salary_history":
            amt = new_val.get("amount")
            if amt is not None:
                try:
                    parsed_sal = float(amt)
                    if actual_state is None:
                        actual_state = {"employee_id": employee_id, "salary": parsed_sal}
                    else:
                        actual_state["salary"] = parsed_sal
                except (ValueError, TypeError):
                    pass

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
            if table_name == "employees":
                if action == "INSERT":
                    cf_state = dict(new_val)
                    cf_state["salary"] = cf_state.get("salary", 0.0)
                elif action == "UPDATE":
                    if cf_state is None:
                        cf_state = dict(new_val)
                    else:
                        cf_state.update(new_val)
                elif action == "DELETE":
                    cf_state = None
            elif table_name == "salary_history":
                amt = new_val.get("amount")
                if amt is not None:
                    try:
                        parsed_sal = float(amt)
                        if cf_state is None:
                            cf_state = {"employee_id": employee_id, "salary": parsed_sal}
                        else:
                            cf_state["salary"] = parsed_sal
                    except (ValueError, TypeError):
                        pass

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

    _enrich_state(actual_state)
    _enrich_state(cf_state)

    # Step 6: Compute Blast Radius
    sal_actual = float(actual_state.get("salary", 0.0) if actual_state else 0.0)
    sal_cf = float(cf_state.get("salary", 0.0) if cf_state else 0.0)
    sal_delta_annual = max(0.0, sal_actual - sal_cf)

    # Calculate tenure from first skipped event to target_dt
    if first_skipped_dt:
        elapsed_seconds = max(0.0, (target_dt - first_skipped_dt).total_seconds())
        # Average days per month = 30.4375
        tenure_months = max(1.0, elapsed_seconds / (30.4375 * 86400.0))
    else:
        tenure_months = 1.0

    sal_overpaid_cumulative = round(sal_delta_annual * (tenure_months / 12.0), 2)

    blast_radius = BlastRadius(
        salary_actual=sal_actual,
        salary_counterfactual=sal_cf,
        salary_overpaid_annual=sal_delta_annual,
        salary_overpaid_cumulative=sal_overpaid_cumulative,
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
