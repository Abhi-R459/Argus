"""Ed25519 key generation utility for the Argus verification engine."""

import os
from pathlib import Path
from typing import Tuple, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

def get_default_key_dir() -> str:
    """Returns the default directory for Argus keys.

    Returns:
        str: The path to the default key directory (~/.argus/).
    """
    return str(Path.home() / ".argus")

def generate_keypair() -> Tuple[bytes, bytes]:
    """Generates an Ed25519 keypair.

    Returns:
        Tuple[bytes, bytes]: A tuple containing the private and public keys as PEM encoded bytes.
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_pem, public_pem

def save_keypair(private_pem: bytes, public_pem: bytes, directory: Optional[str] = None) -> Tuple[str, str]:
    """Saves the Ed25519 keypair to the specified directory.

    Args:
        private_pem (bytes): The private key in PEM format.
        public_pem (bytes): The public key in PEM format.
        directory (Optional[str], optional): The directory to save the keys in. Defaults to None, which uses the default key directory.

    Returns:
        Tuple[str, str]: A tuple containing the paths to the saved private and public keys.
    """
    key_dir = Path(directory) if directory else Path(get_default_key_dir())
    key_dir.mkdir(parents=True, exist_ok=True)

    private_key_path = key_dir / "signing_key.pem"
    public_key_path = key_dir / "public_key.pem"

    with open(private_key_path, "wb") as f:
        f.write(private_pem)

    with open(public_key_path, "wb") as f:
        f.write(public_pem)

    # Restrict permissions for private key
    try:
        os.chmod(private_key_path, 0o600)
    except Exception:
        pass

    return str(private_key_path), str(public_key_path)

def load_private_key(path: str) -> Ed25519PrivateKey:
    """Loads an Ed25519 private key from a PEM file.

    Args:
        path (str): The path to the private key file.

    Returns:
        Ed25519PrivateKey: The loaded Ed25519 private key.
    """
    with open(path, "rb") as f:
        key_data = f.read()

    private_key = serialization.load_pem_private_key(
        key_data,
        password=None
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Loaded key is not an Ed25519 private key.")
        
    return private_key

def load_public_key(path: str) -> Ed25519PublicKey:
    """Loads an Ed25519 public key from a PEM file.

    Args:
        path (str): The path to the public key file.

    Returns:
        Ed25519PublicKey: The loaded Ed25519 public key.
    """
    with open(path, "rb") as f:
        key_data = f.read()

    public_key = serialization.load_pem_public_key(key_data)
    if not isinstance(public_key, Ed25519PublicKey):
        raise ValueError("Loaded key is not an Ed25519 public key.")
        
    return public_key
