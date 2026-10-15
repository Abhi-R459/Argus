"""Read-only comparison of signed checkpoints with a private GitHub anchor.

The API has Contents: Read access only. Publishing is an operator action, so a
compromised API process cannot silently replace the independently held record.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import quote
import urllib.error
import urllib.request


_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_BRANCH = re.compile(r"[A-Za-z0-9_./-]+\Z")
_HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX_128 = re.compile(r"[0-9a-f]{128}\Z")
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_MANIFEST_BYTES = 1_000_000
_MAX_CHECKPOINTS = 1_000


class AnchorUnavailable(Exception):
    """The remote record could not be read or safely interpreted."""


@dataclass(frozen=True)
class AnchorComparison:
    status: str  # pass | unknown | fail
    detail: str
    anchored_sequence: int = 0
    anchored_at: str | None = None


def fetch_manifest(repo: str, token: str, branch: str = "main") -> dict[str, Any]:
    """Fetch the one bounded manifest through GitHub's Contents API.

    The token is sent only to api.github.com. Errors intentionally omit response
    bodies and credentials; a 404 can mean a missing file or unavailable access.
    """
    if not _REPOSITORY.fullmatch(repo) or not _BRANCH.fullmatch(branch) or ".." in branch:
        raise AnchorUnavailable("The private anchor repository configuration is invalid.")
    if not token:
        raise AnchorUnavailable("The private anchor read credential is unavailable.")
    url = (
        f"https://api.github.com/repos/{repo}/contents/anchors.json"
        f"?ref={quote(branch, safe='')}"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Argus-Read-Only-Anchor-Verifier",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AnchorUnavailable("The private anchor repository could not be read.") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise AnchorUnavailable("The private anchor response exceeds the size limit.")
    try:
        item = json.loads(raw)
        if not isinstance(item, dict) or item.get("type") != "file" or item.get("encoding") != "base64":
            raise ValueError("invalid Contents response")
        encoded = item["content"]
        if not isinstance(encoded, str):
            raise ValueError("missing content")
        decoded = base64.b64decode("".join(encoded.split()), validate=True)
        if len(decoded) > _MAX_MANIFEST_BYTES:
            raise ValueError("manifest too large")
        manifest = json.loads(decoded)
        if not isinstance(manifest, dict):
            raise ValueError("manifest is not an object")
        return manifest
    except (KeyError, UnicodeError, ValueError, TypeError, binascii.Error) as exc:
        raise AnchorUnavailable("The private anchor record is malformed or too large.") from exc


def compare_manifest(
    database_checkpoints: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    *,
    minimum_sequence: int = 0,
) -> AnchorComparison:
    """Compare every externally published checkpoint to the database rows.

    A well-formed remote prefix means a newly created checkpoint is pending
    publication. A changed or missing previously published row is a mismatch.
    The configured minimum prevents a truncation below the launch baseline from
    being mistaken for ordinary publication lag.
    """
    remote = manifest.get("checkpoints")
    if manifest.get("schema_version") != 1 or not isinstance(remote, list):
        return AnchorComparison("unknown", "The private anchor manifest format is unsupported.")
    if not remote or len(remote) > _MAX_CHECKPOINTS:
        return AnchorComparison("unknown", "The private anchor has no usable checkpoints.")
    prior_id = prior_sequence = 0
    for item in remote:
        if not isinstance(item, dict):
            return AnchorComparison("unknown", "A private anchor record is malformed.")
        checkpoint_id = item.get("checkpoint_id")
        sequence_id = item.get("sequence_id")
        if (
            type(checkpoint_id) is not int or checkpoint_id <= prior_id
            or type(sequence_id) is not int or sequence_id <= prior_sequence
            or not isinstance(item.get("checkpoint_hash"), str)
            or not _HEX_64.fullmatch(item["checkpoint_hash"])
            or not isinstance(item.get("merkle_root"), str)
            or not _HEX_64.fullmatch(item["merkle_root"])
            or not isinstance(item.get("signature_hex"), str)
            or not _HEX_128.fullmatch(item["signature_hex"])
            or not isinstance(item.get("key_id"), str)
        ):
            return AnchorComparison("unknown", "A private anchor record is malformed.")
        prior_id, prior_sequence = checkpoint_id, sequence_id

    latest = remote[-1]
    latest_seq = latest["sequence_id"]
    anchored_at = manifest.get("published_at")
    if not isinstance(anchored_at, str):
        anchored_at = None
    if latest_seq < minimum_sequence:
        return AnchorComparison(
            "fail", "The private anchor is older than the required published baseline.",
            latest_seq, anchored_at,
        )
    if len(remote) > len(database_checkpoints):
        return AnchorComparison(
            "fail", "A previously published checkpoint is missing from the database.",
            latest_seq, anchored_at,
        )
    for external, local in zip(remote, database_checkpoints):
        comparable = (
            "checkpoint_id", "sequence_id", "checkpoint_hash", "merkle_root",
            "signature_hex", "key_id",
        )
        if any(external[field] != local.get(field) for field in comparable):
            return AnchorComparison(
                "fail", f"Private anchor record disagrees with checkpoint {external['checkpoint_id']}.",
                latest_seq, anchored_at,
            )
    if len(remote) < len(database_checkpoints):
        return AnchorComparison(
            "unknown", "New signed checkpoints are awaiting publication to the private anchor.",
            latest_seq, anchored_at,
        )
    return AnchorComparison(
        "pass", "All signed checkpoints match the independently held private anchor.",
        latest_seq, anchored_at,
    )


def checkpoint_row(
    checkpoint_id: int, sequence_id: int, checkpoint_hash: str,
    merkle_root: str, signature: bytes, key_id: str | None,
) -> dict[str, Any]:
    return {
        "checkpoint_id": int(checkpoint_id),
        "sequence_id": int(sequence_id),
        "checkpoint_hash": str(checkpoint_hash),
        "merkle_root": str(merkle_root),
        "signature_hex": bytes(signature).hex(),
        "key_id": key_id or "",
    }
