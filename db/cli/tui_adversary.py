"""Argus Adversary Engine Interactive Terminal User Interface (TUI).

Provides an interactive console for Category 2 Red Team out-of-band administrative
attack simulations, forensic diagnostics, and deterministic self-healing recovery.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Dict, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

# Core adversary imports
from db.cli.adversary import (
    cmd_attack,
    cmd_heal,
    cmd_status,
    get_admin_connection,
    get_adversary_status,
)

console = Console()
DEFAULT_SNAPSHOT_PATH = ".argus_snapshot.json"
DEFAULT_ANCHOR_DIR = "anchor"


def _clear_screen() -> None:
    """Clear terminal screen cross-platform."""
    os.system("cls" if os.name == "nt" else "clear")


def _print_header() -> None:
    """Render the Adversary TUI header banner."""
    title = (
        "[bold red]ARGUS ADVERSARY ENGINE TUI[/bold red]\n"
        "[dim]Category 2: Out-of-Band Red Team Attack Simulation & Self-Healing Console[/dim]"
    )
    console.print(Panel(title, border_style="red", box=box.ROUNDED, expand=False))


def _pause() -> None:
    """Pause execution until the user presses Enter."""
    console.print()
    Prompt.ask("[dim]Press [bold]Enter[/bold] to return to menu...[/dim]", default="")


def _safe_connect(db_url: Optional[str] = None):
    """Attempt non-fatal PostgreSQL connection for status inspection."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    url = db_url or os.environ.get("DATABASE_URL_MIGRATIONS") or os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        import psycopg2
        return psycopg2.connect(url, connect_timeout=2)
    except Exception:
        return None


def _get_target_candidates(db_url: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve audit log sequence and checkpoint candidates for attack targeting."""
    try:
        conn = _safe_connect(db_url)
        if conn is None:
            return {"success": False, "error": "PostgreSQL database offline or unreachable"}
        with conn.cursor() as cur:
            cur.execute("SELECT MIN(sequence_id), MAX(sequence_id), COUNT(*) FROM audit_log;")
            min_seq, max_seq, total_rows = cur.fetchone()
            cur.execute("SELECT MIN(checkpoint_id), MAX(checkpoint_id), COUNT(*) FROM chain_checkpoints;")
            min_cp, max_cp, total_cps = cur.fetchone()
        conn.close()
        return {
            "success": True,
            "min_seq": min_seq or 1,
            "max_seq": max_seq or 1,
            "total_rows": total_rows or 0,
            "min_cp": min_cp or 1,
            "max_cp": max_cp or 1,
            "total_cps": total_cps or 0,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def action_status(db_url: Optional[str] = None) -> None:
    """Action: Inspect security posture and active attack diagnostics."""
    console.print("\n[bold cyan]Diagnosing System Integrity & Attack Posture...[/bold cyan]\n")
    args = argparse.Namespace(
        command="status",
        db_url=db_url,
        snapshot_path=DEFAULT_SNAPSHOT_PATH,
        anchor_dir=DEFAULT_ANCHOR_DIR,
        log_level="INFO",
    )
    cmd_status(args)
    _pause()


def action_attack_scenario(scenario: str, db_url: Optional[str] = None) -> None:
    """Action: Execute a specific out-of-band attack scenario."""
    scenario_names = {
        "dba-row-tamper": "DBA Row Tamper (Direct Historical Mutation)",
        "recompute-and-hide": "Recompute & Hide (Forward Hash Recalculation)",
        "checkpoint-forgery": "Checkpoint Forgery (Corrupt Ed25519 Signature)",
        "delete-audit-row": "Delete Audit Row (SQL Gap Injection)",
    }
    desc = scenario_names.get(scenario, scenario)

    # Active attack guard: enforce single active attack to preserve deterministic recovery
    if os.path.exists(DEFAULT_SNAPSHOT_PATH):
        console.print("[bold red][!] An attack simulation is already active![/bold red]")
        console.print("[yellow]Argus stages one attack scenario at a time to guarantee deterministic self-healing.[/yellow]\n")
        auto_heal = Confirm.ask("  Would you like to self-heal the active attack first before staging this one?", default=True)
        if auto_heal:
            action_heal(db_url)
            # Re-check if heal succeeded
            if os.path.exists(DEFAULT_SNAPSHOT_PATH):
                console.print("[dim]Active attack could not be cleared. Attack cancelled.[/dim]")
                _pause()
                return
        else:
            overwrite = Confirm.ask("  Overwrite existing snapshot anyway? (Warning: prior pre-attack baseline will be replaced)", default=False)
            if not overwrite:
                console.print("[dim]Attack cancelled.[/dim]")
                _pause()
                return

    # Check candidates from DB
    candidates = _get_target_candidates(db_url)
    target_seq = None
    target_cp = None

    if scenario in ("dba-row-tamper", "recompute-and-hide", "delete-audit-row"):
        if candidates.get("success") and candidates["total_rows"] > 0:
            suggested = max(1, candidates["max_seq"] - 2) if candidates["max_seq"] > 3 else candidates["min_seq"]
            console.print(f"  [dim]Audit log contains {candidates['total_rows']} entries (seq #{candidates['min_seq']} to #{candidates['max_seq']}).[/dim]")
            target_seq = IntPrompt.ask("  Target sequence ID in audit_log", default=suggested)
        else:
            target_seq = IntPrompt.ask("  Target sequence ID in audit_log", default=1)

    elif scenario == "checkpoint-forgery":
        if candidates.get("success") and candidates["total_cps"] > 0:
            suggested_cp = candidates["max_cp"]
            console.print(f"  [dim]Available checkpoints: #{candidates['min_cp']} to #{candidates['max_cp']}.[/dim]")
            target_cp = IntPrompt.ask("  Target checkpoint ID in chain_checkpoints", default=suggested_cp)
        else:
            target_cp = IntPrompt.ask("  Target checkpoint ID in chain_checkpoints", default=1)

    confirm = Confirm.ask(f"  [bold red]Proceed with out-of-band mutation?[/bold red]", default=True)
    if not confirm:
        console.print("[dim]Attack cancelled.[/dim]")
        _pause()
        return

    console.print()
    with console.status(f"[bold red]Simulating rogue DBA attack ({scenario})...[/bold red]", spinner="dots"):
        args = argparse.Namespace(
            command="attack",
            scenario=scenario,
            sequence_id=target_seq,
            checkpoint_id=target_cp,
            force=True,
            snapshot_path=DEFAULT_SNAPSHOT_PATH,
            anchor_dir=DEFAULT_ANCHOR_DIR,
            db_url=db_url,
            log_level="INFO",
        )
        exit_code = cmd_attack(args)

    _pause()


def action_heal(db_url: Optional[str] = None) -> None:
    """Action: Deterministic snapshot restoration (Self-Healing)."""
    console.print("\n[bold cyan]Argus Self-Healing Recovery System[/bold cyan]")
    console.print("  [dim]Restores pristine database records from snapshot and re-validates the chain.[/dim]\n")

    confirm = Confirm.ask("  Revert all administrative attacks and restore database integrity?", default=True)
    if not confirm:
        console.print("[dim]Heal cancelled.[/dim]")
        _pause()
        return

    console.print()
    with console.status("[bold cyan]Restoring snapshot and verifying chain continuity...[/bold cyan]", spinner="dots"):
        args = argparse.Namespace(
            command="heal",
            db_url=db_url,
            snapshot_path=DEFAULT_SNAPSHOT_PATH,
            anchor_dir=DEFAULT_ANCHOR_DIR,
            log_level="INFO",
        )
        exit_code = cmd_heal(args)

    _pause()


def run_adversary_tui(db_url: Optional[str] = None) -> None:
    """Main interactive loop for the Adversary Engine TUI."""
    while True:
        try:
            _clear_screen()
            _print_header()

            # Check system integrity and active attack state
            status_data: Dict[str, Any] = {}
            conn = _safe_connect(db_url)
            if conn:
                try:
                    status_data = get_adversary_status(conn)
                except Exception:
                    pass
                finally:
                    conn.close()

            attack_active = (
                os.path.exists(DEFAULT_SNAPSHOT_PATH)
                or status_data.get("attack_active", False)
            )

            if attack_active:
                scenario_name = status_data.get("active_scenario") or "Active Adversary Simulation"
                anomalies = []
                if not status_data.get("chain_valid", True):
                    anomalies.append("Hash Chain Broken")
                if not status_data.get("checkpoints_valid", True):
                    inv_count = len(status_data.get("invalid_checkpoints", []))
                    anomalies.append(f"{inv_count} Checkpoint Forgery Detected")
                if not status_data.get("anchor_intact", True):
                    anomalies.append("Anchor Discrepancy")

                anomaly_str = f" [{', '.join(anomalies)}]" if anomalies else ""
                console.print(
                    Panel(
                        f"[bold red][!] RED TEAM ATTACK / BREACH ACTIVE: {scenario_name}{anomaly_str}[/bold red]\n"
                        f"[yellow]Database has active simulated tampering. Run Option [6] to heal.[/yellow]",
                        border_style="red",
                        box=box.ROUNDED,
                    )
                )
            else:
                console.print("[bold green]System Status: Normal (Zero Tampering - All Checkpoints Signed & Valid)[/bold green]\n")

            menu = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            menu.add_column("Key", style="bold red", width=6)
            menu.add_column("Action", style="white")

            menu.add_row("[1]", "Inspect Security Posture & Active Attack Diagnostics")
            menu.add_row("[2]", "Execute Attack: [bold yellow]dba-row-tamper[/bold yellow] (Mutate Historical Row via SQL)")
            menu.add_row("[3]", "Execute Attack: [bold yellow]recompute-and-hide[/bold yellow] (Recalculate Forward Hashes)")
            menu.add_row("[4]", "Execute Attack: [bold yellow]checkpoint-forgery[/bold yellow] (Corrupt Checkpoint Signature)")
            menu.add_row("[5]", "Execute Attack: [bold yellow]delete-audit-row[/bold yellow] (Delete Historical Row via SQL)")
            menu.add_row("[6]", "[bold green]Self-Healing Recovery (Restore Pristine State & Auto-Repair Signatures)[/bold green]")
            menu.add_row("[0]", "[bold white]Exit / Return to Launcher[/bold white]")

            console.print(menu)
            console.print()

            choice = Prompt.ask("[bold red]Select an option[/bold red]", default="1")

            if choice == "1":
                action_status(db_url)
            elif choice == "2":
                action_attack_scenario("dba-row-tamper", db_url)
            elif choice == "3":
                action_attack_scenario("recompute-and-hide", db_url)
            elif choice == "4":
                action_attack_scenario("checkpoint-forgery", db_url)
            elif choice == "5":
                action_attack_scenario("delete-audit-row", db_url)
            elif choice == "6":
                action_heal(db_url)
            elif choice in ("0", "q", "exit"):
                break
            else:
                console.print("[bold red]Invalid option. Please enter 0-6.[/bold red]")
                time.sleep(1)

        except KeyboardInterrupt:
            console.print("\n[dim]Returning to menu...[/dim]")
            time.sleep(0.5)
        except Exception as exc:
            console.print(f"\n[bold red]Unexpected Error:[/bold red] {exc}")
            _pause()


def main() -> None:
    """CLI entry point for direct invocation."""
    db_url = os.environ.get("DATABASE_URL_MIGRATIONS") or os.environ.get("DATABASE_URL")
    run_adversary_tui(db_url)


if __name__ == "__main__":
    main()
