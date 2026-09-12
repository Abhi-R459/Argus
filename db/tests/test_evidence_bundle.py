"""Phase 7 Acceptance Suite: Evidence Bundle Packaging & Verification (TEST-007 / 7.D.2).

Validates:
1. End-to-end evidence bundle packaging.
2. Embedded standalone verifier execution across tamper matrix.
3. Air-gapped pure-Python cryptographic verification.
"""

from db.tests.test_verify_standalone import (
    TestVerifyStandalone,
    build_synthetic_bundle,
    keypair,
)
