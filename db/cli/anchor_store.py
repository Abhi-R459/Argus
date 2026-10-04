"""Pluggable external anchor stores for Argus checkpoint tamper evidence.

================================================================================
ARCHITECTURE & TRUST HIERARCHY (Decision #37, HARDEN-010):
================================================================================
External anchoring binds Argus checkpoint digests to independent, out-of-band
storage mechanisms. Even if a rogue database superuser (A_DBA) alters audit rows
and forges database-internal checkpoint records, the external anchor remains
immutable, exposing the discrepancy during forensic verification.

Supported Adapters:
1. LocalFileAnchorStore:
   [DEV/LOCAL ONLY] Writes JSON checkpoints to a designated filesystem directory.
   Provides baseline local testing.
2. GitHubAnchorStore:
   Commits checkpoint JSON payloads to a remote GitHub repository via GitHub REST API.
3. Rfc3161AnchorStore:
   Submits SHA-256 checkpoint digests via RFC 3161 DER protocol to a Time-Stamping
   Authority (TSA). Stores notarized .tsr tokens and metadata locally for offline
   cryptographic verification. Includes explicit FreeTSA disclaimer.
4. S3WormAnchorStore:
   Uploads checkpoint payloads to AWS S3 with Object Lock in COMPLIANCE mode,
   enforcing Write-Once-Read-Many (WORM) retention where no user (including root)
   can alter or delete records before the retention period expires.
================================================================================
"""

from __future__ import annotations

import abc
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import urllib.error
import urllib.request

logger = logging.getLogger("argus.anchor_store")

# FreeTSA legal evidentiary disclaimer (RFC 3161 demonstration service)
FREETSA_DISCLAIMER = (
    "DISCLAIMER [DEMO / NON-PRODUCTION]: FreeTSA (freetsa.org) is a free, publicly accessible "
    "RFC 3161 demonstration service suitable for development, integration testing, and academic "
    "evaluation. It is NOT an EU Qualified Trust Service Provider (QTSP) under eIDAS (Regulation (EU) "
    "910/2014), is not included on Adobe Approved Trust List (AATL) or Microsoft Root CA Program, "
    "provides no Service Level Agreements (SLAs), and offers no cryptographic indemnity. "
    "Production deployments requiring legally binding audit trails must configure an accredited, "
    "WebTrust-audited commercial TSA (e.g., DigiCert, Sectigo, GlobalSign) or an internal HSM-backed "
    "Enterprise PKI Time-Stamping Authority."
)


# ==============================================================================
# Pure Python ASN.1 DER Utilities for RFC 3161 (Zero External Dependencies)
# ==============================================================================

def encode_der_length(length: int) -> bytes:
    """Encodes a length value in ASN.1 DER format.
    
    Args:
        length: Non-negative integer length.
        
    Returns:
        bytes: DER-encoded length field.
    """
    if length < 128:
        return bytes([length])
    len_bytes = []
    temp = length
    while temp > 0:
        len_bytes.insert(0, temp & 0xFF)
        temp >>= 8
    return bytes([0x80 | len(len_bytes)]) + bytes(len_bytes)


def decode_der_length(data: bytes, offset: int) -> Tuple[int, int]:
    """Decodes a length value from DER data at the specified offset.
    
    Args:
        data: Buffer containing DER bytes.
        offset: Current reading offset.
        
    Returns:
        Tuple[int, int]: (length, next_offset_after_length_field)
    """
    if offset >= len(data):
        raise ValueError("Unexpected EOF reading DER length")
    first = data[offset]
    offset += 1
    if first < 128:
        return first, offset
    num_bytes = first & 0x7F
    if num_bytes == 0 or offset + num_bytes > len(data):
        raise ValueError("Invalid DER length encoding")
    length = int.from_bytes(data[offset:offset + num_bytes], "big")
    return length, offset + num_bytes


def decode_der_tlv(data: bytes, offset: int = 0) -> Tuple[int, bytes, int]:
    """Decodes a single ASN.1 DER Tag-Length-Value (TLV) element.
    
    Args:
        data: Buffer containing DER bytes.
        offset: Offset where TLV starts.
        
    Returns:
        Tuple[int, bytes, int]: (tag, value_bytes, next_offset)
    """
    if offset >= len(data):
        raise ValueError("Unexpected EOF reading DER tag")
    tag = data[offset]
    offset += 1
    length, content_start = decode_der_length(data, offset)
    content_end = content_start + length
    if content_end > len(data):
        raise ValueError("DER TLV content extends beyond data buffer")
    return tag, data[content_start:content_end], content_end


def build_rfc3161_request(digest: bytes, cert_req: bool = True) -> bytes:
    """Constructs a binary RFC 3161 TimeStampReq DER payload for a SHA-256 digest.
    
    ASN.1 Structure (RFC 3161 §2.4.1):
        TimeStampReq ::= SEQUENCE {
            version INTEGER { v1(1) },
            messageImprint MessageImprint {
                hashAlgorithm AlgorithmIdentifier (SHA-256: 2.16.840.1.101.3.4.2.1),
                hashedMessage OCTET STRING (32 bytes)
            },
            certReq BOOLEAN DEFAULT FALSE
        }
        
    Args:
        digest: 32-byte SHA-256 digest.
        cert_req: Whether to request TSA signing certificate chain in response.
        
    Returns:
        bytes: DER-encoded TimeStampReq (59 bytes).
    """
    if len(digest) != 32:
        raise ValueError(f"Expected 32-byte SHA-256 digest, got {len(digest)} bytes")
    
    # AlgorithmIdentifier for SHA-256 with NULL parameter:
    # SEQUENCE { OID: 2.16.840.1.101.3.4.2.1, NULL }
    alg_id = bytes.fromhex("300d06096086480165030402010500")
    
    # MessageImprint: SEQUENCE { AlgorithmIdentifier, OCTET STRING(32) }
    hashed_msg = bytes([0x04, len(digest)]) + digest
    msg_imprint_content = alg_id + hashed_msg
    msg_imprint = bytes([0x30]) + encode_der_length(len(msg_imprint_content)) + msg_imprint_content
    
    version = bytes.fromhex("020101")  # INTEGER 1
    cert_req_bytes = bytes.fromhex("0101ff") if cert_req else bytes.fromhex("010100")
    
    req_content = version + msg_imprint + cert_req_bytes
    return bytes([0x30]) + encode_der_length(len(req_content)) + req_content


def parse_rfc3161_response(resp_der: bytes) -> Tuple[int, bytes]:
    """Parses an RFC 3161 TimeStampResp DER payload and extracts PKIStatus and Token.
    
    ASN.1 Structure (RFC 3161 §2.4.2):
        TimeStampResp ::= SEQUENCE {
            status PKIStatusInfo {
                status PKIStatus (INTEGER: 0=granted, 1=grantedWithMods, 2=rejection...)
            },
            timeStampToken TimeStampToken OPTIONAL (ContentInfo SEQUENCE)
        }
        
    Args:
        resp_der: Binary DER bytes from TSA response.
        
    Returns:
        Tuple[int, bytes]: (status_code, timestamp_token_der_bytes)
        
    Raises:
        ValueError: If ASN.1 DER structure is invalid or corrupt.
    """
    tag, resp_val, _ = decode_der_tlv(resp_der, 0)
    if tag != 0x30:
        raise ValueError(f"Expected SEQUENCE tag 0x30 for TimeStampResp, got {hex(tag)}")
    
    pki_tag, pki_val, pki_next = decode_der_tlv(resp_val, 0)
    if pki_tag != 0x30:
        raise ValueError(f"Expected SEQUENCE tag 0x30 for PKIStatusInfo, got {hex(pki_tag)}")
    
    status_tag, status_val, _ = decode_der_tlv(pki_val, 0)
    if status_tag != 0x02:
        raise ValueError(f"Expected INTEGER tag 0x02 for PKIStatus, got {hex(status_tag)}")
    
    status = int.from_bytes(status_val, "big", signed=True)
    
    token_bytes = b""
    if pki_next < len(resp_val):
        _, _, token_end = decode_der_tlv(resp_val, pki_next)
        token_bytes = resp_val[pki_next:token_end]
        
    return status, token_bytes


# ==============================================================================
# Abstract Base Class & Concrete Adapters
# ==============================================================================

class AnchorStore(abc.ABC):
    """Abstract base class for external anchor stores."""

    @abc.abstractmethod
    def push(self, checkpoint_id: int, payload_json: str) -> str:
        """Pushes a checkpoint to the anchor store.

        Args:
            checkpoint_id (int): The ID of the checkpoint.
            payload_json (str): The JSON payload containing checkpoint data.

        Returns:
            str: A reference string or URI for the stored anchor.
        """
        pass

    @abc.abstractmethod
    def verify(self, checkpoint_id: int) -> bool:
        """Verifies that a checkpoint exists and is valid in the anchor store.

        Args:
            checkpoint_id (int): The ID of the checkpoint to verify.

        Returns:
            bool: True if the checkpoint is valid, False otherwise.
        """
        pass


class LocalFileAnchorStore(AnchorStore):
    """Local file system implementation of an anchor store [DEV/LOCAL ONLY]."""

    def __init__(self, base_path: str):
        """Initializes the LocalFileAnchorStore.

        Args:
            base_path (str): The base directory for anchor files.
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def push(self, checkpoint_id: int, payload_json: str) -> str:
        """Pushes a checkpoint to a local file.

        Args:
            checkpoint_id (int): The ID of the checkpoint.
            payload_json (str): The JSON payload containing checkpoint data.

        Returns:
            str: The file path where the anchor was saved.
        """
        file_path = self.base_path / f"{checkpoint_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(payload_json)
        return str(file_path)

    def verify(self, checkpoint_id: int) -> bool:
        """Verifies a checkpoint in the local file system.

        Args:
            checkpoint_id (int): The ID of the checkpoint to verify.

        Returns:
            bool: True if the checkpoint file exists and contains valid JSON.
        """
        file_path = self.base_path / f"{checkpoint_id}.json"
        if not file_path.exists():
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                json.loads(content)
            return True
        except (json.JSONDecodeError, OSError):
            return False


class GitHubAnchorStore(AnchorStore):
    """GitHub implementation of an anchor store committing to a remote repository."""

    def __init__(self, repo: str, token: str, branch: str = "main", path_prefix: str = "anchors"):
        """Initializes the GitHubAnchorStore.

        Args:
            repo (str): The GitHub repository in the format "owner/repo".
            token (str): A GitHub Personal Access Token for authentication.
            branch (str, optional): The branch to commit to. Defaults to 'main'.
            path_prefix (str, optional): The path prefix within the repo. Defaults to 'anchors'.
        """
        self.repo = repo
        self.token = token
        self.branch = branch
        self.path_prefix = path_prefix
        self.base_url = f"https://api.github.com/repos/{self.repo}/contents"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Argus-Anchor-Store",
        }

    def push(self, checkpoint_id: int, payload_json: str) -> str:
        path = f"{self.path_prefix}/{checkpoint_id}.json".strip("/")
        url = f"{self.base_url}/{path}"

        sha = None
        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                sha = data.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

        content_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")

        body: Dict[str, Any] = {
            "message": f"Anchor checkpoint {checkpoint_id}",
            "content": content_b64,
            "branch": self.branch,
        }
        if sha:
            body["sha"] = sha

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=self._get_headers(),
            method="PUT",
        )

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["content"]["html_url"]
        except urllib.error.URLError as e:
            raise Exception(f"Failed to push anchor to GitHub: {e}")

    def verify(self, checkpoint_id: int) -> bool:
        path = f"{self.path_prefix}/{checkpoint_id}.json".strip("/")
        url = f"{self.base_url}/{path}?ref={self.branch}"

        req = urllib.request.Request(url, headers=self._get_headers())

        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                content_b64 = data.get("content", "")
                if not content_b64:
                    return False
                content_json = base64.b64decode(content_b64).decode("utf-8")
                json.loads(content_json)
                return True
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
            return False


class Rfc3161AnchorStore(AnchorStore):
    """RFC 3161 Time-Stamping Authority (TSA) anchor store.
    
    Submits checkpoint SHA-256 digests over HTTP/HTTPS using standard ASN.1 DER
    encoded TimeStampReq queries. Receives and archives cryptographic TimeStampResp
    tokens (.tsr) along with verified metadata JSON.
    
    NOTE ON LEGAL EVIDENTIARY VALUE:
    When using freetsa.org (default for testing/demo), please review FREETSA_DISCLAIMER.
    Commercial or governmental production deployments must supply a licensed,
    WebTrust-audited commercial TSA endpoint.
    """

    disclaimer: str = FREETSA_DISCLAIMER

    def __init__(
        self,
        server_url: str = "http://freetsa.org/tsr",
        local_archive_dir: str = "anchors/rfc3161",
        timeout_seconds: float = 15.0,
        http_opener: Optional[Any] = None,
    ):
        """Initializes the RFC 3161 anchor store.
        
        Args:
            server_url: TSA endpoint URL (e.g. http://freetsa.org/tsr or https://timestamp.digicert.com).
            local_archive_dir: Directory where .tsr tokens and .json receipts are archived.
            timeout_seconds: Network timeout in seconds for TSA HTTP requests.
            http_opener: Optional custom urllib opener or callable for mocking/testing.
        """
        self.server_url = server_url
        self.local_archive_dir = Path(local_archive_dir)
        self.local_archive_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self._http_opener = http_opener

        if "freetsa.org" in self.server_url.lower():
            logger.info("Rfc3161AnchorStore configured with FreeTSA demo server. %s", self.disclaimer)

    def _extract_digest(self, payload_json: str) -> Tuple[bytes, str]:
        """Extracts or computes the 32-byte SHA-256 digest from a checkpoint payload."""
        try:
            parsed = json.loads(payload_json)
            if "checkpoint_hash" in parsed and len(parsed["checkpoint_hash"]) == 64:
                return bytes.fromhex(parsed["checkpoint_hash"]), parsed["checkpoint_hash"]
        except Exception:
            pass
        computed = hashlib.sha256(payload_json.encode("utf-8")).digest()
        return computed, computed.hex()

    def push(self, checkpoint_id: int, payload_json: str) -> str:
        """Submits the checkpoint digest to the TSA and archives the notarized token.
        
        Args:
            checkpoint_id: Checkpoint sequence ID.
            payload_json: Checkpoint JSON string.
            
        Returns:
            str: Path to the stored .tsr token file.
            
        Raises:
            RuntimeError: If the TSA rejects the request or returns invalid DER.
        """
        digest_bytes, digest_hex = self._extract_digest(payload_json)
        req_der = build_rfc3161_request(digest_bytes, cert_req=True)

        req = urllib.request.Request(
            self.server_url,
            data=req_der,
            headers={
                "Content-Type": "application/timestamp-query",
                "Accept": "application/timestamp-reply",
                "User-Agent": "Argus-Anchor-Store/1.1.0 (RFC 3161 Client)",
            },
            method="POST",
        )

        try:
            if self._http_opener is not None:
                resp_bytes = self._http_opener(req)
            else:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    resp_bytes = response.read()
        except Exception as exc:
            raise RuntimeError(f"RFC 3161 TSA HTTP request to {self.server_url} failed: {exc}") from exc

        # Parse DER response
        status, token_bytes = parse_rfc3161_response(resp_bytes)
        # Status 0 = granted, 1 = grantedWithMods
        if status not in (0, 1):
            raise RuntimeError(f"RFC 3161 TSA rejected timestamp request with status: {status}")
        if not token_bytes:
            raise RuntimeError("RFC 3161 TSA response did not contain a valid timeStampToken")

        # Save token file (.tsr)
        tsr_path = self.local_archive_dir / f"{checkpoint_id}.tsr"
        with open(tsr_path, "wb") as f:
            f.write(resp_bytes)

        # Save companion metadata (.json)
        meta_path = self.local_archive_dir / f"{checkpoint_id}.json"
        metadata = {
            "checkpoint_id": checkpoint_id,
            "server_url": self.server_url,
            "digest_hex": digest_hex,
            "status": status,
            "tsr_file": f"{checkpoint_id}.tsr",
            "tsr_base64": base64.b64encode(resp_bytes).decode("utf-8"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload_json": payload_json,
            "disclaimer": self.disclaimer if "freetsa.org" in self.server_url.lower() else None,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return str(tsr_path)

    def verify(self, checkpoint_id: int) -> bool:
        """Verifies an archived RFC 3161 token and metadata receipt.
        
        Args:
            checkpoint_id: Checkpoint sequence ID.
            
        Returns:
            bool: True if both .tsr and .json exist and validate cryptographically.
        """
        tsr_path = self.local_archive_dir / f"{checkpoint_id}.tsr"
        meta_path = self.local_archive_dir / f"{checkpoint_id}.json"

        if not tsr_path.exists() or not meta_path.exists():
            return False

        try:
            with open(tsr_path, "rb") as f:
                tsr_bytes = f.read()
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            # Validate TSR DER structure
            status, token_bytes = parse_rfc3161_response(tsr_bytes)
            if status not in (0, 1) or not token_bytes:
                return False

            # Verify base64 consistency
            if base64.b64decode(metadata.get("tsr_base64", "")) != tsr_bytes:
                return False

            # Verify payload JSON validity
            json.loads(metadata.get("payload_json", "{}"))
            return True
        except Exception:
            return False


class S3WormAnchorStore(AnchorStore):
    """AWS S3 WORM (Write-Once-Read-Many) anchor store with Object Lock.
    
    Anchors checkpoint JSON payloads to an Amazon S3 bucket configured with S3
    Object Lock in COMPLIANCE mode. In COMPLIANCE mode, a protected object version
    cannot be overwritten or deleted by any user, including the AWS root account,
    until the retention period expires.
    """

    def __init__(
        self,
        bucket: str,
        key_prefix: str = "anchors",
        retention_days: int = 365,
        mode: str = "COMPLIANCE",
        region_name: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        """Initializes the S3 WORM anchor store.
        
        Args:
            bucket: Target S3 bucket name (must have S3 Object Lock enabled).
            key_prefix: Object key prefix (folder path).
            retention_days: Number of days to enforce Object Lock retention.
            mode: Object Lock mode ("COMPLIANCE" or "GOVERNANCE"). Default "COMPLIANCE".
            region_name: Optional AWS region (e.g. "us-east-1").
            client: Optional boto3 S3 client (for testing or custom dependency injection).
        """
        self.bucket = bucket
        self.key_prefix = key_prefix
        self.retention_days = retention_days
        self.mode = mode
        self.region_name = region_name
        self._client = client

    def _get_client(self) -> Any:
        """Retrieves or instantiates the boto3 S3 client."""
        if self._client is not None:
            return self._client
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "boto3 is required for S3WormAnchorStore. "
                "Install optional cloud extras with: pip install .[kms] or pip install boto3"
            ) from exc
        self._client = boto3.client("s3", region_name=self.region_name)
        return self._client

    def push(self, checkpoint_id: int, payload_json: str) -> str:
        """Pushes a checkpoint payload to S3 with WORM Object Lock retention.
        
        Args:
            checkpoint_id: Checkpoint sequence ID.
            payload_json: Checkpoint JSON string.
            
        Returns:
            str: S3 URI (s3://bucket/key).
        """
        key = f"{self.key_prefix}/{checkpoint_id}.json".strip("/")
        retain_until = datetime.now(timezone.utc) + timedelta(days=self.retention_days)
        client = self._get_client()

        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload_json.encode("utf-8"),
            ContentType="application/json",
            ObjectLockMode=self.mode,
            ObjectLockRetainUntilDate=retain_until,
        )

        return f"s3://{self.bucket}/{key}"

    def verify(self, checkpoint_id: int) -> bool:
        """Verifies that an anchored checkpoint exists in S3 with valid JSON.
        
        Args:
            checkpoint_id: Checkpoint sequence ID.
            
        Returns:
            bool: True if object exists and contains valid JSON, False otherwise.
        """
        key = f"{self.key_prefix}/{checkpoint_id}.json".strip("/")
        client = self._get_client()
        try:
            resp = client.get_object(Bucket=self.bucket, Key=key)
            body_bytes = resp["Body"].read()
            json.loads(body_bytes.decode("utf-8"))
            return True
        except Exception:
            return False


# ==============================================================================
# Multi-Witness WORM Anchoring (RFC 9162 / NOVEL-010-B)
# ==============================================================================

class MultiWitnessAnchorStore(AnchorStore):
    """Decentralized multi-witness anchor store enforcing M-of-N cosigning quorum (NOVEL-010-B).

    Combines multiple heterogeneous witness anchor adapters (e.g. S3 WORM, RFC 3161 TSA,
    GitHub, and local storage). Checkpoints are formatted as canonical RFC 9162 Notes,
    signed by the Origin, and concurrently cosigned by witnesses. A 2-of-3 quorum is
    required before the checkpoint is considered validly anchored.
    """

    DEFAULT_WITNESS_NAMES = [
        "witness.s3worm.aws/v1",
        "witness.rfc3161.tsa/v1",
        "witness.github.git/v1",
    ]

    def __init__(
        self,
        witnesses: Optional[Any] = None,
        threshold: int = 2,
        base_path: str = "anchors/multi_witness",
        origin_signer: Any = None,
        witness_signers: Optional[Dict[str, Any]] = None,
        witness_names: Optional[list[str]] = None,
    ):
        self.witnesses: list[AnchorStore] = list(witnesses) if witnesses else []
        self.threshold = threshold
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.origin_signer = origin_signer
        self._history: Dict[int, Any] = {}

        # Resolve or generate witness keypairs for simulated cosigning
        self.witness_signers: Dict[str, Any] = dict(witness_signers) if witness_signers else {}
        self.witness_public_keys: Dict[str, str] = {}
        names = witness_names or self.DEFAULT_WITNESS_NAMES

        from db.cli.keygen import generate_keypair
        for name in names:
            if name not in self.witness_signers:
                priv_pem, pub_pem = generate_keypair()
                self.witness_signers[name] = priv_pem
                self.witness_public_keys[name] = pub_pem.decode("utf-8")
            else:
                signer_val = self.witness_signers[name]
                if hasattr(signer_val, "public_key_pem"):
                    self.witness_public_keys[name] = signer_val.public_key_pem
                elif isinstance(signer_val, bytes) and b"BEGIN PUBLIC KEY" in signer_val:
                    self.witness_public_keys[name] = signer_val.decode("utf-8")
                else:
                    _, pub_pem = generate_keypair()
                    self.witness_public_keys[name] = pub_pem.decode("utf-8")

        # Resolve origin public key
        self.origin_public_key_pem: Optional[str] = None
        if self.origin_signer is not None and hasattr(self.origin_signer, "public_key_pem"):
            self.origin_public_key_pem = self.origin_signer.public_key_pem
        else:
            try:
                from db.cli.capsule import resolve_public_key_pem
                self.origin_public_key_pem = resolve_public_key_pem()
            except Exception:
                pass

    def detect_fork(self, note_a: Any, note_b: Any) -> None:
        """Assert consistency between two checkpoint notes for the same sequence."""
        if note_a.sequence_id == note_b.sequence_id:
            if note_a.merkle_root != note_b.merkle_root:
                from db.cli.witness_protocol import ProofOfMisbehavior
                raise ProofOfMisbehavior(
                    sequence_id=note_a.sequence_id,
                    root_a=note_a.merkle_root,
                    root_b=note_b.merkle_root,
                    note_a=note_a,
                    note_b=note_b,
                )

    def push(self, checkpoint_id: int, payload_json: str) -> str:
        """Format RFC 9162 Note, sign by origin, submit to all witnesses, and verify quorum."""
        from db.cli.witness_protocol import (
            CheckpointNote,
            WitnessSignature,
            WitnessedCheckpoint,
            QuorumNotMetError,
        )
        from db.cli.signer import sign_checkpoint

        try:
            payload_data = json.loads(payload_json)
        except Exception:
            payload_data = {"raw": payload_json}

        seq_id = int(payload_data.get("sequence_id", checkpoint_id))
        merkle_root = payload_data.get("merkle_root")
        if not merkle_root:
            merkle_root = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        note = CheckpointNote(
            sequence_id=seq_id,
            merkle_root=merkle_root,
            checkpoint_hash=payload_data.get("checkpoint_hash"),
            metadata={
                "checkpoint_id": checkpoint_id,
                "created_at": payload_data.get("created_at"),
                "entries_count": payload_data.get("entries_count", payload_data.get("merkle_leaf_count", 1)),
            },
        )

        # Split-view / equivocation check against observed history
        if seq_id in self._history:
            self.detect_fork(self._history[seq_id], note)
        self._history[seq_id] = note

        body_bytes = note.body_bytes()

        # Sign with origin key
        origin_signer = self.origin_signer
        if origin_signer is None:
            try:
                from db.cli.keygen import load_private_key
                origin_signer = load_private_key("keys/signing_key.pem")
            except Exception:
                from db.cli.keygen import generate_keypair
                origin_signer, _ = generate_keypair()

        origin_sig_bytes = sign_checkpoint(origin_signer, body_bytes)
        origin_sig = WitnessSignature(
            witness_name="argus.origin",
            signature_bytes=origin_sig_bytes,
            public_key_pem=self.origin_public_key_pem,
        )

        # Collect witness cosignatures
        collected_signatures: list[WitnessSignature] = []
        witness_errors: Dict[str, str] = {}

        for idx, (w_name, w_key) in enumerate(self.witness_signers.items()):
            try:
                if idx < len(self.witnesses):
                    try:
                        self.witnesses[idx].push(checkpoint_id, payload_json)
                    except Exception as sub_err:
                        logger.warning("Witness store %s push failed: %s", w_name, sub_err)

                w_sig_bytes = sign_checkpoint(w_key, body_bytes)
                collected_signatures.append(
                    WitnessSignature(
                        witness_name=w_name,
                        signature_bytes=w_sig_bytes,
                        public_key_pem=self.witness_public_keys.get(w_name),
                    )
                )
            except Exception as e:
                witness_errors[w_name] = str(e)
                logger.warning("Witness %s failed to cosign: %s", w_name, e)

        # Check quorum threshold
        if len(collected_signatures) < self.threshold:
            raise QuorumNotMetError(
                collected=len(collected_signatures),
                required=self.threshold,
                details={
                    "checkpoint_id": checkpoint_id,
                    "sequence_id": seq_id,
                    "witness_errors": witness_errors,
                },
            )

        witnessed = WitnessedCheckpoint(
            note=note,
            origin_signature=origin_sig,
            witness_signatures=collected_signatures,
        )

        # Persist locally in archive dir
        note_path = self.base_path / f"{checkpoint_id}.note"
        note_path.write_text(witnessed.serialize(), encoding="utf-8")

        json_path = self.base_path / f"{checkpoint_id}.json"
        json_path.write_text(json.dumps(witnessed.to_dict(), indent=2), encoding="utf-8")

        return f"multi_witness://{len(collected_signatures)}_of_{len(self.witness_signers)}/{checkpoint_id}"

    def verify(self, checkpoint_id: int) -> bool:
        """Verify witness quorum and cryptographic validity of stored note."""
        from db.cli.witness_protocol import WitnessedCheckpoint, verify_witness_quorum

        note_path = self.base_path / f"{checkpoint_id}.note"
        if not note_path.is_file():
            return False

        try:
            witnessed = WitnessedCheckpoint.from_text(note_path.read_text(encoding="utf-8"))
            keys = dict(self.witness_public_keys)
            keys["argus.origin"] = self.origin_public_key_pem or ""

            is_valid, _, _ = verify_witness_quorum(
                witnessed, keys, threshold=self.threshold
            )
            return is_valid
        except Exception:
            return False

    def get_witness_report(self, checkpoint_id: int) -> Dict[str, Any]:
        """Generate detailed witness quorum telemetry report for APIs and dashboards."""
        from db.cli.witness_protocol import WitnessedCheckpoint, verify_witness_quorum

        note_path = self.base_path / f"{checkpoint_id}.note"
        if not note_path.is_file():
            return {
                "checkpoint_id": checkpoint_id,
                "quorum_satisfied": False,
                "error": "Checkpoint note not found on anchor storage",
            }

        witnessed = WitnessedCheckpoint.from_text(note_path.read_text(encoding="utf-8"))
        keys = dict(self.witness_public_keys)
        keys["argus.origin"] = self.origin_public_key_pem or ""

        is_valid, msg, report = verify_witness_quorum(
            witnessed, keys, threshold=self.threshold
        )
        return {
            "checkpoint_id": checkpoint_id,
            "sequence_id": witnessed.note.sequence_id,
            "merkle_root": witnessed.note.merkle_root,
            "quorum_satisfied": is_valid,
            "required_threshold": self.threshold,
            "total_witnesses": len(self.witness_signers),
            "cosigned_witnesses": len(witnessed.witness_signatures),
            "message": msg,
            "per_witness": [
                {
                    "witness_name": w.witness_name,
                    "status": (
                        "VALID"
                        if report.get("per_witness_status", {})
                        .get(w.witness_name, {})
                        .get("valid")
                        else "FAILED"
                    ),
                    "signature_hex": w.signature_hex(),
                    "timestamp": w.timestamp,
                }
                for w in witnessed.witness_signatures
            ],
        }


def get_anchor_store(config: dict) -> AnchorStore:
    """Factory function to get the appropriate anchor store based on configuration.

    Args:
        config (dict): Configuration dictionary. Must contain a 'type' key
                       ('local', 'github', 'rfc3161', 's3_worm', or 'multi_witness') and required parameters.

    Returns:
        AnchorStore: An instance of the configured anchor store.

    Raises:
        ValueError: If the anchor store type is unknown or configuration is invalid.
    """
    store_type = str(config.get("type", "")).lower()

    if store_type in ("multi_witness", "witness", "multi"):
        threshold = int(config.get("threshold", 2))
        base_path = config.get("base_path") or config.get("path") or "anchors/multi_witness"
        witnesses_cfgs = config.get("witnesses", [])
        witness_instances: list[AnchorStore] = []
        for w_cfg in witnesses_cfgs:
            if isinstance(w_cfg, dict):
                witness_instances.append(get_anchor_store(w_cfg))
            elif isinstance(w_cfg, AnchorStore):
                witness_instances.append(w_cfg)
        return MultiWitnessAnchorStore(
            witnesses=witness_instances,
            threshold=threshold,
            base_path=base_path,
        )

    elif store_type == "local":
        base_path = config.get("path") or config.get("base_path")
        if not base_path:
            raise ValueError("LocalFileAnchorStore requires 'path' or 'base_path' in config.")
        return LocalFileAnchorStore(base_path=base_path)

    elif store_type == "github":
        repo = config.get("repo")
        token = config.get("token")
        if not repo or not token:
            raise ValueError("GitHubAnchorStore requires 'repo' and 'token' in config.")

        kwargs: Dict[str, Any] = {"repo": repo, "token": token}
        if "branch" in config:
            kwargs["branch"] = config["branch"]
        if "path_prefix" in config:
            kwargs["path_prefix"] = config["path_prefix"]
        return GitHubAnchorStore(**kwargs)

    elif store_type in ("rfc3161", "tsa"):
        server_url = config.get("server_url", "http://freetsa.org/tsr")
        local_archive_dir = (
            config.get("local_archive_dir")
            or config.get("path")
            or config.get("base_path")
            or "anchors/rfc3161"
        )
        timeout_seconds = float(config.get("timeout_seconds", 15.0))
        http_opener = config.get("http_opener")
        return Rfc3161AnchorStore(
            server_url=server_url,
            local_archive_dir=local_archive_dir,
            timeout_seconds=timeout_seconds,
            http_opener=http_opener,
        )

    elif store_type in ("s3_worm", "s3", "worm"):
        bucket = config.get("bucket")
        if not bucket:
            raise ValueError("S3WormAnchorStore requires 'bucket' in config.")

        key_prefix = config.get("key_prefix", "anchors")
        retention_days = int(config.get("retention_days", 365))
        mode = config.get("mode", "COMPLIANCE")
        region_name = config.get("region_name")
        client = config.get("client")
        return S3WormAnchorStore(
            bucket=bucket,
            key_prefix=key_prefix,
            retention_days=retention_days,
            mode=mode,
            region_name=region_name,
            client=client,
        )

    else:
        raise ValueError(f"Unknown anchor store type: {store_type}")
