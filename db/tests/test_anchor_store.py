"""Comprehensive unit tests for Argus Pluggable External Anchor Stores (HARDEN-010).

Covers:
1. ASN.1 DER primitives (length encoding/decoding, TLV parsing).
2. RFC 3161 TimeStampReq construction and TimeStampResp parsing.
3. LocalFileAnchorStore (push, verify, corruption handling).
4. GitHubAnchorStore (mocked GitHub API responses, base64 decoding, branch handling).
5. Rfc3161AnchorStore (mocked TSA responses, FreeTSA disclaimer, rejection handling).
6. S3WormAnchorStore (mocked boto3 S3 client, Object Lock COMPLIANCE mode, retention date verification).
7. get_anchor_store factory across all provider types and error conditions.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Dict
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from db.cli.anchor_store import (
    AnchorStore,
    FREETSA_DISCLAIMER,
    GitHubAnchorStore,
    LocalFileAnchorStore,
    Rfc3161AnchorStore,
    S3WormAnchorStore,
    build_rfc3161_request,
    decode_der_length,
    decode_der_tlv,
    encode_der_length,
    get_anchor_store,
    parse_rfc3161_response,
)


# ==============================================================================
# 1. ASN.1 DER Utility Tests
# ==============================================================================

class TestDerUtilities:
    """Validates pure-Python ASN.1 DER encoder and decoder implementations."""

    def test_encode_decode_short_length(self):
        """Short lengths (< 128) must encode as a single byte."""
        for length in (0, 1, 42, 127):
            encoded = encode_der_length(length)
            assert len(encoded) == 1
            assert encoded[0] == length

            decoded, next_off = decode_der_length(encoded, 0)
            assert decoded == length
            assert next_off == 1

    def test_encode_decode_long_length(self):
        """Long lengths (>= 128) must encode as 0x80 | num_bytes followed by big-endian bytes."""
        test_lengths = [128, 255, 256, 1024, 65535, 70000]
        for length in test_lengths:
            encoded = encode_der_length(length)
            assert encoded[0] & 0x80 == 0x80
            decoded, next_off = decode_der_length(encoded, 0)
            assert decoded == length
            assert next_off == len(encoded)

    def test_decode_der_length_errors(self):
        """EOF and truncated length fields must raise ValueError."""
        with pytest.raises(ValueError, match="Unexpected EOF"):
            decode_der_length(b"", 0)

        # 0x82 indicates 2 length bytes follow, but buffer ends
        with pytest.raises(ValueError, match="Invalid DER length"):
            decode_der_length(bytes([0x82, 0x01]), 0)

    def test_decode_der_tlv(self):
        """TLV decoder correctly extracts tag, value, and next offset."""
        # Tag 0x04 (OCTET STRING), length 4, data b"test"
        sample = bytes([0x04, 0x04]) + b"test"
        tag, val, next_off = decode_der_tlv(sample, 0)
        assert tag == 0x04
        assert val == b"test"
        assert next_off == 6

        # Out-of-bounds TLV content
        with pytest.raises(ValueError, match="extends beyond data buffer"):
            decode_der_tlv(bytes([0x04, 0x10, 0x01, 0x02]), 0)


# ==============================================================================
# 2. RFC 3161 Request and Response Tests
# ==============================================================================

class TestRfc3161DerProtocols:
    """Validates RFC 3161 TimeStampReq generation and TimeStampResp parsing."""

    def test_build_rfc3161_request_exact_sha256(self):
        """Builds valid RFC 3161 TimeStampReq DER sequence of 59 bytes."""
        digest = hashlib.sha256(b"argus-checkpoint-digest").digest()
        req_der = build_rfc3161_request(digest, cert_req=True)

        assert len(req_der) == 59
        # First byte SEQUENCE
        assert req_der[0] == 0x30
        assert req_der[1] == 57

        # Verify digest rejection if not 32 bytes
        with pytest.raises(ValueError, match="Expected 32-byte SHA-256 digest"):
            build_rfc3161_request(b"short", cert_req=True)

    def test_parse_rfc3161_response_success(self):
        """Parses mock granted TimeStampResp containing PKIStatus 0 and token bytes."""
        # Status SEQUENCE { INTEGER(0) }
        status_seq = bytes([0x30, 0x03, 0x02, 0x01, 0x00])
        # Token SEQUENCE { OCTET STRING(b'notarized-tsa-token') }
        token_content = b"notarized-tsa-token"
        token_seq = bytes([0x30, len(token_content) + 2, 0x04, len(token_content)]) + token_content
        resp_der = bytes([0x30, len(status_seq + token_seq)]) + status_seq + token_seq

        status, token_bytes = parse_rfc3161_response(resp_der)
        assert status == 0
        assert token_bytes == token_seq

    def test_parse_rfc3161_response_rejection(self):
        """Parses mock rejection TimeStampResp (PKIStatus 2)."""
        # Status SEQUENCE { INTEGER(2) }
        status_seq = bytes([0x30, 0x03, 0x02, 0x01, 0x02])
        resp_der = bytes([0x30, len(status_seq)]) + status_seq

        status, token_bytes = parse_rfc3161_response(resp_der)
        assert status == 2
        assert token_bytes == b""

    def test_parse_rfc3161_response_malformed(self):
        """Malformed DER responses must raise ValueError."""
        with pytest.raises(ValueError, match="Expected SEQUENCE tag 0x30"):
            parse_rfc3161_response(bytes([0x04, 0x02, 0x00, 0x00]))


# ==============================================================================
# 3. LocalFileAnchorStore Tests
# ==============================================================================

class TestLocalFileAnchorStore:
    """Tests baseline filesystem anchor store."""

    def test_push_and_verify(self, tmp_path: Path):
        store = LocalFileAnchorStore(str(tmp_path))
        payload = json.dumps({"checkpoint_id": 10, "checkpoint_hash": "a" * 64})

        ref = store.push(10, payload)
        assert Path(ref).exists()
        assert store.verify(10) is True

    def test_verify_missing_or_corrupt(self, tmp_path: Path):
        store = LocalFileAnchorStore(str(tmp_path))
        assert store.verify(999) is False

        # Corrupt JSON
        corrupt_file = tmp_path / "11.json"
        corrupt_file.write_text("not-valid-json{", encoding="utf-8")
        assert store.verify(11) is False


# ==============================================================================
# 4. GitHubAnchorStore Tests
# ==============================================================================

class TestGitHubAnchorStore:
    """Tests GitHub repository anchor store with mocked HTTP."""

    def test_push_success(self):
        store = GitHubAnchorStore(repo="argus-org/anchors", token="ghp_secret", branch="main")
        payload = json.dumps({"checkpoint_id": 1, "hash": "c" * 64})

        # Mock urllib.request.urlopen
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "content": {"html_url": "https://github.com/argus-org/anchors/blob/main/anchors/1.json"}
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        # Mock GET returning 404 (file does not exist yet), then PUT succeeds
        with patch("urllib.request.urlopen") as mock_urlopen:
            # First call raises HTTPError 404 (no existing sha)
            err = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
            mock_urlopen.side_effect = [err, mock_response]

            url = store.push(1, payload)
            assert "https://github.com" in url
            assert mock_urlopen.call_count == 2

    def test_verify_success_and_failure(self):
        store = GitHubAnchorStore(repo="argus-org/anchors", token="ghp_secret")
        payload = json.dumps({"checkpoint_id": 1})
        b64_content = base64.b64encode(payload.encode("utf-8")).decode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"content": b64_content}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert store.verify(1) is True

        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None)):
            assert store.verify(1) is False


# ==============================================================================
# 5. Rfc3161AnchorStore Tests (FreeTSA & Disclaimers)
# ==============================================================================

class TestRfc3161AnchorStore:
    """Tests RFC 3161 TSA client and FreeTSA disclaimer verification."""

    def _create_mock_tsa_reply(self, status: int = 0) -> bytes:
        status_seq = bytes([0x30, 0x03, 0x02, 0x01, status])
        token_content = b"sample-notarized-tsr-data"
        token_seq = bytes([0x30, len(token_content) + 2, 0x04, len(token_content)]) + token_content
        return bytes([0x30, len(status_seq + token_seq)]) + status_seq + token_seq

    def test_freetsa_disclaimer_present(self):
        """FreeTSA disclaimer must be prominent and document non-eIDAS status."""
        assert "DISCLAIMER [DEMO / NON-PRODUCTION]" in FREETSA_DISCLAIMER
        assert "NOT an EU Qualified Trust Service Provider (QTSP)" in FREETSA_DISCLAIMER
        assert "eIDAS" in FREETSA_DISCLAIMER
        assert "DigiCert" in FREETSA_DISCLAIMER

    def test_push_and_verify_with_mock_opener(self, tmp_path: Path):
        mock_reply = self._create_mock_tsa_reply(status=0)

        def mock_opener(req):
            return mock_reply

        store = Rfc3161AnchorStore(
            server_url="http://freetsa.org/tsr",
            local_archive_dir=str(tmp_path),
            http_opener=mock_opener,
        )

        payload = json.dumps({
            "checkpoint_id": 5,
            "sequence_id": 125,
            "checkpoint_hash": "f" * 64,
        })

        tsr_path = store.push(5, payload)
        assert Path(tsr_path).exists()
        assert Path(tsr_path).suffix == ".tsr"

        # Verify companion JSON metadata
        json_path = tmp_path / "5.json"
        assert json_path.exists()
        metadata = json.loads(json_path.read_text(encoding="utf-8"))
        assert metadata["checkpoint_id"] == 5
        assert metadata["status"] == 0
        assert metadata["digest_hex"] == "f" * 64
        assert "DISCLAIMER [DEMO / NON-PRODUCTION]" in metadata["disclaimer"]

        # Verification passes
        assert store.verify(5) is True

    def test_push_rejected_by_tsa(self, tmp_path: Path):
        mock_reply = self._create_mock_tsa_reply(status=2)  # Rejection

        store = Rfc3161AnchorStore(
            server_url="http://freetsa.org/tsr",
            local_archive_dir=str(tmp_path),
            http_opener=lambda req: mock_reply,
        )

        payload = json.dumps({"checkpoint_id": 6, "checkpoint_hash": "0" * 64})
        with pytest.raises(RuntimeError, match="RFC 3161 TSA rejected timestamp request"):
            store.push(6, payload)

    def test_verify_tampered_tsr(self, tmp_path: Path):
        mock_reply = self._create_mock_tsa_reply(status=0)
        store = Rfc3161AnchorStore(
            server_url="http://freetsa.org/tsr",
            local_archive_dir=str(tmp_path),
            http_opener=lambda req: mock_reply,
        )
        payload = json.dumps({"checkpoint_id": 7, "checkpoint_hash": "1" * 64})
        store.push(7, payload)

        # Corrupt the .tsr token file
        tsr_file = tmp_path / "7.tsr"
        tsr_file.write_bytes(b"corrupted-der-token")

        assert store.verify(7) is False


# ==============================================================================
# 6. S3WormAnchorStore Tests (AWS Object Lock COMPLIANCE Mode)
# ==============================================================================

class TestS3WormAnchorStore:
    """Tests AWS S3 WORM Object Lock anchor store."""

    def test_push_calls_put_object_with_compliance_lock(self):
        mock_s3 = MagicMock()
        store = S3WormAnchorStore(
            bucket="argus-compliance-audit-vault",
            key_prefix="checkpoints/v1",
            retention_days=365,
            mode="COMPLIANCE",
            client=mock_s3,
        )

        payload = json.dumps({"checkpoint_id": 42, "checkpoint_hash": "e" * 64})
        uri = store.push(42, payload)

        assert uri == "s3://argus-compliance-audit-vault/checkpoints/v1/42.json"
        mock_s3.put_object.assert_called_once()
        _, kwargs = mock_s3.put_object.call_args

        assert kwargs["Bucket"] == "argus-compliance-audit-vault"
        assert kwargs["Key"] == "checkpoints/v1/42.json"
        assert kwargs["ContentType"] == "application/json"
        assert kwargs["ObjectLockMode"] == "COMPLIANCE"
        # Assert retention date is approximately 365 days in future
        now_utc = datetime.now(timezone.utc)
        retain_until = kwargs["ObjectLockRetainUntilDate"]
        delta = retain_until - now_utc
        assert 364 <= delta.days <= 366

    def test_verify_success_and_failure(self):
        mock_s3 = MagicMock()
        payload = json.dumps({"checkpoint_id": 42})
        mock_body = MagicMock()
        mock_body.read.return_value = payload.encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}

        store = S3WormAnchorStore(bucket="my-bucket", client=mock_s3)
        assert store.verify(42) is True

        # When object does not exist
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        assert store.verify(42) is False

    def test_missing_boto3_raises_import_error(self):
        """When boto3 is missing and no client is provided, raises helpful ImportError."""
        store = S3WormAnchorStore(bucket="my-bucket", client=None)
        with patch.dict("sys.modules", {"boto3": None}):
            with pytest.raises(ImportError, match="boto3 is required for S3WormAnchorStore"):
                store._get_client()


# ==============================================================================
# 7. get_anchor_store Factory Tests
# ==============================================================================

class TestGetAnchorStoreFactory:
    """Tests the factory configuration resolution across all anchor types."""

    def test_local_store_factory(self, tmp_path: Path):
        store = get_anchor_store({"type": "local", "path": str(tmp_path)})
        assert isinstance(store, LocalFileAnchorStore)

    def test_local_store_missing_path_raises(self):
        with pytest.raises(ValueError, match="requires 'path' or 'base_path'"):
            get_anchor_store({"type": "local"})

    def test_github_store_factory(self):
        store = get_anchor_store({"type": "github", "repo": "foo/bar", "token": "tok"})
        assert isinstance(store, GitHubAnchorStore)

    def test_github_missing_creds_raises(self):
        with pytest.raises(ValueError, match="requires 'repo' and 'token'"):
            get_anchor_store({"type": "github", "repo": "foo/bar"})

    def test_rfc3161_store_factory(self, tmp_path: Path):
        store = get_anchor_store({
            "type": "rfc3161",
            "server_url": "https://timestamp.digicert.com",
            "local_archive_dir": str(tmp_path),
        })
        assert isinstance(store, Rfc3161AnchorStore)
        assert store.server_url == "https://timestamp.digicert.com"

    def test_s3_worm_store_factory(self):
        mock_client = MagicMock()
        store = get_anchor_store({
            "type": "s3_worm",
            "bucket": "my-worm-bucket",
            "client": mock_client,
            "retention_days": 180,
        })
        assert isinstance(store, S3WormAnchorStore)
        assert store.bucket == "my-worm-bucket"
        assert store.retention_days == 180

    def test_s3_worm_missing_bucket_raises(self):
        with pytest.raises(ValueError, match="requires 'bucket'"):
            get_anchor_store({"type": "s3_worm"})

    def test_unknown_store_type_raises(self):
        with pytest.raises(ValueError, match="Unknown anchor store type: invalid_type"):
            get_anchor_store({"type": "invalid_type"})
