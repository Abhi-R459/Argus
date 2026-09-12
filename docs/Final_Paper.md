# Argus: A Native Tamper-Evident Audit Trail and Cryptographic Verification Engine for PostgreSQL

**Track:** Database Core, Security & Cryptographic Verification Engine  
**Course:** BCSE302L — Database Management Systems  
**Authors:** Abhinav (Database Core, Security & Verification Engine) & Nidhurshek (Application, API & Client Dashboard)  
**Target Submission:** Research Track / High-Assurance Database Systems  

---

## Abstract

Enterprise database management systems (RDBMS) managing sensitive human resources, payroll, and compliance records are fundamentally vulnerable to insider threats and administrative compromise. Under standard Discretionary Access Control (DAC), database superusers possess unrestricted power to execute silent, untracked `UPDATE` and `DELETE` mutations against operational tables and historical audit logs. 

We present **Argus**, a lightweight, high-throughput, and tamper-evident audit logging and verification engine implemented natively within PostgreSQL 15+. Argus enforces five-tier defense-in-depth:
1. **In-Engine Hash Chaining with 2PL Concurrency Safety:** PostgreSQL `AFTER` triggers compute SHA-256 hash chains over masked row mutations atomically within the caller's transaction, serialized via exclusive row-level locking (`SELECT ... FOR UPDATE`) on a singleton state table.
2. **Decoupled Asymmetric Checkpointing:** A standalone out-of-process verification engine aggregates intermediate hash sequences and generates digital signatures using **Ed25519 asymmetric cryptography**, publishing them to an independent external repository.
3. **High-Throughput Parallel Verification:** A keyset-paginated parallel verification engine utilizing multi-core process pools achieves a **6.19x speedup** on 8 worker cores, validating 100,000 complete audit records in under 1.9 seconds ($\approx 54,000$ entries/second) while preserving 100% boundary continuity.
4. **Privacy-Preserving Forensic Search via HMAC Blind Indexing:** Keyed HMAC-SHA256 digests over sensitive identifiers (e.g., National IDs) combined with functional B-tree indexing enable sub-millisecond forensic queries without exposing plaintext PII or compromising redaction.
5. **Portable Air-Gapped Evidence Bundles (`.arguspack`):** Turnkey evidence packages containing canonical JSONL event streams, detached Ed25519 signatures, checkpoint histories, and an embedded pure-Python RFC 8032 verifier executable without external pip dependencies.

Extensive empirical evaluations confirm that Argus introduces amortized $O(1)$ write latency overhead ($\approx 0.15\text{ ms}$ marginal cost) and maintains deterministic linear $O(N)$ verification scaling. We formally specify the threat model, algorithms, complexity bounds, failure recovery protocols, and comparative positioning against systems including SQL Server Ledger, immudb, and Hyperledger Fabric.

---

## Table of Contents
- [16.1 Research Contribution Statement](#161-research-contribution-statement)
- [16.2 Threat Model & Adversary Taxonomy](#162-threat-model--adversary-taxonomy)
- [16.3 Security Analysis (CIA Triad)](#163-security-analysis-cia-triad)
- [16.4 Formal Algorithm Specifications](#164-formal-algorithm-specifications)
- [16.5 Complexity & Asymptotic Analysis](#165-complexity--asymptotic-analysis)
- [16.6 Failure Mode & Resilience Analysis](#166-failure-mode--resilience-analysis)
- [16.7 Comprehensive Comparison Matrix](#167-comprehensive-comparison-matrix)
- [16.8 Empirical Benchmark Evaluation](#168-empirical-benchmark-evaluation)
- [16.9 Architecture & Project Mapping](#169-architecture--project-mapping)
- [16.10 Sequencing, Pedagogy & Mentorship Note](#1610-sequencing-pedagogy--mentorship-note)
- [16.11 Enterprise Auditor UX & Cross-View Forensic Navigation](#1611-enterprise-auditor-ux--cross-view-forensic-navigation)

---

## 16.1 Research Contribution Statement

Argus introduces six key contributions:
1. **In-Engine Cryptographic Hash Chaining with 2PL Concurrency Safety:** Native PL/pgSQL triggers compute SHA-256 digests over JSONB deltas with masked PII, serialized via exclusive row locking on `chain_state` (Decision #2).
2. **Asymmetric Signed Checkpoints & External Anchoring:** Out-of-band Ed25519 signing defeats the "recompute-and-hide" attack, anchoring state to external repositories (Decision #3, #8).
3. **Partitioned Parallel Verification:** Keyset-paginated workers execute concurrent internal segment checks combined with sequential boundary continuity validation (Decision #9, #15).
4. **Empirical Rigor & Attack Validation:** Validated across 100K synthetic transactions and 6 live attack scenarios with zero false negatives.
5. **In-Engine HMAC Blind Indexing for Masked Records:** Allows targeted forensic discovery by compliance auditors without decrypting PII or leaking plaintext data (Decision #23).
6. **Portable Air-Gapped Evidence Bundles (`.arguspack`):** Self-verifying evidence archives with embedded zero-dependency pure-Python verifiers (Decision #24).

---

## 16.2 Threat Model & Adversary Taxonomy

We model four adversary classes:
- **$A_{DBA}$ (Rogue Database Administrator / Superuser):** Possesses full DDL/DML capabilities within PostgreSQL, can bypass `REVOKE`, drop triggers, or edit raw table storage. *Cannot access the external verifier host or the Ed25519 private key.*
- **$A_{APP}$ (Compromised Application Backend):** Possesses standard application credentials (`hr_admin`). Bound by PostgreSQL DAC (`REVOKE UPDATE, DELETE ON audit_log`).
- **$A_{USER}$ (Malicious Insider):** Authenticated end-user restricted to API endpoints and bounded by defensive triggers (salary decrease limits, self-modification blocks).
- **$A_{NET}$ (External Network Adversary):** Remote network attacker bounded by TLS 1.3 encryption and authentication perimeters.

### Security Guarantees
- **Forward Integrity:** Altering record $R_j$ invalidates all subsequent hash links $H_k$ ($k > j$).
- **Backward Integrity & Concurrency Safety:** Exclusive locking on `chain_state` enforces linear, fork-free hash chaining.
- **Non-Repudiation:** Externally anchored Ed25519 signatures prevent undetected wholesale recomputations.
- **Zero PII Leakage:** `mask_employee_payload()` redacts sensitive encryption buffers into `"[REDACTED]"`.

---

## 16.3 Security Analysis (CIA Triad)

- **Confidentiality:** At-rest column encryption via `pgcrypto` (`national_id_encrypted`, `contact_info_encrypted`), deterministic PII masking in audit records (`[REDACTED]`), keyed HMAC-SHA256 blind indexing for queryable masked identifiers without plaintext exposure, and role-segregated views (`v_employee_directory`, `v_compliance_overview`).
- **Integrity:** In-engine hash chaining, business rule validation triggers (`trg_check_salary_decrease`, `trg_salary_history_no_self_mod`, `trg_employees_immutable_nid`), Ed25519 checkpoint signing, and turnkey `.arguspack` self-verifying evidence bundles.
- **Availability:** Non-blocking local transactions ($\approx 0.15\text{ ms}$ overhead), stateless out-of-process verification acquiring zero table locks, graceful offline queuing during external anchor partitions, and live websocket/polling dashboard synchronization.

---

## 16.4 Formal Algorithm Specifications

### Mathematical Definition
An audit log event is defined as:
$$R_i = \langle s_i, u_i, a_i, t_i, r_i, v^{old}_i, v^{new}_i, \tau_i, H^{prev}_i, H^{curr}_i \rangle$$
Serialized canonically via the pipe-delimited string $S(R_i)$ (SETUP-002), with entry digest:
$$H^{curr}_i = \text{SHA256}(S(R_i) \parallel H^{prev}_i)$$

### Invariants
1. **Strict Monotonic Sequence:** $s_i = s_{i-1} + 1$, with $s_1 = 1$.
2. **Hash Linkage:** $H^{prev}_i = H^{curr}_{i-1}$, with $H^{prev}_1 = 0^{64}$.
3. **Content Integrity:** $H^{curr}_i = \text{SHA256}(S(R_i) \parallel H^{prev}_i)$.
4. **Checkpoint Authenticity:** $\text{Ed25519Verify}(vk, H^{cp}_j, \sigma_j) = \text{True}$.

---

## 16.5 Complexity & Asymptotic Analysis

| Operation | Time Complexity | Auxiliary Space Complexity |
|---|---|---|
| **Audited Write Mutation** | $O(1)$ amortized marginal overhead | $O(1)$ per row |
| **Sequential Verification Walk** | $O(N)$ | $O(1)$ (Keyset-paginated) |
| **Checkpoint-Resumed Walk** | $O(k)$ ($k \ll N$) | $O(1)$ |
| **Parallel Segment Verification** | $O(N/P + S)$ | $O(P \cdot B)$ |
| **Historical State Reconstruction** | $O(\log N + m)$ | $O(m)$ |

---

## 16.6 Failure Mode & Resilience Analysis

Argus models and mitigates six concrete failure scenarios:
1. **Server Crash / Power Failure:** PostgreSQL WAL crash recovery guarantees atomic rollback of data mutations and audit records simultaneously.
2. **Transaction Rollback / Rule Rejection:** Sequence counter in `chain_state` rolls back with the transaction, preventing phantom entries or sequence gaps.
3. **Verifier Process Crash:** Verifier is read-only and stateless; re-running restarts verification cleanly.
4. **High Write Concurrency:** `SELECT ... FOR UPDATE` on `chain_state` enforces FIFO serialization with mathematical deadlock-freedom.
5. **Anchor Store Outage:** Core logging continues locally; checkpoints queue offline until connectivity is restored.
6. **Key Compromise:** Past checkpoints remain immutable on the external anchor store; key rotation restores forward security.

---

## 16.7 Comprehensive Comparison Matrix

| Architectural Feature | pgAudit | pgMemento | SQL Server Ledger | Argus |
|---|---|---|---|---|
| **Tamper Detection** | ❌ None | ❌ None | ✅ Merkle Tree | **✅ Linear Chain + Signed Checkpoints** |
| **PostgreSQL Native** | ✅ Extension | ✅ PL/pgSQL | ❌ SQL Server Only | **✅ Native PostgreSQL 15+** |
| **External Anchoring**| ❌ None | ❌ None | ⚠️ Unsigned Digest | **✅ Pluggable (GitHub, WORM)** |
| **Digital Signatures** | ❌ None | ❌ None | ❌ No (Digest only) | **✅ Ed25519 Asymmetric Signatures** |
| **Independent Verifier**| ❌ None | ❌ None | ⚠️ In-engine procedure | **✅ Out-of-process Python CLI** |
| **Write Overhead (P50)**| < 0.2 ms | 1–3 ms | 1–2 ms | **< 0.2 ms marginal overhead** |
| **Forensic Search on Masked PII** | ❌ None | ❌ None | ❌ Plaintext only | **✅ HMAC-SHA256 Blind Indexing** |
| **Portable Air-Gapped Evidence Bundles**| ❌ None | ❌ None | ❌ Proprietary backup | **✅ `.arguspack` with Zero-Dep Verifier** |
| **Open Source** | ✅ Yes | ✅ Yes | ❌ Proprietary | **✅ Yes (Open Source)** |

---

## 16.8 Empirical Benchmark Evaluation

### Latency Summary across Scale Levels
Write latencies measured on single-row transactions triggering complete cryptographic auditing:

| Scale Level | Operation | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| **100 rows** | INSERT | 0.68 | 0.64 | 1.12 | 1.85 |
| **10,000 rows**| INSERT | 0.78 | 0.73 | 1.38 | 2.65 |
| **100,000 rows**| INSERT | 0.85 | 0.80 | 1.62 | 3.20 |

### Parallel Verification Scaling at 100K Records
Comparing single-threaded baseline against multi-process pool verification:

| Workers ($P$) | Elapsed Time (s) | Throughput (entries/sec) | Speedup Factor | Efficiency |
|---|---|---|---|---|
| **1 Worker (Baseline)** | 11.45 s | 8,733.6 eps | **1.00x** | 100.0% |
| **2 Workers** | 6.12 s | 16,339.9 eps | **1.87x** | 93.5% |
| **4 Workers** | 3.15 s | 31,746.0 eps | **3.63x** | 90.8% |
| **8 Workers** | 1.85 s | 54,054.1 eps | **6.19x** | 77.4% |

---

## 16.9 Architecture & Project Mapping

Argus maintains strict modular separation:
- `/db/alembic/`: Declarative schema migrations establishing normalized entity tables, views, audit tables, and HMAC blind expression indexes.
- `/db/triggers/`: In-engine PL/pgSQL triggers executing hash chaining, payload masking, blind indexing, and business rules.
- `/db/cli/`: Standalone auditor CLI containing `chain_walker.py`, `hash_verifier.py`, `verify_standalone.py`, `keygen.py`, `signer.py`, `anchor_store.py`, and `backup.py`.
- `/db/bench/`: Benchmark suite generating empirical evaluation datasets and vector plots.
- `/api/routers/`: FastAPI endpoints exposing live chain visualization, anchor sync, blind index querying, and `.arguspack` streaming.
- `/frontend/src/`: React auditor dashboard with real-time hash chain visualizer, anchor health monitor, encrypted identity search, and evidence package exporter.

---

## 16.10 Sequencing, Pedagogy & Mentorship Note

Developed over an 11-week academic lifecycle, Argus serves as a pedagogical demonstration of database systems theory:
- Relational normal forms (3NF) and constraint enforcement.
- Concurrency control via Two-Phase Locking (2PL).
- Transactional atomicity and Write-Ahead Log (WAL) crash recovery.
- B-tree indexing and keyset streaming optimization.

---

## 16.11 Enterprise Auditor UX & Cross-View Forensic Navigation

A fundamental challenge in cryptographic audit architectures is bridging formal mathematical guarantees (hash chains, digital signatures, blind indexes) with operational usability for human compliance auditors. If incident alerting is fragmented across disjointed views or requires manual copy-pasting of 64-character hex digests and microsecond timestamps, the Mean Time to Investigate (MTTI) escalates, introducing operational blind spots.

Argus addresses this through a reactive, cohesive forensic navigation architecture:

1. **Global Reactive Incident State & Persistent Alerting:** Rather than isolating violation indicators to a single dashboard tab, a shared client-side hook (`useIncidentStatus()`) synthesizes real-time results from `POST /api/verify`, `GET /api/anchor/status`, and unreviewed trigger flags. When out-of-band tampering ($A_{DBA}$) or anchor divergence is detected, high-contrast crimson banners persist across all routes in `AuditorLayout.tsx` with one-click direct investigation deep-links.
2. **Dedicated Full-Page Chain Explorer (`/auditor/chain`):** Enterprise audit verification requires examining block lineages beyond small overview cards. The dedicated chain explorer exposes keyset-based pagination and centered windowing (`around_seq`), allowing auditors to jump to any sequence block, inspect cryptographic parents and entry digests, view side-by-side JSON property diffs, and inspect detached Ed25519 checkpoint signatures.
3. **Frictionless Cross-View Forensic Traversal:** All portal views adhere to a standardized query contract (`?seq=`, `?emp_id=`, `?as_of=`):
   - An alert in the persistent banner deep-links to `/auditor/chain?seq=X`, automatically windowing the chain around block $X$ and opening the Block Inspector.
   - An entry in `AuditLogTable.tsx` provides direct jumps: *"Inspect in Chain"* (`/auditor/chain?seq=X`) and *"Time-Travel to Change"* (`/auditor/time-travel?emp_id=Y&as_of=Z`).
   - A flagged violation in `RiskPanel.tsx` deep-links directly into matching audit records and visualizer nodes.
4. **Interactive Historical Time-Travel:** The `TimeTravelView.tsx` interface eliminates blind guesswork by providing a searchable employee directory dropdown coupled with a chronological mutation timeline. Auditors click any historical mutation event to automatically populate the target microsecond timestamp and invoke `reconstruct_employee_state(:emp_id, :as_of)` via PostgreSQL's $O(\log N)$ composite B-tree index.
5. **Strict Auditor Role Read-Only Purity:** To uphold formal security assumptions, the auditor portal contains zero backdoor attack injection or test endpoints. Administrative Red Team simulations are executed out-of-band via superuser CLI sockets (`db.cli.adversary`), while the compliance auditor role remains strictly read-only (`SELECT`-only permissions enforced at both the FastAPI dependency layer and PostgreSQL connection pool).

---

## References

1. Bernstein, P. A., Hadzilacos, V., & Goodman, N. (1987). *Concurrency Control and Recovery in Database Systems*. Addison-Wesley.
2. Mohan, C., Haderle, D., Lindsay, B., Pirahesh, H., & Schwarz, P. (1992). ARIES: A transaction recovery method supporting fine-granularity locking and partial rollbacks using write-ahead logging. *ACM TODS*, 17(1), 94-162.
3. Josefsson, S., & Liusvaara, I. (2017). Edwards-Curve Digital Signature Algorithm (EdDSA). *IETF RFC 8032*.
4. Microsoft Corporation. (2022). *SQL Server Ledger Overview and Architecture*. Microsoft Learn Documentation.
5. PostgreSQL Global Development Group. (2024). *PostgreSQL 15 Documentation: pgcrypto and Trigger Procedures*.
