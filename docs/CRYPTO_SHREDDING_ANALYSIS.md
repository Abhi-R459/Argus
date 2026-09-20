# Resolving Blind-Index Linkability under GDPR Article 17 Crypto-Shredding (HARDEN-013)

> **Document Version:** 1.0  
> **Date:** September 17, 2026  
> **Status:** Advanced Frontiers Research & Technical Architecture  
> **Task Mapping:** `HARDEN-013` (Milestone 11.3, Step 11.C.3)  
> **Applicable Branch:** `feature/abhinav-core`  
> **Regulatory Foundations:** GDPR Articles 17 ("Right to Erasure"), 25 ("Data Protection by Design"), 32 ("Security of Processing"); CNIL & EDPB Guidelines 01/2021 on Pseudonymization  

---

## 1. Executive Summary & The Fundamental Conflict

### 1.1 The Irreconcilable Clash: Immutability vs. Erasure
Modern data privacy jurisprudence (most notably **GDPR Article 17**, the "Right to be Forgotten", and equivalent mandates in CCPA/CPRA, LGPD, and HIPAA) grants data subjects the legal entitlement to compel data controllers to permanently erase their personal data without undue delay.

Conversely, high-assurance tamper-evident database engines (such as Argus, Microsoft SQL Server Ledger, and AWS QLDB) are architected around a mathematical invariant: **append-only hash chain immutability**. 
Every historical event $e_i$ is bound into the linear or tree-structured cryptographic hash chain:
$$H_i = \text{SHA-256}(H_{i-1} \parallel M_i)$$

If an administrator or automated process attempts to physically delete or nullify a historical audit record ($M_i \leftarrow \emptyset$), the sequence of hashes from $i$ to the chain tail immediately fractures:
$$H_k \neq \text{SHA-256}(H_{k-1} \parallel M_k) \quad \forall k \ge i$$
The verification engine interprets this physical deletion as **an active adversary tampering event ($A_{\text{DBA}}$)**, raising critical forensic alarms, invalidating signed checkpoints, and failing regulatory compliance audits (SOX 404, SOC 2 CC6.8).

### 1.2 The Standard Cryptographic Shredding Solution & Its Blind-Index Vulnerability
To resolve this tension, enterprise systems implement **Cryptographic Shredding** (supported by European Data Protection Board (EDPB) guidance and French CNIL recommendations):
1. Plaintext Personally Identifiable Information (PII) is encrypted with an individual, subject-specific symmetric Data Encryption Key ($K_{\text{DEK}}$) using AES-256-GCM.
2. The encrypted ciphertext is stored within the immutable audit log payload ($M_i$).
3. When the data subject exercises their Article 17 Right to Erasure, the controller **destroys $K_{\text{DEK}}$**.
4. Without the key, the ciphertext cannot be decrypted by any computationally bounded entity, rendering the data irreversibly inaccessible (effectively equivalent to deletion under information-theoretic and standard computational security models).
5. The cryptographic hash chain remains 100% intact because the ciphertext bytes in $M_i$ are unchanged.

#### The Unresolved Vulnerability: Static Blind Index Linkability
In Argus Phase 7 (BLIND-001/002/003) and Phase 11 (HARDEN-009), we introduced **PBKDF2-HMAC-SHA256 Blind Indexing** for structured identifiers (e.g. 9-digit national IDs) to enable exact-match forensic search without decrypting PII or leaking plaintext:
$$BI = \text{PBKDF2-HMAC-SHA256}(\text{National\_ID}, \text{AUDIT\_SALT}, \text{iterations})$$

Because `AUDIT_SALT` is a global, system-wide secret pepper, the blind index $BI$ is **deterministic across all historical records of the same individual**:
- Record 12: Hire event $\rightarrow BI = \texttt{0x9a4f...}$
- Record 38: Salary increase $\rightarrow BI = \texttt{0x9a4f...}$
- Record 79: Termination $\rightarrow BI = \texttt{0x9a4f...}$

**The Privacy Leak:** Even after $K_{\text{DEK}}$ is destroyed and the employee's name, email, and salary are rendered permanently unreadable, the token $\texttt{0x9a4f...}$ persists across every historical audit entry!
An adversary, curious insider, or unauthorized analyst observing the audit trail can:
1. **Track Lifecycle Patterns:** Trace that entity $\texttt{0x9a4f...}$ experienced 14 mutations over 4 years, correlated with departmental events or quarterly bonus cycles.
2. **Re-identification via Side-Channels:** Correlate external public records (e.g. layoff announcements, news of an executive hiring) with timestamped mutations bearing token $\texttt{0x9a4f...}$, breaking pseudonymity.
3. **Regulatory Violation:** GDPR Article 4(5) defines pseudonymised data as personal data if it can be attributed to a natural person by use of additional information. Retaining persistent linkability across shredded records violates the core intent of Article 17 and purpose limitation principles (Article 5(1)(b)).

---

## 2. Theoretical Architecture: DEK-Derived Blind Indexing

### 2.1 The Core Insight
To achieve genuine post-erasure unlinkability without sacrificing tamper-evident hash chaining, the blind indexing key **must not be derived solely from a static global salt**. 
Instead, the blind index key must be derived from the **composition of the global pepper AND the subject-specific Data Encryption Key ($K_{\text{DEK}}$)**:

$$K_{\text{BI}} = f(K_{\text{DEK}}, \text{AUDIT\_SALT})$$

When $K_{\text{DEK}}$ is destroyed during a GDPR Article 17 erasure request:
1. The decryption capability for the PII ciphertext is permanently eliminated.
2. The derivation capability for $K_{\text{BI}}$ is **simultaneously and permanently eliminated**.
3. It becomes mathematically impossible to compute the blind index for the shredded individual in future searches.
4. The historical blind index string $BI$ remaining in `audit_log` becomes an **irreversible pseudo-random token**, indistinguishable from uniform random noise ($U \in \{0, 1\}^{256}$). It can never again be linked to an incoming search query.

```
                           ┌────────────────────────────┐
                           │   Subject Master Secret    │
                           │          (K_DEK)           │
                           └──────────────┬─────────────┘
                                          │
                                          ▼
                                   /──────────────\
                                  <  Is K_DEK     >
                                  <  Destroyed?   >
                                   \──────────────/
                                    /            \
                            NO     /              \  YES (GDPR Art. 17)
                                  ▼                ▼
                     ┌───────────────────────┐   ┌───────────────────────────┐
                     │ Derive K_BI via HKDF: │   │ K_BI Permanently Lost!    │
                     │ HKDF(K_DEK, SALT)     │   │ Cannot compute index for  │
                     └───────────┬───────────┘   │ incoming search queries.  │
                                 │               └───────────────────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ Compute Blind Index:  │
                     │ PBKDF2(ID, K_BI)      │
                     └───────────────────────┘
```

---

## 3. Cryptographic Key Derivation Hierarchy

### 3.1 Formal Key Derivation Procedure
Argus uses **HKDF (HMAC-based Extract-and-Expand Key Derivation Function, RFC 5869)** with SHA-256 to isolate cryptographic subkeys:

1. **Master Extraction:**
   Let $K_{\text{DEK}}$ be the 256-bit AES key allocated to Subject $S$.
   $$PRK = \text{HKDF-Extract}(\text{salt} = \text{AUDIT\_SALT}_{\text{global}}, \text{ikm} = K_{\text{DEK}})$$

2. **Subkey Expansion:**
   - **Data Encryption Key ($K_{\text{enc}}$):**
     $$K_{\text{enc}} = \text{HKDF-Expand}(PRK, \text{info} = \text{"argus:subject:encryption:v1"}, L = 32)$$
   - **Blind Index Derivation Key ($K_{\text{BI}}$):**
     $$K_{\text{BI}} = \text{HKDF-Expand}(PRK, \text{info} = \text{"argus:subject:blind-index:v1"}, L = 32)$$

3. **Tunable Blind Index Generation:**
   Using the calibrated work factor $W = 1,000$ iterations (established in HARDEN-009):
   $$BI(S, \text{National\_ID}) = \text{PBKDF2-HMAC-SHA256}\Big(\text{Password}=\text{National\_ID}, \text{Salt}=K_{\text{BI}}, \text{Iterations}=1000\Big)$$

---

## 4. Operational Search Mechanics & Forward Resolution

### 4.1 Searchability Trade-Off Analysis
A fundamental cryptographic law governs this construction: **a blind index derived from a subject-specific key requires the subject key to evaluate the query**.

In the naive global-salt architecture:
$$\text{Query}(ID) \rightarrow \text{Compute } BI(ID, \text{SALT}_{\text{global}}) \rightarrow \text{Index Scan in } O(1)$$

In the DEK-derived architecture, how does the system locate an individual's historical records during forensic investigation without scanning all subject keys?

Argus adopts a **Two-Tier Identity Resolution Strategy**:

```
                         ┌─────────────────────────────┐
                         │   Forensic Search Request:  │
                         │    GET /api/audit-logs?     │
                         │    national_id_search=...   │
                         └──────────────┬──────────────┘
                                        │
                                        ▼
                     ┌─────────────────────────────────────┐
                     │ 1. Active Subject Key Directory     │
                     │    Query employee directory for     │
                     │    matching active subject S.       │
                     └──────────────────┬──────────────────┘
                                        │
                                        ▼
                                  /────────────\
                                 <  Subject Key >
                                 <  Available?  >
                                  \────────────/
                                    /          \
                            YES    /            \  NO (Shredded / Unknown)
                                  ▼              ▼
                     ┌──────────────────────┐  ┌─────────────────────────────┐
                     │ Derive K_BI(S) via   │  │ Subject has been shredded   │
                     │ HKDF(K_DEK(S), SALT) │  │ or does not exist.          │
                     └──────────┬───────────┘  │ Return empty search result  │
                                │              │ (0 records matched).        │
                                ▼              └─────────────────────────────┘
                     ┌──────────────────────┐
                     │ Compute Target Index │
                     │ BI = PBKDF2(ID, K_BI)│
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌─────────────────────────────────────┐
                     │ Exact Match Query on audit_log:     │
                     │ WHERE national_id_blind_index = BI  │
                     └─────────────────────────────────────┘
```

#### Properties:
1. **For Active Employees:** Search operates with identical speed and accuracy. The system resolves the subject's active DEK, computes $BI(S, ID)$, and queries `audit_log` via the B-tree index.
2. **For Shredded Employees:** Once $K_{\text{DEK}}$ is shredded, neither the auditor, nor the DBA, nor an attacker possessing `AUDIT_SALT` can reconstruct $K_{\text{BI}}$. The query terminates safely with 0 results.
3. **Cross-Subject Unlinkability:** Even if two employees previously shared identical attributes (e.g. identical bonus category or shared contact address), their distinct DEKs yield completely disjoint, uncorrelated blind index tokens.

---

## 5. Database Schema Blueprints & Shredding Trigger

### 5.1 Subject Key Custody Table (`subject_keys`)
```sql
CREATE TABLE subject_keys (
    subject_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id INT UNIQUE NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    encrypted_dek BYTEA NOT NULL,  -- AES-256-GCM wrapped under Master KEK
    kek_id VARCHAR(128) NOT NULL,  -- Cloud KMS Key ARN or Vault Transit Key ID
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shredded_at TIMESTAMPTZ NULL,
    shredded_by_user_id INT NULL REFERENCES users(user_id)
);

CREATE INDEX idx_subject_keys_emp ON subject_keys(employee_id) WHERE shredded_at IS NULL;
```

### 5.2 Deterministic Shredding Routine
```sql
CREATE OR REPLACE FUNCTION shred_employee_pii(
    p_employee_id INT,
    p_operator_user_id INT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_subject_id UUID;
BEGIN
    -- 1. Verify existence of active subject key
    SELECT subject_id INTO v_subject_id
    FROM subject_keys
    WHERE employee_id = p_employee_id AND shredded_at IS NULL
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Employee % already shredded or does not exist.', p_employee_id;
    END IF;

    -- 2. Overwrite and zeroize the encrypted DEK in place
    UPDATE subject_keys
    SET encrypted_dek = decode(repeat('00', 32), 'hex'),
        shredded_at = NOW(),
        shredded_by_user_id = p_operator_user_id
    WHERE subject_id = v_subject_id;

    -- 3. Delete plaintext employee record from active operational table
    DELETE FROM employees WHERE employee_id = p_employee_id;

    -- 4. Emit un-shredded audit entry recording the cryptographic erasure action
    -- (The erasure event itself is recorded in audit_log without storing PII)
    INSERT INTO audit_log (
        actor_user_id,
        action,
        table_name,
        row_id,
        new_value
    ) VALUES (
        p_operator_user_id,
        'GDPR_CRYPTO_SHRED',
        'employees',
        p_employee_id,
        jsonb_build_object(
            'subject_id', v_subject_id,
            'event', 'GDPR_ARTICLE_17_ERASURE',
            'shredded_at', NOW()
        )
    );
END;
$$;
```

---

## 6. Regulatory Compliance & Forensic Synthesis

| Regulatory Standard | Mandate Requirement | Argus DEK-Derived Architecture Fulfillment |
| :--- | :--- | :--- |
| **GDPR Article 17** | Permanent erasure of personal data upon request | DEK destroyed; ciphertext irreversibly undecipherable; blind index tokens permanently decoupled and unsearchable. |
| **GDPR Article 25** | Data protection by design and by default | Pseudonymization and key isolation are built into database triggers and KDF derivation layers. |
| **GDPR Article 32** | Security of processing & encryption of personal data | AES-256-GCM authenticated payload encryption combined with NIST SP 800-132 PBKDF2 blind indexing. |
| **SOX Section 404** | Internal control over financial reporting & immutable audit | Hash chain continuity ($H_i = \text{SHA256}(H_{i-1} \parallel M_i)$) is 100% preserved; no database rows are altered or deleted. |
| **SOC 2 CC6.8** | Unauthorized modification and deletion prevention | `audit_log` remains strictly append-only; tampering is immediately flagged by Verifier Engine. |

---

## 7. Conclusion
By pairing per-subject Data Encryption Keys ($K_{\text{DEK}}$) with HKDF subkey expansion, Argus solves the historic trade-off between cryptographic audit immutability and modern privacy rights. When a shredding request is executed, the subject's operational footprint is completely erased, the searchability of their historical audit records is terminated, and the cryptographic hash chain continues forward without a single broken link.
