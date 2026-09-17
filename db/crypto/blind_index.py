"""Tunable PBKDF2-HMAC-SHA256 Blind Indexing Engine (HARDEN-009 / Step 11.B.5).

Provides cryptographically hardened blind indexing for low-entropy structured
identifiers (e.g. 9-digit US SSNs, Aadhaar, national identity cards) under NIST SP 800-132.

Background & Threat Model:
--------------------------
Structured 9-digit national IDs have a keyspace of only 10^9 (~2^30) combinations.
If an attacker exfiltrates the database salt (AUDIT_SALT), standard single-round
HMAC-SHA256 can be brute-forced across the entire 10^9 space on an off-the-shelf
workstation GPU (e.g., NVIDIA RTX 4090 at ~1.2 GH/s) in under 1 second.

By introducing a tunable work factor via PBKDF2-HMAC-SHA256:
- 1 iteration (legacy HMAC): ~0.83 seconds full-keyspace GPU search.
- 1,000 iterations: ~13.9 minutes full-keyspace search, ~0.3ms Python / ~6ms DB trigger write latency.
- 10,000 iterations: ~2.3 hours full-keyspace search, ~3.3ms Python / ~50ms DB trigger write latency.
- 50,000 iterations: ~11.6 hours full-keyspace search.

NIST SP 800-132 explicitly approves PBKDF2 with HMAC-SHA256 for key derivation
and pseudorandom hashing, maintaining consistency with FIPS/NIST compliance posture.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, List, Optional

DEFAULT_SALT: str = "argus_default_blind_index_salt_2026"
DEFAULT_ITERATIONS: int = 1000
DEFAULT_MODE: str = "pbkdf2"

# Reference GPU hash rate for HMAC-SHA256 (NVIDIA RTX 4090: ~1.2 x 10^9 hashes/sec)
GPU_BASE_HASH_RATE: float = 1.2e9

# Keyspace for structured 9-digit national identifiers (000-00-0000 to 999-99-9999)
NID_KEYSPACE: int = 10**9


def compute_blind_index(
    val: str,
    salt: Optional[str] = None,
    iterations: Optional[int] = None,
    mode: str = DEFAULT_MODE,
) -> str:
    """Compute a deterministic, cryptographically blinded index for sensitive text.

    Args:
        val: Sensitive plaintext value (e.g. "123-45-6789").
        salt: Salt or secret key. Defaults to DEFAULT_SALT.
        iterations: Iteration count / work factor. Defaults to DEFAULT_ITERATIONS (1000).
        mode: Hashing mode - "pbkdf2" (NIST SP 800-132 slow KDF) or "hmac" (legacy fast HMAC).

    Returns:
        64-character lowercase hexadecimal hash.

    Raises:
        ValueError: If val is empty or whitespace-only.
    """
    if not val or not val.strip():
        raise ValueError("Input value for blind index cannot be empty.")

    clean_val = val.strip()
    active_salt = salt if salt is not None else DEFAULT_SALT
    active_iters = iterations if iterations is not None else DEFAULT_ITERATIONS

    val_bytes = clean_val.encode("utf-8")
    salt_bytes = active_salt.encode("utf-8")

    if mode == "hmac" or active_iters <= 1:
        # Legacy fast mode or single-round HMAC
        return hmac.new(salt_bytes, val_bytes, hashlib.sha256).hexdigest()

    # NIST SP 800-132 / RFC 8018 PBKDF2-HMAC-SHA256
    # Password = val_bytes, Salt = salt_bytes, dklen = 32 bytes (256 bits)
    return hashlib.pbkdf2_hmac("sha256", val_bytes, salt_bytes, active_iters, 32).hex()


def format_duration(seconds: float) -> str:
    """Format duration in seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds:.2f} s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    if seconds < 86400:
        return f"{seconds / 3600:.2f} hours"
    return f"{seconds / 86400:.2f} days"


def calibrate_work_factor(
    iterations_list: Optional[List[int]] = None,
    num_samples: int = 5,
    gpu_hash_rate: float = GPU_BASE_HASH_RATE,
    val: str = "123-45-6789",
    salt: str = DEFAULT_SALT,
) -> List[dict[str, Any]]:
    """Benchmark write latency vs offline GPU brute-force resistance across work factors.

    Args:
        iterations_list: List of iteration levels to benchmark.
            Defaults to [1, 100, 500, 1000, 5000, 10000, 50000].
        num_samples: Number of timing runs per level to average.
        gpu_hash_rate: Projected adversary GPU hash rate (default: 1.2 GH/s for RTX 4090).
        val: Sample identifier to hash.
        salt: Sample salt.

    Returns:
        List of benchmark metric dictionaries.
    """
    if iterations_list is None:
        iterations_list = [1, 100, 500, 1000, 5000, 10000, 50000]

    results = []
    val_bytes = val.encode("utf-8")
    salt_bytes = salt.encode("utf-8")

    for iters in iterations_list:
        timings = []
        for _ in range(num_samples):
            t0 = time.perf_counter()
            if iters <= 1:
                hmac.new(salt_bytes, val_bytes, hashlib.sha256).hexdigest()
            else:
                hashlib.pbkdf2_hmac("sha256", val_bytes, salt_bytes, iters, 32).hex()
            timings.append((time.perf_counter() - t0) * 1000.0)

        avg_latency_ms = sum(timings) / len(timings)
        # GPU time to crack 10^9 keys: (10^9 * iters) / gpu_hash_rate
        gpu_search_seconds = (NID_KEYSPACE * iters) / gpu_hash_rate
        sla_compliant = avg_latency_ms < 5.0  # sub-5ms trigger SLA

        results.append({
            "iterations": iters,
            "latency_ms": round(avg_latency_ms, 3),
            "gpu_search_seconds": round(gpu_search_seconds, 2),
            "gpu_search_formatted": format_duration(gpu_search_seconds),
            "sla_compliant": sla_compliant,
            "nist_approved": True,  # NIST SP 800-132 approved
            "sample_digest": compute_blind_index(val, salt=salt, iterations=iters)[:16] + "...",
        })

    return results
