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
    private_key_or_signer: Union[Ed25519PrivateKey, Signer],
    checkpoint_hash: str,
) -> bytes:
    """Signs a checkpoint hash string using an Ed25519 private key or Signer instance.

    Args:
        private_key_or_signer: The Ed25519 private key or Signer instance to use.
        checkpoint_hash (str): The checkpoint hash string to sign.

    Returns:
        bytes: The raw signature bytes.
    """
    raw_data = checkpoint_hash.encode("utf-8")
    if hasattr(private_key_or_signer, "sign") and not isinstance(
        private_key_or_signer, Ed25519PrivateKey
    ):
        return private_key_or_signer.sign(raw_data)
    return private_key_or_signer.sign(raw_data)


# Backward compatibility alias
sign_checkpoint_hash = sign_checkpoint


def verify_signature(
    public_key_or_signer: Union[Ed25519PublicKey, Signer, KeyRegistry, Any],
    checkpoint_hash: str,
    signature: bytes,
    key_id: str | None = None,
) -> bool:
    """Verifies a signature for a checkpoint hash string using an Ed25519 public key,
    Signer instance, or KeyRegistry.

    Args:
        public_key_or_signer: The Ed25519 public key, Signer, or KeyRegistry.
        checkpoint_hash (str): The checkpoint hash string that was signed.
        signature (bytes): The signature to verify.
        key_id (str | None): Optional key identifier for keyset resolution.

    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    try:
        raw_data = checkpoint_hash.encode("utf-8")
        if isinstance(public_key_or_signer, KeyRegistry):
            return public_key_or_signer.verify_checkpoint(
                checkpoint_hash, signature, key_id=key_id
            )
        if hasattr(public_key_or_signer, "verify") and not isinstance(
            public_key_or_signer, Ed25519PublicKey
        ):
            return public_key_or_signer.verify(raw_data, signature)

        if isinstance(public_key_or_signer, (bytes, bytearray)):
            pub_key = Ed25519PublicKey.from_public_bytes(bytes(public_key_or_signer))
            pub_key.verify(signature, raw_data)
            return True

        public_key_or_signer.verify(signature, raw_data)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


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

