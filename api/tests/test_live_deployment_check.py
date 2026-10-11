"""Ensure the public release check fails on access leaks and invalid TLS URLs."""

import argparse
from email.message import Message
import json

import pytest

from scripts import check_live_deployment as checks


def response(status, body, content_type="application/json"):
    headers = Message()
    for key, value in {
        "Content-Type": content_type, "Cache-Control": "no-store",
        "Strict-Transport-Security": "max-age=31536000",
        "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
    }.items():
        headers[key] = value
    return status, headers, body


@pytest.mark.parametrize("origin", [
    "http://app.example.com", "https://user:password@app.example.com",
    "https://app.example.com/api", "https://app.example.com?token=secret",
    "https://app.example.com#fragment", "https://app.example.com:invalid",
])
def test_public_check_rejects_unsafe_origins(origin):
    with pytest.raises(argparse.ArgumentTypeError):
        checks.https_origin(origin)


@pytest.mark.parametrize("leak", [False, True])
def test_public_check_detects_anonymous_employee_leak(monkeypatch, capsys, leak):
    def fetch(opener, url, timeout, method="GET", headers=None, data=None):
        assert method in {"GET", "OPTIONS", "POST"}
        if method == "POST":
            assert url.endswith("/api/audit-logs/search") and data == b"{}"
        if method == "OPTIONS":
            status, out_headers, body = response(200, b"")
            if headers["Origin"] == "https://app.example.com":
                out_headers["Access-Control-Allow-Origin"] = headers["Origin"]
            return status, out_headers, body
        if url.endswith("/api/health/ready"):
            return response(200, b'{"status":"ready"}')
        if url.endswith(("/docs", "/redoc", "/openapi.json")):
            return response(404, b'{"detail":"Not Found"}')
        if "/api/" in url:
            if leak and url.endswith("/api/employees"):
                return response(200, json.dumps({"national_id": "must-not-be-printed"}).encode())
            return response(401, b'{"detail":"Not authenticated"}')
        return response(200, b'<html><div id="root"></div></html>', "text/html")

    monkeypatch.setattr(checks, "request", fetch)
    assert checks.main(["--frontend-origin", "https://app.example.com",
                        "--api-origin", "https://api.example.com"]) == int(leak)
    assert "must-not-be-printed" not in capsys.readouterr().out


def test_public_check_does_not_follow_redirects():
    assert checks.NoRedirects().redirect_request(None, None, 302, None, None, "http://insecure.invalid") is None


def test_html_authentication_proxy_is_not_a_successful_denial():
    assert not checks.protected_response(*response(401, b"<html>Sign in</html>", "text/html"))
