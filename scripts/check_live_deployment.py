"""Read-only checks for the public Argus frontend and API after deployment.

Uses no credentials and makes no business writes. Passing these checks does
not replace testing real Clerk sign-in, roles, workflows, or backup recovery.
"""

import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def https_origin(value):
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname and not parsed.username
                 and not parsed.password and not parsed.query and not parsed.fragment
                 and parsed.path in ("", "/") and parsed.port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError("Use an exact HTTPS origin without credentials or a path.")
    return value.rstrip("/")


def request(opener, url, timeout, method="GET", headers=None):
    req = Request(url, method=method, headers={"User-Agent": "Argus-Launch-Check/1.0", **(headers or {})})
    try:
        response = opener.open(req, timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        # Reject oversized responses; never print response bodies or headers.
        body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ValueError("Response exceeded the check's size limit.")
        return response.status, response.headers, body


def json_status(body, expected):
    try:
        return json.loads(body) == {"status": expected}
    except (ValueError, UnicodeDecodeError):
        return False


def protected_response(status, headers, body):
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return False
    return (status == 401 and isinstance(payload, dict) and isinstance(payload.get("detail"), str)
            and "application/json" in headers.get("Content-Type", "").lower()
            and "no-store" in headers.get("Cache-Control", "").lower())


def security_headers(headers):
    hsts = re.search(r"(?:^|;)\s*max-age=(\d+)(?:;|$)", headers.get("Strict-Transport-Security", ""), re.I)
    return (headers.get("X-Content-Type-Options", "").lower() == "nosniff"
            and headers.get("X-Frame-Options", "").upper() == "DENY"
            and hsts is not None and int(hsts[1]) >= 31536000)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-origin", required=True, type=https_origin)
    parser.add_argument("--api-origin", required=True, type=https_origin)
    parser.add_argument("--timeout", type=int, default=90, help="Seconds per request, 5 to 120; allows a free host to wake.")
    args = parser.parse_args(argv)
    if not 5 <= args.timeout <= 120:
        parser.error("Timeout must be between 5 and 120 seconds.")
    opener = build_opener(NoRedirects())
    failures = 0

    def check(label, passed):
        nonlocal failures
        print(("PASS" if passed else "FAIL") + ": " + label)
        failures += not passed

    try:
        status, headers, body = request(opener, args.api_origin + "/api/health/ready", args.timeout)
        check("API readiness and runtime database roles", status == 200 and json_status(body, "ready"))
        check("API transport and privacy headers", security_headers(headers)
              and "no-store" in headers.get("Cache-Control", "").lower())
        for path in ("/", "/hr/settings", "/auditor/audit-chain"):
            status, headers, body = request(opener, args.frontend_origin + path, args.timeout)
            check("Frontend route " + path, status == 200 and "text/html" in headers.get("Content-Type", "").lower()
                  and b'id="root"' in body and security_headers(headers)
                  and ("no-cache" in headers.get("Cache-Control", "").lower()
                       or "no-store" in headers.get("Cache-Control", "").lower()))
        for path in ("/api/employees", "/api/audit-logs", "/api/auth/me"):
            check("Anonymous access denied for " + path,
                  protected_response(*request(opener, args.api_origin + path, args.timeout)))
        check("Invalid authentication token denied", protected_response(*request(
            opener, args.api_origin + "/api/auth/me", args.timeout,
            headers={"Authorization": "Bearer argus-launch-check-invalid-token"})))
        for path in ("/docs", "/redoc", "/openapi.json"):
            status, _, _ = request(opener, args.api_origin + path, args.timeout)
            check("Development documentation disabled at " + path, status == 404)
        preflight = {"Origin": args.frontend_origin, "Access-Control-Request-Method": "GET",
                     "Access-Control-Request-Headers": "authorization"}
        status, headers, _ = request(opener, args.api_origin + "/api/employees", args.timeout,
                                     method="OPTIONS", headers=preflight)
        check("Frontend origin allowed by API", status == 200
              and headers.get("Access-Control-Allow-Origin") == args.frontend_origin)
        preflight["Origin"] = "https://untrusted-origin.invalid"
        _, headers, _ = request(opener, args.api_origin + "/api/employees", args.timeout,
                                 method="OPTIONS", headers=preflight)
        check("Untrusted origin denied by API", "Access-Control-Allow-Origin" not in headers)
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        # Exceptions may contain network addresses or response data. Report
        # only the type and fail closed, without disabling TLS verification.
        print("FAIL: Deployment check interrupted (" + type(exc).__name__ + ").", file=sys.stderr)
        return 1
    if failures:
        print("Release checks failed; resolve the failures before inviting users.")
        return 1
    print("Public checks passed. Real sign-in, authorized workflows and recovery still require verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
