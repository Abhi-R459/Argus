"""Ed25519 checkpoint signing and verification utility for the Argus verification engine.

Exposes the Signer interface, LocalFileSigner ([DEV/DEMO ONLY]), KmsSigner,
VaultTransitSigner, KeyRegistry, and backward-compatible helper functions.
"""

from __future__ import annotations

from typing import Any, Union
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from db.crypto.kms import (
    Signer,
    LocalFileSigner,
    KmsSigner,
    VaultTransitSigner,
    KeyRegistry,
)


def sign_checkpoint(
    private_key_or_signer: Union[Ed25519PrivateKey, Signer, bytes, str],
    checkpoint_hash: Union[str, bytes],
) -> bytes:
    """Signs a checkpoint hash string or bytes using an Ed25519 private key or Signer instance.

    Args:
        private_key_or_signer: The Ed25519 private key, Signer instance, or PEM bytes/str.
        checkpoint_hash: The checkpoint hash string or raw bytes to sign.

    Returns:
        bytes: The raw signature bytes.
    """
    if isinstance(checkpoint_hash, str):
        raw_data = checkpoint_hash.encode("utf-8")
    else:
        raw_data = checkpoint_hash

    # Handle PEM bytes or str for private key
    signer_obj = private_key_or_signer
    if isinstance(signer_obj, (bytes, str)):
        from cryptography.hazmat.primitives import serialization
        key_bytes = signer_obj.encode("utf-8") if isinstance(signer_obj, str) else signer_obj
        if b"BEGIN PRIVATE KEY" in key_bytes:
            signer_obj = serialization.load_pem_private_key(key_bytes, password=None)

    if hasattr(signer_obj, "sign") and not isinstance(
        signer_obj, Ed25519PrivateKey
    ):
        return signer_obj.sign(raw_data)
    return signer_obj.sign(raw_data)


# Backward compatibility alias
sign_checkpoint_hash = sign_checkpoint


def verify_signature(
    public_key_or_signer: Union[Ed25519PublicKey, Signer, KeyRegistry, Any],
    checkpoint_hash: str,
    signature: bytes,
    key_id: str | None = None,
    merkle_root: str | None = None,
) -> bool:
    """Verifies a signature for a checkpoint hash string using an Ed25519 public key,
    Signer instance, or KeyRegistry.

    If merkle_root is provided, first attempts verification against the bound payload
    f"{checkpoint_hash}:{merkle_root}". If that fails, falls back to raw checkpoint_hash
    for backward compatibility with pre-Merkle checkpoints.

    Args:
        public_key_or_signer: The Ed25519 public key, Signer, or KeyRegistry.
        checkpoint_hash (str): The checkpoint hash string that was signed.
        signature (bytes): The signature to verify.
        key_id (str | None): Optional key identifier for keyset resolution.
        merkle_root (str | None): Optional RFC 6962 Merkle root bound into the signature.

    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    def _verify_raw(data_bytes: bytes) -> bool:
        try:
            if isinstance(public_key_or_signer, KeyRegistry):
                return public_key_or_signer.verify_checkpoint(
                    data_bytes.decode("utf-8"), signature, key_id=key_id
                )
            if hasattr(public_key_or_signer, "verify") and not isinstance(
                public_key_or_signer, Ed25519PublicKey
            ):
                return public_key_or_signer.verify(data_bytes, signature)

            if isinstance(public_key_or_signer, (bytes, bytearray)):
                pub_key = Ed25519PublicKey.from_public_bytes(bytes(public_key_or_signer))
                pub_key.verify(signature, data_bytes)
                return True

            public_key_or_signer.verify(signature, data_bytes)
            return True
        except (InvalidSignature, Exception):
            return False

    # 1. If merkle_root provided, test bound payload first
    if merkle_root:
        bound_payload = f"{checkpoint_hash}:{merkle_root}".encode("utf-8")
        if _verify_raw(bound_payload):
            return True

    # 2. Fall back to classic checkpoint_hash payload
    raw_data = checkpoint_hash.encode("utf-8")
    return _verify_raw(raw_data)


__all__ = [
    "sign_checkpoint",
    "sign_checkpoint_hash",
    "verify_signature",
    "Signer",
    "LocalFileSigner",
    "KmsSigner",
    "VaultTransitSigner",
    "KeyRegistry",
]

