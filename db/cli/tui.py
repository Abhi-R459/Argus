"""Argus Master Security & Audit Console (TUI Launcher).

Unified interactive terminal entry point for the Verifier Engine (Category 1)
and Adversary Simulation Engine (Category 2).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from db.cli.tui_adversary import run_adversary_tui
from db.cli.tui_verifier import run_verifier_tui

console = Console()


def _clear_screen() -> None:
    """Clear terminal screen cross-platform."""
    os.system("cls" if os.name == "nt" else "clear")


def _print_master_banner() -> None:
    """Render the master Argus TUI launcher banner."""
    content = (
        "[bold cyan]ARGUS SECURITY & AUDIT CONSOLE[/bold cyan]\n"
        "[dim]PostgreSQL Tamper-Evident Ledger • Cryptographic Proofs • Red Team Simulation[/dim]\n\n"
        "Welcome! Choose an interactive terminal engine below to operate without CLI flags."
    )
    console.print(Panel(content, border_style="blue", box=box.ROUNDED, expand=False))


def run_master_tui(db_url: Optional[str] = None) -> None:
    """Run the master interactive TUI selection loop."""
    while True:
        try:
            _clear_screen()
            _print_master_banner()
            console.print()

            table = Table(box=box.ROUNDED, border_style="blue")
            table.add_column("Key", style="bold white", width=6)
            table.add_column("Engine", style="bold cyan", width=34)
            table.add_column("Domain / Capabilities", style="dim white")

            table.add_row(
                "[1]",
                "Verifier Engine (The Shield)",
                "Cryptographic auditing, hash chains, Ed25519 signing, external anchoring, backups, air-gapped evidence verifier",
            )
            table.add_row(
                "[2]",
                "Adversary Engine (The Sword)",
                "Out-of-band rogue DBA attacks (row tamper, forward hash recompute, signature forgery, row deletion), diagnostics, and self-healing",
            )
            table.add_row(
                "[0]",
                "[bold red]Exit Console[/bold red]",
                "Close interactive terminal and return to shell",
            )

            console.print(table)
            console.print()

            choice = Prompt.ask("[bold blue]Select Engine to Launch[/bold blue]", choices=["1", "2", "0", "q", "exit"], default="1")

            if choice == "1":
                run_verifier_tui(db_url)
            elif choice == "2":
                run_adversary_tui(db_url)
            elif choice in ("0", "q", "exit"):
                console.print("\n[bold green]Goodbye![/bold green] Exiting Argus Console.\n")
                break

        except KeyboardInterrupt:
            console.print("\n\n[bold green]Exiting Argus Console.[/bold green]\n")
            break
        except Exception as exc:
            console.print(f"\n[bold red]Error in launcher:[/bold red] {exc}")
            Prompt.ask("[dim]Press Enter to continue...[/dim]", default="")


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser for the master TUI."""
    parser = argparse.ArgumentParser(
        prog="python -m db.cli.tui",
        description="Argus Master Security & Audit Console (Interactive TUI).",
    )
    parser.add_argument(
        "--engine",
        choices=["verifier", "adversary"],
        default=None,
        help="Directly launch specific engine TUI without showing master menu.",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL database URL (defaults to DATABASE_URL_MIGRATIONS / DATABASE_URL).",
    )
    return parser


def main() -> None:
    """CLI entry point for master TUI."""
    parser = build_parser()
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get("DATABASE_URL_MIGRATIONS") or os.environ.get("DATABASE_URL")

    if args.engine == "verifier":
        run_verifier_tui(db_url)
    elif args.engine == "adversary":
        run_adversary_tui(db_url)
    else:
        run_master_tui(db_url)


if __name__ == "__main__":
    main()
