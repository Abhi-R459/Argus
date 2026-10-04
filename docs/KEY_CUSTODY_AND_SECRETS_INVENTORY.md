# Argus: Cryptographic Key Custody & Secrets Inventory Specification

**Document:** `docs/KEY_CUSTODY_AND_SECRETS_INVENTORY.md`  
**Standard:** NIST SP 800-57 (Recommendation for Key Management) / ISO/IEC 27001 A.10  
**Status:** Canonical Reference (Phase 11 — HARDEN-005)  

---

## 1. Executive Summary & Security Principle

Every cryptographic guarantee in Argus reduces to the fundamental security assumption:  
$$\text{Security}(S) = \text{Algorithm}_{\text{NIST}}(\text{Data}) \land \neg \text{Compromised}(\text{Key})$$

If cryptographic keys, salts, or credentials are co-located with untrusted compute or accessible to an attacker who compromises the database or application server, the mathematical protections of hash chaining, asymmetric signatures, and field-level encryption are invalidated.

This document establishes a complete, granular inventory of every cryptographic key, salt, and credential in Argus. For each asset, this specification defines:
1. **Cryptographic Algorithm & Purpose**
2. **Storage Location & Filesystem Permissions (`chmod 0600`)**
3. **Process Memory Boundary & Access Privileges**
4. **Attacker Exposure & Threat Model Mapping**
5. **Mitigation Architecture (KMS / HSM / Vault)**
6. **Key Rotation Protocol & `key_id` Marker Lifecycle**

---

## 2. Comprehensive Secrets Inventory Matrix

| Secret Identifier | Type / Algorithm | Storage Location | File Permissions | Process Boundary | Who Can Access | Threat Exposure & Impact | Production Mitigation |
|---|---|---|---|---|---|---|---|
| **`argus_private.pem`** | Asymmetric Private Key (Ed25519 / RFC 8032) | `keys/argus_private.pem` (or `ARGUS_SIGNING_KEY_PATH`) | `0600` (Owner read/write only) | Out-of-process CLI (`verifier.py`, `signer.py`) | Operator / Standalone Verifier process | If $A_{\text{app}}$ or $A_{\text{DBA}}$ exfiltrates key, they can forge valid checkpoint signatures | Move to Cloud KMS / HSM (AWS KMS asymmetric CMK, GCP KMS, Azure Key Vault, or Vault Transit engine) |
| **`argus_public.pem`** | Asymmetric Public Key (Ed25519) | `keys/argus_public.pem` & `.arguspack/manifest.json` | `0644` (World readable) | CLI, FastAPI backend, `.arguspack` bundles | Public / Regulators / Compliance Auditors | None (public verification artifact) | Distribute via DNSSEC, public key repository, or x509 certificate |
| **`AUDIT_SALT`** | Cryptographic Salt (256-bit Hex) | `.env` (`AUDIT_SALT=...`) | `0600` (Restricted `.env`) | FastAPI process & test runners | Application Backend (`api/routers/audits.py`) | If exfiltrated, attacker can enumerate low-entropy National IDs (SSNs) offline | Tunable PBKDF2 work factor (HARDEN-009) + rate-limiting on search endpoints |
| **`PGCRYPTO_KEY`** | Symmetric Secret Key (AES-256 / 256-bit passphrase) | `.env` (`PGCRYPTO_KEY=...`) | `0600` (Restricted `.env`) | Application backend & temporary SQL session | Application Backend / Database connection pool | If exfiltrated, exfiltrated disk blocks or backups can be decrypted | Envelope encryption with KMS-wrapped Data Encryption Keys (DEKs) |
| **`POSTGRES_PASSWORD`** | Superuser Credential (String) | `.env` & Docker Secrets | `0600` (Restricted `.env`) | Docker Compose / PostgreSQL daemon | Database Administrator ($A_{\text{DBA}}$) | Full DDL/DML, can drop triggers or mutate table storage | Hardened append-only triggers, immutable audit log revokes, and external anchors |
| **`HR_ADMIN_PASSWORD`** | Least-Privilege Role Credential | `db/scripts/setup_roles.sql` & `.env` | `0600` (Restricted `.env`) | FastAPI `hr_admin` connection pool | HR Admin service / Backend API | If compromised, limited to operational HR tables; blocked from modifying `audit_log` | Database-level `REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log` (HARDEN-002) |
| **`AUDITOR_PASSWORD`** | Read-Only Role Credential | `db/scripts/setup_roles.sql` & `.env` | `0600` (Restricted `.env`) | FastAPI `compliance_auditor` connection pool | Compliance Auditor service / Backend API | Read-only access to audit logs and views; zero write or raw PII access | Hard database-level read-only permissions; no operational write access |
| **`CLERK_SECRET_KEY`** | API Bearer Token (String) | `.env` (`CLERK_SECRET_KEY=...`) | `0600` (Restricted `.env`) | FastAPI authentication middleware | Backend Authentication Layer | Unauthorized issuance or verification of user session tokens | Rotate via Clerk Dashboard; IP allowlisting |
| **`GITHUB_TOKEN`** | OAuth / Personal Access Token | `.env` (`GITHUB_TOKEN=...`) | `0600` (Restricted `.env`) | Standalone CLI (`anchor_store.py`) | Out-of-band Anchor Sync process | Can mutate commit history in git anchor repository | Fine-grained PAT restricted strictly to target anchor repo with commit-only scope |
| **`AWS_SECRET_ACCESS_KEY`** | IAM Cloud Credential | Environment / IAM Role | `0600` (Restricted `.env`) | Standalone CLI (`anchor_store.py`) | Out-of-band Anchor Sync process | Unauthorized access to S3 bucket | AWS IAM Roles for Service Accounts (IRSA) / EC2 Instance Profiles; S3 Object Lock in `COMPLIANCE` mode prevents deletion even with root credentials |
| **`WITNESS_PUBLIC_KEYS`** | Public Key Registry (Ed25519) | `db/cli/witness_protocol.py` | `0644` (Application code) | Standalone CLI & FastAPI backend | Verifier, Auditors, Third-party consumers | None (Public keys used for cosigning verification) | Pinned in code registry; rotatable via RFC 9162 note versioning |
| **`ARGUSCAP_SIGNING_KEY`** | Asymmetric Ed25519 Keypair | `.arguscap/manifest.json` | `0644` (Public key in ZIP) | Standalone `verify_capsule.py` | Standalone zero-dependency verifier | None (Public key shipped with evidence bundle) | Dual-bound to root checkpoint signature and Merkle root |

---

## 3. Detailed Cryptographic Boundaries & Custody Analysis

### 3.1 Ed25519 Checkpoint Signing Key (`argus_private.pem`)
- **Mathematical Specification:** 32-byte Ed25519 seed yielding a 64-byte private key, producing 64-byte deterministic signatures over SHA-256 checkpoint digests according to RFC 8032.
- **Process Memory Boundary:**
  - The private key is **never** loaded into PostgreSQL database process memory (`postgres` daemon).
  - The private key is **never** loaded into the FastAPI web server runtime or frontend web client.
  - The key is accessed solely by the standalone CLI verifier (`python -m db.cli.verifier sign-checkpoint`) during explicit checkpoint notarization runs.
- **Development / Demonstration Mode Notice:**
  > [!WARNING]
  > In the default local development environment, `keys/argus_private.pem` is stored as an unencrypted PEM file on local disk with POSIX permissions `0600`. This mode is strictly designated **[DEV/DEMO ONLY — NOT FOR PRODUCTION]**.
- **Production Architecture (Cloud KMS / HSM):**
  In enterprise deployments, local disk key storage is replaced by an abstract signer adapter calling an HSM or cloud-managed key management service:
  ```
  ┌─────────────────────────┐          sign(hash)          ┌───────────────────────────┐
  │   Argus CLI Verifier    ├─────────────────────────────►│    Cloud KMS / HSM        │
  │   (Requests Signature)  │◄─────────────────────────────┤ (Holds Private Key in     │
  └─────────────────────────┘         64-byte sig          │  Tamper-Resistant FIPS    │
                                                           │  140-2 Level 3 Silicon)   │
                                                           └───────────────────────────┘
  ```
  Under this architecture, private key bytes **never enter host memory**, and exfiltration by a compromised host is physically and architecturally impossible.

---

### 3.2 Audit Salt (`AUDIT_SALT`) & Blind-Index Cryptanalysis Boundary
- **Mathematical Specification:** 256-bit high-entropy pseudorandom hex string used as the HMAC secret:
  $$\text{BlindIndex} = \text{HMAC-SHA256}(K_{\text{AUDIT\_SALT}}, \text{Plaintext})$$
- **Threat Model Exposure:**
  - Standard HMAC-SHA256 provides $2^{256}$ pre-image resistance against unknown keys.
  - However, for structured, low-entropy fields (such as 9-digit United States Social Security Numbers with $\approx 10^9$ possible combinations), an attacker who gains read access to `AUDIT_SALT` can precompute a rainbow table or brute-force the entire dictionary in under 15 seconds on a modern GPU.
- **Remediation & Defense-in-Depth:**
  1. **Work Factor Strengthening (HARDEN-009):** For low-entropy identifiers, Argus provides tunable PBKDF2-HMAC-SHA256 blind indexing with calibrated iteration counts ($1,000$, $10,000$, or $50,000$ iterations), elevating the dictionary search cost by several orders of magnitude while preserving sub-millisecond trigger overhead.
  2. **Audit-the-Auditor Logging:** All queries matching against `national_id_blind_index` are explicitly recorded in security telemetry logs.
  3. **Rate-Limiting:** The forensic search API endpoint is rate-limited to 10 queries per minute per authenticated auditor session.

---

### 3.3 Symmetric Master Key (`PGCRYPTO_KEY`) & Column Encryption
- **Mathematical Specification:** 256-bit symmetric key utilized by PostgreSQL `pgcrypto`'s `pgp_sym_encrypt` routine executing AES-256 in cipher feedback mode.
- **Storage & Injection Model:**
  - In development, injected via environment variable `PGCRYPTO_KEY`.
  - In production, injected per-transaction via encrypted session variable:
    ```sql
    SET LOCAL argus.encryption_key = '...';
    ```
  - Upon transaction completion or rollback, the session variable is automatically cleared from database worker memory.
- **Separation of Custody:**
  The symmetric key must never be held by the PostgreSQL database superuser. Database administrators can view encrypted `BYTEA` blocks but cannot execute `pgp_sym_decrypt()` without the runtime key injected from the trusted application tier.

---

## 4. Key Rotation Protocol with `key_id` Markers

### 4.1 Checkpoint Signing Key Rotation Lifecycle
To maintain verifiable history across decades of operation without being invalidated by scheduled key retirement or emergency compromise recovery, Argus implements `key_id` marker versioning:

```
Checkpoint #1  ─── Signed by key_id: "ed25519_2025_01" ─── Verified with Public Key 2025
Checkpoint #2  ─── Signed by key_id: "ed25519_2025_01" ─── Verified with Public Key 2025
[ KEY ROTATION EVENT — 2026-01-01 ]
Checkpoint #3  ─── Signed by key_id: "ed25519_2026_01" ─── Verified with Public Key 2026
Checkpoint #4  ─── Signed by key_id: "ed25519_2026_01" ─── Verified with Public Key 2026
```

### 4.2 Step-by-Step Rotation Protocol:
1. **Key Generation:** Generate new keypair with unique identifier:
   ```bash
   python -m db.cli.verifier keygen --key-id ed25519_2026_01 --output ./keys/
   ```
2. **Public Key Registration:** Append new public key and effective sequence boundary to the trusted keyset manifest (`keys/keyset.json`):
   ```json
   {
     "keys": [
       {
         "key_id": "ed25519_2025_01",
         "public_key": "-----BEGIN PUBLIC KEY-----\n...",
         "valid_from_sequence": 1,
         "valid_until_sequence": 25000,
         "status": "retired"
       },
       {
         "key_id": "ed25519_2026_01",
         "public_key": "-----BEGIN PUBLIC KEY-----\n...",
         "valid_from_sequence": 25001,
         "valid_until_sequence": null,
         "status": "active"
       }
     ]
   }
   ```
3. **On-Chain Checkpoint Stamping:** When creating subsequent checkpoints, `chain_checkpoints` records `key_id = 'ed25519_2026_01'`.
4. **Historical Verifier Walk:** When walking the chain, the verifier resolves the signature using the specific public key matching the checkpoint's `key_id`. Historical checkpoints remain mathematically valid indefinitely.
5. **Private Key Retirement:** The retired private key is securely zeroized from online systems and moved to offline cold storage for archival provenance.

---

## 5. Filesystem Security & Access Control Checklist

In any production deployment of Argus, operators must enforce the following POSIX filesystem permissions:

```bash
# 1. Restrict private keys to owner read-only:
chmod 0600 keys/argus_private.pem
chown argus-verifier:argus-verifier keys/argus_private.pem

# 2. Public keys world readable:
chmod 0644 keys/argus_public.pem

# 3. Restrict environment configuration:
chmod 0600 .env
chown argus-app:argus-app .env

# 4. Restrict local anchor store directory:
chmod 0700 anchors/
chown argus-verifier:argus-verifier anchors/

# 5. Restrict backup dumps:
chmod 0600 backups/*.sql
```

---

## 6. Regulatory Audit & Compliance Summary

This key custody model directly satisfies:
- **SOC 2 Trust Services Criteria CC6.1 & CC6.2:** Logical access controls over cryptographic keys and segregation of key management from database operations.
- **NIST SP 800-57 Part 1 Rev. 5:** Cryptographic key management lifecycles, key compromise recovery, and algorithm deprecation handling.
- **ISO/IEC 27001:2022 Control 8.24 (Use of Cryptography):** Documented rules for the management of cryptographic keys throughout their lifecycle.
