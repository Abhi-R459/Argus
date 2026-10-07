"""Shared witness storage and trust-key configuration for API and verifier."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote, unquote


def resolve_witness_store_path(
    anchor_file_path: str | os.PathLike[str] | None = None,
    configured_path: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve the one witness-note directory used by writers and readers.

    WITNESS_STORE_PATH is an explicit override. Otherwise notes live beside the
    local anchor file (or inside the configured anchor directory) in
    ``multi_witness/``.
    """
    path = configured_path or os.environ.get("WITNESS_STORE_PATH")
    if path:
        return Path(path)
    anchor = Path(anchor_file_path or os.environ.get("ANCHOR_FILE_PATH", "./anchor/chain_anchor.log"))
    anchor_dir = anchor.parent if anchor.suffix else anchor
    return anchor_dir / "multi_witness"


def load_public_keys(directory: str | os.PathLike[str] | None) -> dict[str, str]:
    """Load configured PEM public keys indexed by their URL-escaped key IDs."""
    if not directory:
        return {}
    result: dict[str, str] = {}
    for key_file in Path(directory).glob("*.pem"):
        if key_file.is_file():
            result[unquote(key_file.stem)] = key_file.read_text(encoding="utf-8")
    return result


def load_origin_public_key(
    key_id: str | None,
    directory: str | os.PathLike[str] | None,
) -> str | None:
    """Load a checkpoint verification key by key ID; never infer from private keys."""
    if not directory:
        return None
    key_dir = Path(directory)
    filename = "public_key.pem" if key_id in (None, "", "local:ed25519:v1") else f"{quote(key_id, safe='')}.pem"
    key_path = key_dir / filename
    return key_path.read_text(encoding="utf-8") if key_path.is_file() else None
