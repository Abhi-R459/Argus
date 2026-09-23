"""Argus Verifier Engine Interactive Terminal User Interface (TUI).

Provides an interactive console for all Category 1 auditing, cryptographic
verification, checkpoint management, digital signing, and external anchoring.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from typing import Any, Dict, List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

# Core verifier imports
from db.cli.verifier import (
    _cmd_anchor,
    _cmd_auto_checkpoint,
    _cmd_backup,
    _cmd_create_checkpoint,
    _cmd_sign_checkpoint,
    _cmd_verify_chain,
    get_connection,
)

console = Console()


def _clear_screen() -> None:
    """Clear terminal screen cross-platform."""
    os.system("cls" if os.name == "nt" else "clear")


def _print_header() -> None:
    """Render the Verifier TUI header banner."""
    title = (
        "[bold cyan]ARGUS VERIFIER & AUDIT TUI[/bold cyan]\n"
        "[dim]Category 1: Cryptographic Verification, Checkpointing & Anchoring Console[/dim]"
    )
    console.print(Panel(title, border_style="cyan", box=box.ROUNDED, expand=False))


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
    url = db_url or os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_MIGRATIONS")
    if not url:
        return None
    try:
        import psycopg2
        return psycopg2.connect(url, connect_timeout=2)
    except Exception:
        return None


def _get_chain_quick_stats(db_url: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve quick statistics from chain_state and audit_log."""
    try:
        conn = _safe_connect(db_url)
        if conn is None:
            return {"success": False, "error": "PostgreSQL database offline or unreachable"}
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM audit_log;")
            audit_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chain_checkpoints;")
            cp_count = cur.fetchone()[0]
            cur.execute("SELECT tail_sequence_id, tail_hash FROM chain_state WHERE id = 1;")
            row = cur.fetchone()
            tail_seq, tail_hash = row if row else (0, "0" * 64)
        conn.close()
        return {
            "success": True,
            "audit_count": audit_count,
            "cp_count": cp_count,
            "tail_seq": tail_seq,
            "tail_hash": tail_hash,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def action_chain_status(db_url: Optional[str] = None) -> None:
    """Action: Display live database chain status."""
    console.print("\n[bold cyan]Querying Live Chain State...[/bold cyan]")
    stats = _get_chain_quick_stats(db_url)
    if not stats["success"]:
        console.print(Panel(f"[bold red]Database Connection Failed:[/bold red] {stats['error']}", border_style="red"))
        _pause()
        return

    table = Table(title="Argus Ledger Status", box=box.ROUNDED, border_style="cyan")
    table.add_column("Metric", style="bold white", width=26)
    table.add_column("Current Value", style="green", width=48)

    table.add_row("Total Audit Log Records", f"{stats['audit_count']:,}")
    table.add_row("Total Signed Checkpoints", f"{stats['cp_count']:,}")
    table.add_row("Latest Sequence ID", f"#{stats['tail_seq']:,}")
    tail_h = stats["tail_hash"]
    display_hash = f"{tail_h[:16]}...{tail_h[-16:]}" if len(tail_h) > 32 else tail_h
    table.add_row("Current Tail Hash", display_hash)
    table.add_row("Database Status", "[bold green]ONLINE (Ready)[/bold green]")

    console.print(table)
    _pause()


def action_verify_sequential(db_url: Optional[str] = None) -> None:
    """Action: Run sequential keyset verification."""
    console.print("\n[bold cyan]Sequential Chain Verification Configuration[/bold cyan]")
    page_size = IntPrompt.ask("  Batch page size for keyset pagination", default=500)
    start_seq = IntPrompt.ask("  Starting sequence ID", default=0)

    console.print()
    with console.status("[bold cyan]Walking hash chain sequentially and verifying SHA-256 links...[/bold cyan]", spinner="dots"):
        t0 = time.time()
        args = argparse.Namespace(
            command="verify-chain",
            db_url=db_url,
            dry_run=False,
            start_seq=start_seq,
            page_size=page_size,
            parallel=False,
            sequential=True,
            workers=0,
            log_level="INFO",
        )
        exit_code = _cmd_verify_chain(args)
        elapsed = time.time() - t0

    console.print()
    if exit_code == 0:
        console.print(
            Panel(
                f"[bold green][PASS] INTEGRITY VERIFIED (SUCCESS)[/bold green]\n"
                f"Elapsed Time: {elapsed:.2f}s | Mode: Sequential | Page Size: {page_size}",
                border_style="green",
                box=box.ROUNDED,
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red][FAIL] CRYPTOGRAPHIC TAMPERING DETECTED[/bold red]\n"
                f"The hash chain contains broken links or unauthorized mutations.",
                border_style="red",
                box=box.ROUNDED,
            )
        )
    _pause()


def action_verify_parallel(db_url: Optional[str] = None) -> None:
    """Action: Run parallel multi-process verification."""
    console.print("\n[bold cyan]Parallel Chain Verification Configuration[/bold cyan]")
    default_workers = min(os.cpu_count() or 4, 8)
    workers = IntPrompt.ask("  Worker process count", default=default_workers)
    page_size = IntPrompt.ask("  Batch page size per segment", default=500)

    console.print()
    with console.status(f"[bold cyan]Verifying checkpoint-bounded segments with {workers} worker processes...[/bold cyan]", spinner="dots"):
        t0 = time.time()
        args = argparse.Namespace(
            command="verify-chain",
            db_url=db_url,
            dry_run=False,
            start_seq=0,
            page_size=page_size,
            parallel=True,
            sequential=False,
            workers=workers,
            log_level="INFO",
        )
        exit_code = _cmd_verify_chain(args)
        elapsed = time.time() - t0

    console.print()
    if exit_code == 0:
        console.print(
            Panel(
                f"[bold green][PASS] PARALLEL VERIFICATION COMPLETE (SUCCESS)[/bold green]\n"
                f"Elapsed Time: {elapsed:.2f}s | Workers: {workers} | Status: All segments verified",
                border_style="green",
                box=box.ROUNDED,
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red][FAIL] TAMPERING DETECTED IN SEGMENT[/bold red]\n"
                f"Cross-segment boundary or internal segment hash verification failed.",
                border_style="red",
                box=box.ROUNDED,
            )
        )
    _pause()


def action_create_checkpoints(db_url: Optional[str] = None) -> None:
    """Action: Generate periodic checkpoints."""
    console.print("\n[bold cyan]Create Checkpoints[/bold cyan]")
    interval = IntPrompt.ask("  Checkpoint interval (every N audit entries)", default=25)
    page_size = IntPrompt.ask("  Batch page size", default=500)

    with console.status(f"[bold cyan]Scanning chain and creating checkpoints every {interval} entries...[/bold cyan]", spinner="dots"):
        args = argparse.Namespace(
            command="create-checkpoint",
            db_url=db_url,
            checkpoint_interval=interval,
            page_size=page_size,
            log_level="INFO",
        )
        exit_code = _cmd_create_checkpoint(args)

    if exit_code == 0:
        console.print("[bold green][OK] Checkpoints created successfully.[/bold green]")
    else:
        console.print("[bold red][!] Checkpoint generation failed or no new entries found.[/bold red]")
    _pause()


def action_sign_checkpoint(db_url: Optional[str] = None) -> None:
    """Action: Digitally sign a stored checkpoint with Ed25519."""
    console.print("\n[bold cyan]Sign Checkpoint (Ed25519)[/bold cyan]")
    
    # Try to find latest checkpoint ID as default
    default_id = 1
    try:
        conn = get_connection(db_url)
        with conn.cursor() as cur:
            cur.execute("SELECT checkpoint_id, sequence_id FROM chain_checkpoints ORDER BY checkpoint_id DESC LIMIT 1;")
            row = cur.fetchone()
            if row:
                default_id = row[0]
                console.print(f"  [dim]Latest available checkpoint is #[bold]{default_id}[/bold] (at seq #{row[1]})[/dim]")
        conn.close()
    except Exception:
        pass

    checkpoint_id = IntPrompt.ask("  Target Checkpoint ID to sign", default=default_id)
    key_path_input = Prompt.ask("  Path to Ed25519 private key PEM [default: ~/.argus/signing_key.pem]", default="")
    key_path = key_path_input if key_path_input.strip() else None

    with console.status(f"[bold cyan]Signing checkpoint #{checkpoint_id} with Ed25519 private key...[/bold cyan]", spinner="dots"):
        args = argparse.Namespace(
            command="sign-checkpoint",
            db_url=db_url,
            checkpoint_id=checkpoint_id,
            key_path=key_path,
            key_id="local:ed25519:v1",
            log_level="INFO",
        )
        exit_code = _cmd_sign_checkpoint(args)

    if exit_code == 0:
        console.print(f"[bold green][OK] Checkpoint #{checkpoint_id} signed successfully.[/bold green]")
    else:
        console.print(f"[bold red][!] Signing failed for checkpoint #{checkpoint_id}.[/bold red]")
    _pause()


def action_anchor_checkpoint(db_url: Optional[str] = None) -> None:
    """Action: Publish a signed checkpoint to an external anchor store."""
    console.print("\n[bold cyan]Anchor Checkpoint to External Store[/bold cyan]")
    checkpoint_id = IntPrompt.ask("  Target Checkpoint ID to anchor", default=1)
    anchor_type = Prompt.ask("  Anchor store type", choices=["local", "github"], default="local")
    
    path = "./anchors"
    repo = None
    token = None
    branch = "main"

    if anchor_type == "local":
        path = Prompt.ask("  Local anchor directory path", default="./anchors")
    else:
        repo = Prompt.ask("  GitHub repository (owner/repo)")
        token = Prompt.ask("  GitHub personal access token (leave empty for GITHUB_TOKEN env)", default="")
        branch = Prompt.ask("  Branch", default="main")

    verify_sig = Confirm.ask("  Verify signature before anchoring?", default=True)

    with console.status(f"[bold cyan]Pushing checkpoint #{checkpoint_id} to {anchor_type} store...[/bold cyan]", spinner="dots"):
        args = argparse.Namespace(
            command="anchor",
            db_url=db_url,
            checkpoint_id=checkpoint_id,
            type=anchor_type,
            path=path,
            repo=repo,
            token=token or None,
            branch=branch,
            path_prefix="anchors",
            verify_sig=verify_sig,
            public_key_path=None,
            log_level="INFO",
        )
        exit_code = _cmd_anchor(args)

    if exit_code == 0:
        console.print(f"[bold green][OK] Checkpoint #{checkpoint_id} successfully anchored to {anchor_type}.[/bold green]")
    else:
        console.print(f"[bold red][!] Anchoring failed for checkpoint #{checkpoint_id}.[/bold red]")
    _pause()


def action_auto_checkpoint(db_url: Optional[str] = None) -> None:
    """Action: Dual-trigger checkpoint daemon or single evaluation tick."""
    console.print("\n[bold cyan]Dual-Trigger Auto-Checkpoint Manager[/bold cyan]")
    console.print("  [dim]Bounds undetectable tampering window T (by row threshold or elapsed time).[/dim]")
    
    run_once = Confirm.ask("  Run single evaluation tick and exit? (No = start continuous daemon)", default=True)
    max_entries = IntPrompt.ask("  Row threshold (uncheckpointed entries)", default=25)
    max_seconds = float(Prompt.ask("  Maximum elapsed seconds window", default="60.0"))
    sign = Confirm.ask("  Automatically sign created checkpoints?", default=True)
    anchor = Confirm.ask("  Automatically push created checkpoints to anchor store?", default=True)

    args = argparse.Namespace(
        command="auto-checkpoint",
        db_url=db_url,
        max_entries=max_entries,
        max_seconds=max_seconds,
        poll_interval=5.0,
        run_once=run_once,
        sign=sign,
        key_path=None,
        anchor=anchor,
        anchor_type="local",
        anchor_path="./anchors",
        key_id="local:ed25519:v1",
        log_level="INFO",
    )
    if run_once:
        with console.status("[bold cyan]Evaluating auto-checkpoint trigger condition...[/bold cyan]", spinner="dots"):
            exit_code = _cmd_auto_checkpoint(args)
    else:
        console.print("[bold yellow]Starting continuous daemon. Press Ctrl+C to terminate.[/bold yellow]\n")
        exit_code = _cmd_auto_checkpoint(args)

    _pause()


def action_backup(db_url: Optional[str] = None) -> None:
    """Action: Database backup dump with SHA-256 streaming hash or verification."""
    console.print("\n[bold cyan]Cryptographic Backup & Integrity Verification[/bold cyan]")
    choice = Prompt.ask(
        "  Select backup operation",
        choices=["1", "2"],
        default="1",
    )
    if choice == "1":
        output = Prompt.ask("  Output SQL dump path", default="argus_backup.sql")
        manifest = Prompt.ask("  Export off-host verification manifest path", default="argus_backup_manifest.json")
        cp_id_str = Prompt.ask("  Associate with Checkpoint ID (optional, hit Enter to skip)", default="")
        cp_id = int(cp_id_str) if cp_id_str.isdigit() else None

        with console.status("[bold cyan]Executing pg_dump and computing streaming SHA-256 hash...[/bold cyan]", spinner="dots"):
            args = argparse.Namespace(
                command="backup",
                backup_action="dump",
                db_url=db_url,
                output=output,
                checkpoint_id=cp_id,
                manifest_path=manifest or None,
                log_level="INFO",
            )
            exit_code = _cmd_backup(args)
        if exit_code == 0:
            console.print(f"[bold green][OK] Backup dumped to {output} and recorded in database.[/bold green]")
        else:
            console.print("[bold red][!] Backup dump failed.[/bold red]")
    else:
        file_path = Prompt.ask("  Path to backup SQL file to verify", default="argus_backup.sql")
        manifest = Prompt.ask("  Path to off-host manifest JSON", default="argus_backup_manifest.json")
        with console.status("[bold cyan]Re-hashing backup file and verifying against manifest...[/bold cyan]", spinner="dots"):
            args = argparse.Namespace(
                command="backup",
                backup_action="verify",
                db_url=db_url,
                backup_id=None,
                file=file_path,
                manifest_path=manifest,
                log_level="INFO",
            )
            exit_code = _cmd_backup(args)
        if exit_code == 0:
            console.print("[bold green][PASS] Backup hash matches off-host manifest perfectly.[/bold green]")
        else:
            console.print("[bold red][FAIL] Backup file integrity check failed (hash mismatch).[/bold red]")
    _pause()


def action_standalone_verifier() -> None:
    """Action: Air-gapped zero-dependency verifier for .arguspack bundles."""
    console.print("\n[bold cyan]Air-Gapped Standalone Verifier (.arguspack)[/bold cyan]")
    console.print("  [dim]Uses zero-dependency RFC 8032 Edwards25519 curve math to verify exported evidence.[/dim]")

    # Look for candidate bundles
    candidates = glob.glob("*.arguspack") + glob.glob("*.zip") + glob.glob("export/*.arguspack") + glob.glob("export/*.zip")
    default_bundle = candidates[0] if candidates else "export_bundle.arguspack"
    
    bundle_path = Prompt.ask("  Path to .arguspack bundle or directory", default=default_bundle)

    try:
        from db.cli.verify_standalone import verify_bundle
    except ImportError:
        console.print("[bold red]verify_standalone module could not be imported.[/bold red]")
        _pause()
        return

    with console.status(f"[bold cyan]Verifying RFC 8032 digital signature and SHA-256 chain in {bundle_path}...[/bold cyan]", spinner="dots"):
        t0 = time.time()
        exit_code, report = verify_bundle(bundle_path)
        elapsed = time.time() - t0

    console.print()
    table = Table(title=f"Verification Report: {os.path.basename(bundle_path)}", box=box.ROUNDED, border_style="cyan")
    table.add_column("Property", style="bold white", width=24)
    table.add_column("Result", style="green", width=48)

    sig_str = "[bold green]VALID (Ed25519 Authenticated)[/bold green]" if report.get("signature_valid") else "[bold red]INVALID / MISSING[/bold red]"
    table.add_row("Digital Signature", sig_str)
    table.add_row("Events Audited", f"{report.get('total_events', 0):,}")
    table.add_row("Hash Mismatches", str(len(report.get("mismatches", []))))
    table.add_row("Sequence Gaps", str(len(report.get("gaps", []))))
    table.add_row("Orphan Breaks", str(len(report.get("orphans", []))))
    table.add_row("Elapsed Time", f"{elapsed:.3f}s")

    console.print(table)
    if exit_code == 0:
        console.print(Panel("[bold green][PASS] BUNDLE INTEGRITY 100% VERIFIED[/bold green]", border_style="green"))
    else:
        console.print(Panel(f"[bold red][FAIL] VERIFICATION FAILED ({report.get('status')})[/bold red]", border_style="red"))
    _pause()


def run_verifier_tui(db_url: Optional[str] = None) -> None:
    """Main interactive loop for the Verifier Engine TUI."""
    while True:
        try:
            _clear_screen()
            _print_header()

            # Display quick stats bar
            stats = _get_chain_quick_stats(db_url)
            if stats["success"]:
                tail = stats["tail_hash"]
                short_tail = f"{tail[:8]}...{tail[-8:]}" if len(tail) > 16 else tail
                console.print(
                    f"  [dim]Connected | Audit Records: [bold white]{stats['audit_count']:,}[/bold white] | "
                    f"Checkpoints: [bold white]{stats['cp_count']:,}[/bold white] | "
                    f"Tail: [bold cyan]#{stats['tail_seq']} ({short_tail})[/bold cyan][/dim]\n"
                )
            else:
                console.print(f"  [bold yellow][!] DB Warning:[/bold yellow] [dim]{stats['error']}[/dim]\n")

            menu = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            menu.add_column("Key", style="bold cyan", width=6)
            menu.add_column("Action", style="white")

            menu.add_row("[1]", "Verify Hash Chain (Sequential Keyset Walk)")
            menu.add_row("[2]", "Verify Hash Chain in Parallel (Multi-Core Process Pool)")
            menu.add_row("[3]", "Create Checkpoints (Regular Row Intervals)")
            menu.add_row("[4]", "Sign Checkpoint with Ed25519 Private Key")
            menu.add_row("[5]", "Anchor Checkpoint to External Store (Local / GitHub)")
            menu.add_row("[6]", "Run Dual-Trigger Auto-Checkpoint Daemon / Single Tick")
            menu.add_row("[7]", "Cryptographic Database Backup & Verification (pg_dump + SHA-256)")
            menu.add_row("[8]", "Air-Gapped Standalone Verifier (.arguspack Evidence Bundle)")
            menu.add_row("[9]", "Live Chain Status & Tail Hash Inspector")
            menu.add_row("[0]", "[bold red]Exit / Return to Launcher[/bold red]")

            console.print(menu)
            console.print()

            choice = Prompt.ask("[bold cyan]Select an option[/bold cyan]", default="1")

            if choice == "1":
                action_verify_sequential(db_url)
            elif choice == "2":
                action_verify_parallel(db_url)
            elif choice == "3":
                action_create_checkpoints(db_url)
            elif choice == "4":
                action_sign_checkpoint(db_url)
            elif choice == "5":
                action_anchor_checkpoint(db_url)
            elif choice == "6":
                action_auto_checkpoint(db_url)
            elif choice == "7":
                action_backup(db_url)
            elif choice == "8":
                action_standalone_verifier()
            elif choice == "9":
                action_chain_status(db_url)
            elif choice in ("0", "q", "exit"):
                break
            else:
                console.print("[bold red]Invalid option. Please enter 0-9.[/bold red]")
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
    run_verifier_tui(db_url)


if __name__ == "__main__":
    main()
