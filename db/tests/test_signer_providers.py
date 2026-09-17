"""Unit tests for Argus Signer abstraction, Cloud KMS / Vault adapters, and KeyRegistry key rotation.

Tests cover:
1. Signer abstract interface enforcement.
2. LocalFileSigner ([DEV/DEMO ONLY]) lifecycle, warnings, signing, and verification.
3. KmsSigner (AWS KMS) adapter with mock client and missing dependency guard.
4. VaultTransitSigner (HashiCorp Vault) adapter with mock client and missing dependency guard.
5. KeyRegistry keyset resolution supporting seamless on-chain key rotation.
6. Integration with store_checkpoint and verify_checkpoint_signatures.
"""

from __future__ import annotations

import base64
import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

from db.crypto.kms import (
    Signer,
    LocalFileSigner,
    KmsSigner,
    VaultTransitSigner,
    KeyRegistry,
)
from db.cli.signer import sign_checkpoint, verify_signature
from db.cli.checkpoint_store import (
    store_checkpoint,
    create_dual_trigger_checkpoint,
    verify_checkpoint_signatures,
)


# ===================================================================
# 1. Signer Abstract Interface Tests
# ===================================================================

def test_signer_abc_cannot_be_instantiated():
    """Signer ABC cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        Signer()  # type: ignore[abstract]


class IncompleteSigner(Signer):
    """Subclass that forgets to implement get_public_key_bytes."""
    @property
    def key_id(self) -> str:
        return "incomplete"

    def sign(self, data: bytes) -> bytes:
        return b""


def test_incomplete_signer_fails():
    """Subclass without all abstract methods cannot be instantiated."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteSigner()  # type: ignore[abstract]


# ===================================================================
# 2. LocalFileSigner Tests ([DEV/DEMO ONLY])
# ===================================================================

def test_local_file_signer_docstring_and_security_notice():
    """LocalFileSigner docstring contains explicit [DEV/DEMO ONLY] warning."""
    assert "[DEV/DEMO ONLY — NOT FOR PRODUCTION]" in LocalFileSigner.__doc__
    assert "A_APP" in LocalFileSigner.__doc__
    assert "KmsSigner" in LocalFileSigner.__doc__


def test_local_file_signer_with_in_memory_key():
    """LocalFileSigner works with a pre-loaded Ed25519PrivateKey."""
    priv_key = Ed25519PrivateKey.generate()
    signer = LocalFileSigner(private_key=priv_key, key_id="local:test:v1")

    assert signer.key_id == "local:test:v1"
    assert signer.algorithm == "Ed25519"

    message = b"checkpoint_sha256_hash_value"
    sig = signer.sign(message)
    assert isinstance(sig, bytes)
    assert len(sig) == 64

    pub_bytes = signer.get_public_key_bytes()
    assert isinstance(pub_bytes, bytes)
    assert len(pub_bytes) == 32

    pub_key = signer.get_public_key()
    assert isinstance(pub_key, Ed25519PublicKey)

    assert signer.verify(message, sig) is True
    assert signer.verify(b"tampered_message", sig) is False
    assert signer.verify(message, b"bad_signature" * 5) is False


def test_local_file_signer_from_file():
    """LocalFileSigner correctly loads private key from a PEM file."""
    priv_key = Ed25519PrivateKey.generate()
    pem_bytes = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
        f.write(pem_bytes)
        temp_path = f.name

    try:
        signer = LocalFileSigner(key_path=temp_path, key_id="local:pem:v1")
        assert signer.key_id == "local:pem:v1"

        data = b"audit_trail_entry_digest"
        sig = signer.sign(data)
        assert signer.verify(data, sig) is True
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_local_file_signer_missing_file_raises():
    """LocalFileSigner raises FileNotFoundError when file is missing."""
    with pytest.raises(FileNotFoundError):
        LocalFileSigner(key_path="/path/that/definitely/does/not/exist/key.pem")


# ===================================================================
# 3. KmsSigner Tests (AWS KMS Adapter)
# ===================================================================

def test_kms_signer_missing_boto3_raises_import_error():
    """KmsSigner raises clear ImportError advising pip install .[kms] when boto3 is absent."""
    with patch.dict("sys.modules", {"boto3": None}):
        with pytest.raises(ImportError, match="pip install .\\[kms\\]"):
            KmsSigner(key_id="arn:aws:kms:us-east-1:123456789012:key/test", client=None)


def test_kms_signer_with_mock_client():
    """KmsSigner signs and verifies using a mock AWS KMS client."""
    mock_kms = MagicMock()
    priv_key = Ed25519PrivateKey.generate()
    raw_pub_bytes = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    def mock_sign(KeyId, Message, MessageType, SigningAlgorithm):
        assert KeyId == "arn:aws:kms:us-east-1:123456789012:key/test-key"
        assert MessageType == "RAW"
        assert SigningAlgorithm == "ED25519_SHA_512"
        return {"Signature": priv_key.sign(Message)}

    mock_kms.sign.side_effect = mock_sign
    mock_kms.get_public_key.return_value = {"PublicKey": raw_pub_bytes}

    signer = KmsSigner(
        key_id="arn:aws:kms:us-east-1:123456789012:key/test-key",
        client=mock_kms,
    )

    assert signer.key_id == "arn:aws:kms:us-east-1:123456789012:key/test-key"
    assert signer.algorithm == "Ed25519"

    message = b"checkpoint_digest_12345"
    sig = signer.sign(message)
    assert len(sig) == 64

    pub_bytes = signer.get_public_key_bytes()
    assert pub_bytes == raw_pub_bytes

    assert signer.verify(message, sig) is True
    assert signer.verify(b"altered_message", sig) is False


# ===================================================================
# 4. VaultTransitSigner Tests (HashiCorp Vault Adapter)
# ===================================================================

def test_vault_signer_missing_hvac_raises_import_error():
    """VaultTransitSigner raises clear ImportError advising pip install .[kms] when hvac is absent."""
    with patch.dict("sys.modules", {"hvac": None}):
        with pytest.raises(ImportError, match="pip install .\\[kms\\]"):
            VaultTransitSigner(key_name="argus-key", client=None)


def test_vault_transit_signer_with_mock_client():
    """VaultTransitSigner signs and verifies using a mock HashiCorp Vault client."""
    mock_hvac = MagicMock()
    priv_key = Ed25519PrivateKey.generate()
    raw_pub_bytes = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    def mock_sign_data(name, hash_input, mount_point):
        assert name == "argus-checkpoint"
        assert mount_point == "transit"
        raw_msg = base64.b64decode(hash_input)
        sig = priv_key.sign(raw_msg)
        return {"data": {"signature": f"vault:v1:{base64.b64encode(sig).decode('ascii')}"}}

    mock_hvac.secrets.transit.sign_data.side_effect = mock_sign_data
    mock_hvac.secrets.transit.read_key.return_value = {
        "data": {
            "latest_version": 1,
            "keys": {
                "1": {"public_key": base64.b64encode(raw_pub_bytes).decode("ascii")}
            },
        }
    }

    signer = VaultTransitSigner(
        key_name="argus-checkpoint",
        client=mock_hvac,
    )

    assert signer.key_id == "vault:transit:keys/argus-checkpoint"
    assert signer.algorithm == "Ed25519"

    message = b"checkpoint_hash_vault_test"
    sig = signer.sign(message)
    assert len(sig) == 64

    pub_bytes = signer.get_public_key_bytes()
    assert pub_bytes == raw_pub_bytes

    assert signer.verify(message, sig) is True
    assert signer.verify(b"different_data", sig) is False


# ===================================================================
# 5. KeyRegistry & Keyset Resolution (Key Rotation) Tests
# ===================================================================

def test_key_registry_rotation_and_resolution():
    """KeyRegistry resolves historical keys correctly across key rotation events."""
    key_2025 = Ed25519PrivateKey.generate()
    key_2026 = Ed25519PrivateKey.generate()

    signer_2025 = LocalFileSigner(private_key=key_2025, key_id="local:ed25519:2025")
    signer_2026 = LocalFileSigner(private_key=key_2026, key_id="local:ed25519:2026")

    registry = KeyRegistry()
    registry.register("local:ed25519:2025", signer_2025.get_public_key())
    registry.register("local:ed25519:2026", signer_2026.get_public_key(), is_default=True)

    hash_2025 = "a" * 64
    sig_2025 = signer_2025.sign(hash_2025.encode("utf-8"))

    hash_2026 = "b" * 64
    sig_2026 = signer_2026.sign(hash_2026.encode("utf-8"))

    # Verify both checkpoints resolve their respective keys and succeed
    assert registry.verify_checkpoint(hash_2025, sig_2025, key_id="local:ed25519:2025") is True
    assert registry.verify_checkpoint(hash_2026, sig_2026, key_id="local:ed25519:2026") is True

    # Default resolution without key_id uses active 2026 key
    assert registry.verify_checkpoint(hash_2026, sig_2026) is True
    assert registry.verify_checkpoint(hash_2025, sig_2025) is False  # Fails because default is 2026

    # Cross-key tampering detection: 2025 signature with 2026 key fails
    assert registry.verify_checkpoint(hash_2025, sig_2025, key_id="local:ed25519:2026") is False

    # Unknown key raises KeyError or returns False
    with pytest.raises(KeyError, match="not found in KeyRegistry"):
        registry.get("local:ed25519:1999")
    assert registry.verify_checkpoint(hash_2025, sig_2025, key_id="local:ed25519:1999") is False


def test_key_registry_from_dict():
    """KeyRegistry.from_dict initializes properly with default."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    registry = KeyRegistry.from_dict({"k1": pub, "k2": pub}, default_key_id="k2")
    assert registry.get("k1") == pub
    assert registry.get() == pub


def test_signer_module_backward_compatibility():
    """db.cli.signer helper functions work seamlessly with both keys and Signers."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    signer = LocalFileSigner(private_key=priv, key_id="local:compat:v1")

    chk_hash = "c" * 64

    # Sign using raw private key
    sig1 = sign_checkpoint(priv, chk_hash)
    assert verify_signature(pub, chk_hash, sig1) is True

    # Sign using Signer instance
    sig2 = sign_checkpoint(signer, chk_hash)
    assert verify_signature(signer, chk_hash, sig2) is True
    assert verify_signature(pub, chk_hash, sig2) is True

    # Verify with KeyRegistry passed to verify_signature
    reg = KeyRegistry()
    reg.register("local:compat:v1", pub)
    assert verify_signature(reg, chk_hash, sig2, key_id="local:compat:v1") is True


# ===================================================================
# 6. Database Checkpoint Store key_id Integration Tests
# ===================================================================

def test_store_checkpoint_with_key_id():
    """store_checkpoint writes key_id to chain_checkpoints table."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.rowcount = 1

    seq_id = 50
    chk_hash = "e" * 64
    sig = b"sig_bytes_here"
    key_id = "arn:aws:kms:us-east-1:123:key/abc"

    inserted = store_checkpoint(mock_conn, seq_id, chk_hash, sig, key_id=key_id)
    assert inserted is True

    mock_cur.execute.assert_called_once_with(
        "INSERT INTO chain_checkpoints (sequence_id, checkpoint_hash, signature, key_id) "
        "VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (sequence_id) DO NOTHING",
        (seq_id, chk_hash, sig, key_id),
    )


def test_create_dual_trigger_checkpoint_with_signer_sets_key_id():
    """create_dual_trigger_checkpoint extracts key_id from Signer instance."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.rowcount = 1

    priv = Ed25519PrivateKey.generate()
    signer = LocalFileSigner(private_key=priv, key_id="local:custom:v99")

    # Mock should_create_checkpoint to fire
    with patch("db.cli.checkpoint_store.should_create_checkpoint") as mock_should:
        mock_should.return_value = (
            True,
            "entry_count_threshold",
            {
                "last_checkpoint_seq": 0,
                "entries_since": 25,
                "seconds_since": 10.0,
            },
        )
        with patch("db.cli.checkpoint_store.get_uncheckpointed_entries") as mock_uncheck:
            mock_uncheck.return_value = [
                {"sequence_id": 1, "entry_hash": "a" * 64, "created_at": None},
                {"sequence_id": 25, "entry_hash": "b" * 64, "created_at": None},
            ]
            mock_cur.fetchone.return_value = {
                "checkpoint_id": 10,
                "sequence_id": 25,
                "checkpoint_hash": "dummy",
                "signature": b"sig",
                "created_at": None,
            }

            result = create_dual_trigger_checkpoint(mock_conn, signer=signer)

            assert result is not None
            assert result["key_id"] == "local:custom:v99"


def test_verify_checkpoint_signatures_keyset_resolution():
    """verify_checkpoint_signatures validates multiple checkpoints signed with rotated keys."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    priv1 = Ed25519PrivateKey.generate()
    priv2 = Ed25519PrivateKey.generate()

    hash1 = "1" * 64
    sig1 = priv1.sign(hash1.encode("utf-8"))

    hash2 = "2" * 64
    sig2 = priv2.sign(hash2.encode("utf-8"))

    mock_cur.fetchall.return_value = [
        {
            "checkpoint_id": 1,
            "sequence_id": 25,
            "checkpoint_hash": hash1,
            "signature": sig1,
            "key_id": "key:2025",
            "created_at": None,
        },
        {
            "checkpoint_id": 2,
            "sequence_id": 50,
            "checkpoint_hash": hash2,
            "signature": sig2,
            "key_id": "key:2026",
            "created_at": None,
        },
    ]

    registry = KeyRegistry()
    registry.register("key:2025", priv1.public_key())
    registry.register("key:2026", priv2.public_key(), is_default=True)

    all_valid, records = verify_checkpoint_signatures(mock_conn, key_registry=registry)

    assert all_valid is True
    assert len(records) == 2
    assert records[0]["status"] == "verified"
    assert records[0]["key_id"] == "key:2025"
    assert records[1]["status"] == "verified"
    assert records[1]["key_id"] == "key:2026"
