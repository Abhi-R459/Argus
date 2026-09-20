"""Argus Cryptographic Signer Abstraction & Key Management Service (KMS) Adapters.

================================================================================
ARCHITECTURE & THREAT MODEL (Decision #35, HARDEN-008):
================================================================================
This module defines the abstract Signer interface and pluggable provider
adapters for Ed25519 asymmetric signing of audit chain checkpoints.

Key Custody Boundaries:
1. LocalFileSigner:
   [DEV/DEMO ONLY — NOT FOR PRODUCTION]
   Loads private keys from a local filesystem .pem file. Storing private keys
   on the application server collapses the threat boundary: an attacker who
   compromises the app host (A_APP) can forge checkpoint signatures.

2. KmsSigner (AWS KMS):
   Signs digests within FIPS 140-2 Level 3 Hardware Security Modules (HSMs).
   Private keys never leave AWS KMS; signing calls are gated by AWS IAM and
   audited by AWS CloudTrail. Requires optional extra: pip install .[kms]

3. VaultTransitSigner (HashiCorp Vault Transit):
   Signs digests inside HashiCorp Vault Transit Secrets Engine. Private keys
   never enter application host memory. Requires optional extra: pip install .[kms]

4. KeyRegistry:
   Provides keyset resolution supporting on-chain key rotation (key_id):
   historical checkpoints verify against the key valid at their creation time.
================================================================================
"""

from __future__ import annotations

import abc
import base64
import logging
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger("argus.crypto.kms")


class Signer(abc.ABC):
    """Abstract base class for asymmetric cryptographic signing providers.

    All implementations provide Ed25519 signing and verification over arbitrary
    byte streams (e.g. SHA-256 checkpoint hashes).
    """

    @property
    @abc.abstractmethod
    def key_id(self) -> str:
        """Unique identifier or URI for the cryptographic key.

        Examples:
            - "local:ed25519:v1"
            - "arn:aws:kms:us-east-1:123456789012:key/abc-123"
            - "vault:transit:keys/argus-checkpoint"
        """
        pass

    @property
    def algorithm(self) -> str:
        """Cryptographic algorithm identifier (default: 'Ed25519')."""
        return "Ed25519"

    @abc.abstractmethod
    def sign(self, data: bytes) -> bytes:
        """Signs the input data and returns raw signature bytes (64 bytes for Ed25519).

        Args:
            data: Raw message bytes or hash digest to sign.

        Returns:
            bytes: Cryptographic signature bytes.
        """
        pass

    @abc.abstractmethod
    def get_public_key_bytes(self) -> bytes:
        """Returns the raw 32-byte Ed25519 public key.

        Returns:
            bytes: 32 raw public key bytes.
        """
        pass

    def get_public_key(self) -> Ed25519PublicKey:
        """Constructs and returns a cryptography Ed25519PublicKey instance."""
        return Ed25519PublicKey.from_public_bytes(self.get_public_key_bytes())

    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verifies a signature against data using this signer's public key.

        Args:
            data: Original message or hash bytes that were signed.
            signature: Raw signature bytes to verify.

        Returns:
            bool: True if signature is cryptographically valid, False otherwise.
        """
        try:
            pub_key = self.get_public_key()
            pub_key.verify(signature, data)
            return True
        except (InvalidSignature, Exception):
            return False


class LocalFileSigner(Signer):
    """Local filesystem Ed25519 signer.

    ========================================================================
    [DEV/DEMO ONLY — NOT FOR PRODUCTION]
    ========================================================================
    SECURITY NOTICE:
    Storing Ed25519 private keys on local application server filesystems
    collapses the threat boundary against host-compromise attackers (A_APP).
    If an attacker compromises the server hosting this private key, they can
    forge valid checkpoint signatures and rewrite audit history undetected.
    For production compliance (SOC 2 CC6.8, SOX 404, ISO 27001), use managed
    HSM/KMS key custody (KmsSigner or VaultTransitSigner) where private keys
    never enter host memory.
    ========================================================================
    """

    def __init__(
        self,
        key_path: str | Path | None = None,
        private_key: Ed25519PrivateKey | None = None,
        key_id: str = "local:ed25519:v1",
    ) -> None:
        """Initializes a local file signer from a key path or existing key object.

        Args:
            key_path: Path to Ed25519 private key PEM file.
            private_key: Pre-loaded Ed25519PrivateKey instance.
            key_id: Key identifier string (default: "local:ed25519:v1").
        """
        self._key_id = key_id

        if private_key is not None:
            self._private_key = private_key
        elif key_path is not None:
            from db.cli.keygen import load_private_key
            self._private_key = load_private_key(str(key_path))
        else:
            from db.cli.keygen import get_default_key_dir, load_private_key
            default_path = os.path.join(get_default_key_dir(), "signing_key.pem")
            if not os.path.exists(default_path):
                raise FileNotFoundError(
                    f"Local signing key not found at '{default_path}'. "
                    "Run 'argus-verifier keygen' first or provide key_path/private_key."
                )
            self._private_key = load_private_key(default_path)

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, data: bytes) -> bytes:
        return self._private_key.sign(data)

    def get_public_key_bytes(self) -> bytes:
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def get_public_key(self) -> Ed25519PublicKey:
        return self._private_key.public_key()


class KmsSigner(Signer):
    """AWS Key Management Service (KMS) asymmetric Ed25519 signer adapter.

    Private keys are generated, stored, and used entirely within FIPS 140-2
    Level 3 Hardware Security Modules (HSMs). Key material cannot be exported.
    All signing operations generate immutable AWS CloudTrail audit logs.

    Requires optional dependency: pip install .[kms] (or boto3).
    """

    def __init__(
        self,
        key_id: str,
        client: Any | None = None,
        region_name: str | None = None,
        public_key_bytes: bytes | None = None,
    ) -> None:
        """Initializes an AWS KMS signer.

        Args:
            key_id: AWS KMS Key ARN, Alias, or Key ID.
            client: Optional pre-configured boto3 KMS client (for mocking/DI).
            region_name: AWS region name (e.g. 'us-east-1').
            public_key_bytes: Optional pre-cached 32-byte Ed25519 public key.
        """
        self._key_id = key_id
        self._cached_public_key_bytes = public_key_bytes

        if client is not None:
            self._client = client
        else:
            try:
                import boto3  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ImportError(
                    "boto3 is required for KmsSigner. "
                    "Install optional KMS extras with: pip install .[kms] or pip install boto3"
                ) from exc
            self._client = boto3.client("kms", region_name=region_name)

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, data: bytes) -> bytes:
        """Executes an asymmetric sign operation in AWS KMS."""
        response = self._client.sign(
            KeyId=self._key_id,
            Message=data,
            MessageType="RAW",
            SigningAlgorithm="ED25519_SHA_512",
        )
        return response["Signature"]

    def get_public_key_bytes(self) -> bytes:
        """Retrieves and caches the Ed25519 public key from KMS."""
        if self._cached_public_key_bytes is not None:
            return self._cached_public_key_bytes

        response = self._client.get_public_key(KeyId=self._key_id)
        raw_or_der = response["PublicKey"]

        if len(raw_or_der) == 32:
            self._cached_public_key_bytes = raw_or_der
        else:
            pub = serialization.load_der_public_key(raw_or_der)
            if not isinstance(pub, Ed25519PublicKey):
                raise TypeError(f"KMS key is not Ed25519: got {type(pub)}")
            self._cached_public_key_bytes = pub.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        return self._cached_public_key_bytes


class VaultTransitSigner(Signer):
    """HashiCorp Vault Transit Secrets Engine adapter for Ed25519 signing.

    Cryptographic signing operations are performed inside Vault. Private keys
    never enter host memory.

    Requires optional dependency: pip install .[kms] (or hvac).
    """

    def __init__(
        self,
        key_name: str,
        client: Any | None = None,
        url: str | None = None,
        token: str | None = None,
        mount_point: str = "transit",
        public_key_bytes: bytes | None = None,
    ) -> None:
        """Initializes a HashiCorp Vault Transit signer.

        Args:
            key_name: Named key in Vault Transit engine (e.g. 'argus-checkpoint').
            client: Optional pre-configured hvac.Client instance (for mocking/DI).
            url: Vault server URL (e.g. 'https://vault.internal:8200').
            token: Vault client authentication token.
            mount_point: Vault transit mount path (default: 'transit').
            public_key_bytes: Optional pre-cached 32-byte Ed25519 public key.
        """
        self._key_name = key_name
        self._mount_point = mount_point
        self._cached_public_key_bytes = public_key_bytes

        if client is not None:
            self._client = client
        else:
            try:
                import hvac  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ImportError(
                    "hvac is required for VaultTransitSigner. "
                    "Install optional KMS extras with: pip install .[kms] or pip install hvac"
                ) from exc
            self._client = hvac.Client(url=url, token=token)

    @property
    def key_id(self) -> str:
        return f"vault:{self._mount_point}:keys/{self._key_name}"

    def sign(self, data: bytes) -> bytes:
        """Signs input data via Vault Transit sign_data endpoint."""
        b64_data = base64.b64encode(data).decode("ascii")
        response = self._client.secrets.transit.sign_data(
            name=self._key_name,
            hash_input=b64_data,
            mount_point=self._mount_point,
        )
        sig_str: str = response["data"]["signature"]
        if sig_str.startswith("vault:"):
            parts = sig_str.split(":")
            raw_b64 = parts[-1]
        else:
            raw_b64 = sig_str
        return base64.b64decode(raw_b64)

    def get_public_key_bytes(self) -> bytes:
        """Retrieves and caches the public key from Vault Transit."""
        if self._cached_public_key_bytes is not None:
            return self._cached_public_key_bytes

        response = self._client.secrets.transit.read_key(
            name=self._key_name,
            mount_point=self._mount_point,
        )
        latest_version = str(response["data"]["latest_version"])
        key_info = response["data"]["keys"][latest_version]
        b64_pub = key_info.get("public_key")
        if not b64_pub:
            raise ValueError(f"Vault key '{self._key_name}' does not expose public_key")
        self._cached_public_key_bytes = base64.b64decode(b64_pub)
        return self._cached_public_key_bytes


class KeyRegistry:
    """Keyset registry managing key_id to public key / signer mappings.

    Supports continuous key rotation: historical checkpoints minted under an older
    key_id verify against the historical key, while newly minted checkpoints verify
    against the active key.
    """

    def __init__(self) -> None:
        self._keys: dict[str, Any] = {}
        self._default_key_id: str | None = None

    def register(
        self,
        key_id: str,
        key_or_signer: Any,
        is_default: bool = False,
    ) -> None:
        """Registers a public key, public key bytes, or Signer for a key_id."""
        self._keys[key_id] = key_or_signer
        if is_default or self._default_key_id is None:
            self._default_key_id = key_id

    def get(self, key_id: str | None = None) -> Any:
        """Retrieves the registered key object for key_id, falling back to default when key_id is None."""
        if key_id is not None:
            if key_id in self._keys:
                return self._keys[key_id]
            raise KeyError(f"Cryptographic key '{key_id}' not found in KeyRegistry")
        if self._default_key_id and self._default_key_id in self._keys:
            return self._keys[self._default_key_id]
        raise KeyError(f"Cryptographic key '{key_id}' not found in KeyRegistry")

    def get_public_key(self, key_id: str | None = None) -> Ed25519PublicKey:
        """Resolves an Ed25519PublicKey instance for the given key_id."""
        item = self.get(key_id)
        if isinstance(item, Ed25519PublicKey):
            return item
        if hasattr(item, "get_public_key"):
            return item.get_public_key()
        if hasattr(item, "public_key"):
            return item.public_key()
        if isinstance(item, (bytes, bytearray)):
            if len(item) == 32:
                return Ed25519PublicKey.from_public_bytes(bytes(item))
            return serialization.load_pem_public_key(bytes(item))  # type: ignore[return-value]
        raise TypeError(f"Cannot derive Ed25519PublicKey from {type(item)}")

    def verify_checkpoint(
        self,
        checkpoint_hash: str,
        signature: bytes,
        key_id: str | None = None,
    ) -> bool:
        """Resolves the key for key_id and verifies the checkpoint signature."""
        try:
            pub_key = self.get_public_key(key_id)
            pub_key.verify(signature, checkpoint_hash.encode("utf-8"))
            return True
        except (InvalidSignature, Exception):
            return False

    @classmethod
    def from_dict(
        cls,
        keys_dict: dict[str, Any],
        default_key_id: str | None = None,
    ) -> KeyRegistry:
        """Creates a KeyRegistry from a dictionary mapping key_id to key objects."""
        registry = cls()
        for k_id, k_val in keys_dict.items():
            registry.register(k_id, k_val, is_default=(k_id == default_key_id))
        return registry
