"""Ed25519 checkpoint signing and verification utility for the Argus verification engine."""

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

def sign_checkpoint(private_key: Ed25519PrivateKey, checkpoint_hash: str) -> bytes:
    """Signs a checkpoint hash string using an Ed25519 private key.

    Args:
        private_key (Ed25519PrivateKey): The Ed25519 private key to use for signing.
        checkpoint_hash (str): The checkpoint hash string to sign.

    Returns:
        bytes: The raw signature bytes.
    """
    signature = private_key.sign(checkpoint_hash.encode('utf-8'))
    return signature

def verify_signature(public_key: Ed25519PublicKey, checkpoint_hash: str, signature: bytes) -> bool:
    """Verifies a signature for a checkpoint hash string using an Ed25519 public key.

    Args:
        public_key (Ed25519PublicKey): The Ed25519 public key to use for verification.
        checkpoint_hash (str): The checkpoint hash string that was signed.
        signature (bytes): The signature to verify.

    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    try:
        public_key.verify(signature, checkpoint_hash.encode('utf-8'))
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False
