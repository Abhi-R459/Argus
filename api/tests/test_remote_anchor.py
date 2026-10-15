"""Private remote-anchor read-back and mismatch behavior."""

import base64
import json
from unittest.mock import patch

from api.services.remote_anchor import _NoRedirect, AnchorUnavailable, compare_manifest, fetch_manifest
import pytest


def _checkpoint(checkpoint_id=1, sequence_id=5):
    return {
        "checkpoint_id": checkpoint_id,
        "sequence_id": sequence_id,
        "checkpoint_hash": "a" * 64,
        "merkle_root": "b" * 64,
        "signature_hex": "c" * 128,
        "key_id": "local:ed25519:v1",
    }


def test_private_manifest_comparison_covers_all_published_checkpoints():
    first = _checkpoint()
    second = _checkpoint(2, 10)
    manifest = {"schema_version": 1, "published_at": "2026-10-15T00:00:00Z", "checkpoints": [first, second]}
    assert compare_manifest([first, second], manifest, minimum_sequence=5).status == "pass"
    assert compare_manifest([first], manifest).status == "fail"  # Database rollback.
    assert compare_manifest([first, second, _checkpoint(3, 15)], manifest).status == "unknown"
    assert compare_manifest([first, second], manifest, minimum_sequence=11).status == "fail"
    changed = {**second, "checkpoint_hash": "d" * 64}
    assert compare_manifest([first, changed], manifest).status == "fail"
    assert compare_manifest([first, second], {**manifest, "checkpoints": [second, first]}).status == "unknown"


def test_private_manifest_fetch_uses_only_read_scope(monkeypatch):
    manifest = {"schema_version": 1, "checkpoints": [_checkpoint()]}
    envelope = {
        "type": "file", "encoding": "base64",
        "content": base64.b64encode(json.dumps(manifest).encode()).decode(),
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(envelope).encode()

    def open_request(request, timeout):
        assert request.full_url == "https://api.github.com/repos/example/anchors/contents/anchors.json?ref=main"
        assert request.get_header("Authorization") == "Bearer read-only-secret"
        assert request.get_method() == "GET"
        assert timeout == 8
        return Response()

    class Opener:
        def open(self, request, timeout):
            return open_request(request, timeout)

    with patch("api.services.remote_anchor.urllib.request.build_opener", return_value=Opener()):
        assert fetch_manifest("example/anchors", "read-only-secret") == manifest


def test_private_manifest_never_redirects_a_read_token():
    with pytest.raises(AnchorUnavailable, match="redirected unexpectedly"):
        _NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://other.example/")
