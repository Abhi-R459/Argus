"""Create one password-encrypted witness key vault on its operator's device."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import re

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption, Encoding, PrivateFormat, PublicFormat,
)

ROOT = Path(__file__).resolve().parents[1]


def initialize_vault(name: str, vault_root: Path, passphrase: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,100}", name):
        raise ValueError("Witness name must be 2-101 lowercase letters, numbers, dots, underscores or dashes.")
    if len(passphrase) < 14:
        raise ValueError("Use a witness passphrase of at least 14 characters.")
    resolved_root = vault_root.expanduser().resolve()
    if resolved_root == ROOT or ROOT in resolved_root.parents:
        raise ValueError("Keep witness keys outside the Argus checkout.")
    resolved_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        resolved_root.chmod(0o700)
    vault = resolved_root / name
    vault.mkdir(mode=0o700)

    key = Ed25519PrivateKey.generate()
    private_bytes = key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8,
        BestAvailableEncryption(passphrase.encode("utf-8")),
    )
    public_bytes = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    private_path = vault / "private.pem"
    descriptor = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(private_bytes)
    (vault / "public.pem").write_bytes(public_bytes)
    if os.name != "nt":
        vault.chmod(0o700)
        private_path.chmod(0o600)
    return vault


def main() -> int:
    parser = argparse.ArgumentParser(description="Create one independent witness key vault")
    parser.add_argument("--name", required=True, help="Registered witness name, e.g. auditor.one")
    parser.add_argument("--vault-root", type=Path, default=Path.home() / ".argus-witness")
    args = parser.parse_args()
    passphrase = getpass.getpass("New witness key passphrase (at least 14 characters): ")
    confirmation = getpass.getpass("Repeat witness key passphrase: ")
    if passphrase != confirmation:
        raise SystemExit("Passphrases do not match; no vault was created.")
    vault = initialize_vault(args.name, args.vault_root, passphrase)
    print(f"Witness vault created at {vault}.")
    print(f"Share only {vault / 'public.pem'} with the Argus deployment operator.")
    print("Keep private.pem, your passphrase, and the future witness-state.json under your own control.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
