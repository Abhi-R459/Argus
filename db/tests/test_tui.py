"""Unit and integration tests for Argus Interactive TUI (TUI-CORE-001).

Tests CLI argument parsing (--tui and tui subcommands) across verifier.py,
adversary.py, and the master launcher db.cli.tui, plus clean exit workflows.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from db.cli.adversary import build_parser as build_adversary_parser
from db.cli.tui import build_parser as build_master_tui_parser
from db.cli.tui_adversary import run_adversary_tui
from db.cli.tui_verifier import run_verifier_tui
from db.cli.verifier import build_parser as build_verifier_parser


class TestTuiCliIntegration:
    """Test CLI argument parsing and dispatch for TUI triggers."""

    def test_verifier_cli_accepts_tui_flag(self):
        """Verify that argus-verifier parses --tui flag cleanly."""
        parser = build_verifier_parser()
        args = parser.parse_args(["--tui"])
        assert args.tui is True
        assert args.command is None

    def test_verifier_cli_accepts_tui_subcommand(self):
        """Verify that argus-verifier parses 'tui' as a valid subcommand."""
        parser = build_verifier_parser()
        args = parser.parse_args(["tui"])
        assert args.command == "tui"

    def test_verifier_cli_existing_flags_unaffected(self):
        """Verify that standard CLI commands like verify-chain remain unchanged."""
        parser = build_verifier_parser()
        args = parser.parse_args(["verify-chain", "--page-size", "250", "--parallel", "--workers", "4"])
        assert args.command == "verify-chain"
        assert args.page_size == 250
        assert args.parallel is True
        assert args.workers == 4
        assert getattr(args, "tui", False) is False

    def test_adversary_cli_accepts_tui_flag(self):
        """Verify that adversary CLI parses --tui flag cleanly."""
        parser = build_adversary_parser()
        args = parser.parse_args(["--tui"])
        assert args.tui is True
        assert args.command is None

    def test_adversary_cli_accepts_tui_subcommand(self):
        """Verify that adversary CLI parses 'tui' as a valid subcommand."""
        parser = build_adversary_parser()
        args = parser.parse_args(["tui"])
        assert args.command == "tui"

    def test_adversary_cli_existing_flags_unaffected(self):
        """Verify that existing adversary commands like attack remain unchanged."""
        parser = build_adversary_parser()
        args = parser.parse_args(["attack", "--scenario", "dba-row-tamper", "--sequence-id", "12"])
        assert args.command == "attack"
        assert args.scenario == "dba-row-tamper"
        assert args.sequence_id == 12
        assert getattr(args, "tui", False) is False

    def test_master_tui_parser_flags(self):
        """Verify that the master launcher parser handles --engine choices."""
        parser = build_master_tui_parser()
        args_verifier = parser.parse_args(["--engine", "verifier"])
        assert args_verifier.engine == "verifier"

        args_adversary = parser.parse_args(["--engine", "adversary"])
        assert args_adversary.engine == "adversary"

        args_default = parser.parse_args([])
        assert args_default.engine is None


class TestTuiExecutionFlow:
    """Test interactive menu loops with mocked user input."""

    @patch("db.cli.tui_verifier.Prompt.ask", return_value="0")
    @patch("db.cli.tui_verifier._get_chain_quick_stats", return_value={"success": True, "audit_count": 50, "cp_count": 2, "tail_seq": 50, "tail_hash": "a" * 64})
    def test_verifier_tui_immediate_exit(self, mock_stats, mock_prompt):
        """Verify that selecting option 0 exits the verifier TUI cleanly."""
        # Should execute the loop once and exit on '0'
        run_verifier_tui("dummy_url")
        assert mock_prompt.called

    @patch("db.cli.tui_adversary.Prompt.ask", return_value="0")
    @patch("os.path.exists", return_value=False)
    def test_adversary_tui_immediate_exit(self, mock_exists, mock_prompt):
        """Verify that selecting option 0 exits the adversary TUI cleanly."""
        run_adversary_tui("dummy_url")
        assert mock_prompt.called
