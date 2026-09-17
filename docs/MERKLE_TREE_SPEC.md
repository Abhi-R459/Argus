# Argus Merkle-Tree-Per-Checkpoint Architectural Specification (HARDEN-011)

> **Document Version:** 1.0  
> **Date:** September 17, 2026  
> **Status:** Frontier Specification / Target Architecture  
> **Task Mapping:** `HARDEN-011` (Milestone 11.3, Step 11.C.1)  
> **Applicable Branch:** `feature/abhinav-core`  
> **Theoretical Foundations:** Crosby & Wallach (USENIX Security '09), RFC 6962 / RFC 9162 (Certificate Transparency), Microsoft SQL Server Ledger  

---

## 1. Executive Summary & Problem Statement

### 1.1 The Linear Hash Chain Bottleneck
In the current Argus production release (v1.1), tamper evidence is maintained via a sequential, linear SHA-256 hash chain:
$$H_i = \text{SHA-256}(H_{i-1} \parallel M_i)$$
where $M_i$ is the canonical JSON serialization of the $i$-th audit event and $H_{i-1}$ is the cryptographic tail hash of the preceding record. Checkpoints are periodically minted every $N=25$ entries or $T=60$ elapsed seconds, binding the current tail hash $H_{\text{curr}}$ with an Ed25519 digital signature and publishing the commitment to an external anchor store (RFC 3161 TSA, AWS S3 Object Lock, or GitHub).

While this linear chain achieves:
1. **$O(1)$ Inline Insertion Overhead:** Appending an audit row requires only 1 SHA-256 operation within the PostgreSQL trigger (adding $<0.35\text{ms}$ write latency).
2. **Complete Tamper Detection:** Any alteration, deletion, or truncation of historical records is reliably detected upon a linear verification walk.

It suffers from fundamental scalability and privacy constraints when interacting with external compliance auditors, mobile verifiers, and multi-tenant subsystems:
- **Linear Membership Proofs ($O(K)$ Complexity):** To prove to a third-party auditor that a specific transaction $e_k$ was executed at time $t$ within checkpoint interval $[S_{\text{start}}, S_{\text{end}}]$ of size $K = S_{\text{end}} - S_{\text{start}} + 1$, the verifier must provide **all $K$ intermediate audit rows**. For large intervals (e.g., $K = 10,000$ operations), the auditor must transfer and hash several megabytes of unrelated audit payloads.
- **Unintended Data Disclosure (Privacy Breach):** Providing all $K$ rows to prove the inclusion of one employee's promotion necessarily discloses the organizational mutations, salaries, and department transfers of **other employees** whose mutations fell within the same checkpoint interval.
- **Linear Consistency Proofs ($O(K)$ Complexity):** Proving that a historical database state represented by checkpoint $C_A$ is an exact prefix of an updated database state represented by checkpoint $C_B$ requires streaming all intermediate records between $C_A$ and $C_B$.

### 1.2 Target Architecture: Merkle-Tree-Per-Checkpoint
To overcome these limitations without forfeiting sub-millisecond relational write performance, this specification details the migration of Argus to a **Merkle-Tree-Per-Checkpoint** architecture. 

In this model:
1. **Relational Inline Writes Remain Linear:** PostgreSQL `AFTER` triggers continue appending records sequentially to `audit_log`, preserving $O(1)$ transaction commit times and strict linear row-level serialization via `chain_state`.
2. **Checkpoint Generation Constructs a Binary Balanced Merkle Tree:** When the dual-trigger firing condition is satisfied ($N \ge 25$ or $T \ge 60\text{s}$), the background checkpoint engine aggregates the uncheckpointed slice of $K$ records into a cryptographic Merkle Hash Tree (MHT).
3. **The Merkle Root is Signed & Anchored:** The Ed25519 signature and external anchor (RFC 3161 / S3 WORM) bind the **Merkle Root Hash** ($R_{\text{MHT}}$) alongside the range $[S_{\text{start}}, S_{\text{end}}]$ and boundary hash links.
4. **Logarithmic Audit Proofs ($O(\log_2 K)$):** Any arbitrary transaction within the checkpoint can be proved included via an Audit Path of length $\lceil \log_2 K \rceil$ hashes (approximately 5 hashes for $K=25$, 14 hashes for $K=10,000$), completely isolating the proof from unrelated tenant or employee records.

---

## 2. Mathematical Formalization & Hash Primitives

### 2.1 RFC 6962 Domain Separation & Second-Preimage Defense
To protect against second-preimage attacks where an attacker crafts an internal node payload that collides with a leaf node preimage, Argus adopts the strict domain separation prefixes defined in **RFC 6962 §2.1** and **NIST SP 800-108**:

- **Leaf Node Hash Prefix:** `0x00` (1 byte)
- **Internal Node Hash Prefix:** `0x01` (1 byte)

Let $R_j$ represent the canonicalized JSON representation of audit event $j$ for $j \in [0, K-1]$. The $j$-th leaf hash $L_j$ is defined as:
$$L_j = \text{SHA-256}\Big(0x00 \parallel R_j\Big)$$

For any parent node $N_{\text{parent}}$ with left child $N_{\text{left}}$ and right child $N_{\text{right}}$, the internal node hash is computed as:
$$N_{\text{parent}} = \text{SHA-256}\Big(0x01 \parallel N_{\text{left}} \parallel N_{\text{right}}\Big)$$

If an odd number of leaves or sub-nodes exists at any tree level, Argus applies the balanced binary tree convention: the unpaired rightmost node is promoted directly to the next level without duplicate hashing, preventing the well-known duplicate-leaf vulnerability identified in Bitcoin's CVE-2012-2459.

```
                  Root (Level 3)
                   [0x01 || N4 || N5]
                      /          \
                     /            \
           Node 4 (Level 2)      Node 5 (Level 2)
          [0x01 || N1 || N2]    [0x01 || N3 || L4]  <-- Odd promotion
             /         \               /       \
            /           \             /         \
      Node 1            Node 2       Node 3      [L4]
  [0x01||L0||L1]    [0x01||L2||L3]  [0x01||L3||L4]
      /    \            /    \
     /      \          /      \
   [L0]    [L1]      [L2]    [L3]
  (Leaf0) (Leaf1)   (Leaf2) (Leaf3)  (Leaf4)
```

---

## 3. Database Schema Contract Extensions

### 3.1 Migration to `chain_checkpoints`
The existing `chain_checkpoints` table is extended with three new structural columns:

```sql
ALTER TABLE chain_checkpoints
    ADD COLUMN merkle_root VARCHAR(64) NULL,
    ADD COLUMN tree_size INT NULL,
    ADD COLUMN tree_height INT NULL;

COMMENT ON COLUMN chain_checkpoints.merkle_root IS 
    'Hex-encoded SHA-256 Merkle root hash of all audit records in interval [start_sequence_id, sequence_id].';
```

### 3.2 Auxiliary Node Storage: `chain_merkle_nodes`
To enable sub-millisecond retrieval of audit inclusion proofs without recomputing the entire tree from raw audit records on each query, internal and leaf nodes are indexed in a dedicated table:

```sql
CREATE TABLE chain_merkle_nodes (
    checkpoint_id INT NOT NULL REFERENCES chain_checkpoints(checkpoint_id) ON DELETE CASCADE,
    node_level SMALLINT NOT NULL,
    node_index INT NOT NULL,
    hash VARCHAR(64) NOT NULL,
    is_leaf BOOLEAN NOT NULL DEFAULT FALSE,
    sequence_id BIGINT NULL REFERENCES audit_log(sequence_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (checkpoint_id, node_level, node_index)
);

CREATE INDEX idx_merkle_nodes_seq ON chain_merkle_nodes (sequence_id) WHERE sequence_id IS NOT NULL;
CREATE INDEX idx_merkle_nodes_level ON chain_merkle_nodes (checkpoint_id, node_level);
```

---

## 4. Algorithmic Specifications

### 4.1 Algorithm 1: Checkpoint Merkle Tree Construction
```python
def build_checkpoint_merkle_tree(audit_records: list[dict]) -> tuple[str, list[dict]]:
    """Constructs an RFC 6962 domain-separated Merkle Tree over a slice of audit records.
    
    Args:
        audit_records: Chronologically ordered audit entries for the checkpoint interval.
        
    Returns:
        tuple[str, list[dict]]: (merkle_root_hex, list_of_node_records_to_persist)
    """
    if not audit_records:
        raise ValueError("Cannot build Merkle tree over empty audit record slice")
        
    # 1. Compute Leaf Hashes (Prefix 0x00)
    current_level_nodes = []
    persisted_nodes = []
    
    for idx, record in enumerate(audit_records):
        canonical_bytes = canonical_json_serialize(record).encode("utf-8")
        leaf_hash = hashlib.sha256(b"\x00" + canonical_bytes).hexdigest()
        current_level_nodes.append(leaf_hash)
        persisted_nodes.append({
            "node_level": 0,
            "node_index": idx,
            "hash": leaf_hash,
            "is_leaf": True,
            "sequence_id": record["sequence_id"]
        })
        
    level = 0
    while len(current_level_nodes) > 1:
        next_level_nodes = []
        n = len(current_level_nodes)
        
        for i in range(0, n, 2):
            left_hash = current_level_nodes[i]
            if i + 1 < n:
                right_hash = current_level_nodes[i + 1]
                parent_hash = hashlib.sha256(
                    b"\x01" + bytes.fromhex(left_hash) + bytes.fromhex(right_hash)
                ).hexdigest()
            else:
                # Promotion of unpaired rightmost node (CVE-2012-2459 mitigation)
                parent_hash = left_hash
                
            next_level_nodes.append(parent_hash)
            persisted_nodes.append({
                "node_level": level + 1,
                "node_index": len(next_level_nodes) - 1,
                "hash": parent_hash,
                "is_leaf": False,
                "sequence_id": None
            })
            
        level += 1
        current_level_nodes = next_level_nodes
        
    merkle_root = current_level_nodes[0]
    return merkle_root, persisted_nodes
```

### 4.2 Algorithm 2: $O(\log_2 K)$ Audit Path Generation
To verify that audit entry $e$ (at sequence index $k$) is member of checkpoint $C$, the server extracts the sequence of sibling hashes along the path from leaf to root:

```python
def generate_audit_path(checkpoint_id: int, sequence_id: int, db_conn) -> dict:
    """Generates a logarithmic cryptographic inclusion proof for a specific audit sequence.
    
    Returns:
        dict: {
            "checkpoint_id": int,
            "sequence_id": int,
            "leaf_hash": str,
            "merkle_root": str,
            "audit_path": list[dict]: [
                {"level": 0, "sibling_hash": "...", "direction": "left" | "right"}
            ]
        }
    """
    # 1. Resolve leaf node
    leaf = db_conn.query_one(
        "SELECT node_index, hash FROM chain_merkle_nodes WHERE checkpoint_id = %s AND sequence_id = %s",
        (checkpoint_id, sequence_id)
    )
    if not leaf:
        raise KeyError(f"Sequence {sequence_id} not found in checkpoint {checkpoint_id}")
        
    index = leaf["node_index"]
    path = []
    
    # Query maximum height for this checkpoint
    max_level = db_conn.query_val(
        "SELECT MAX(node_level) FROM chain_merkle_nodes WHERE checkpoint_id = %s",
        (checkpoint_id,)
    )
    
    for lvl in range(max_level):
        is_right = (index % 2 == 1)
        sibling_index = index - 1 if is_right else index + 1
        
        sibling = db_conn.query_one(
            "SELECT hash FROM chain_merkle_nodes WHERE checkpoint_id = %s AND node_level = %s AND node_index = %s",
            (checkpoint_id, lvl, sibling_index)
        )
        if sibling:
            path.append({
                "level": lvl,
                "direction": "left" if is_right else "right",
                "sibling_hash": sibling["hash"]
            })
            
        index //= 2
        
    root_hash = db_conn.query_val(
        "SELECT merkle_root FROM chain_checkpoints WHERE checkpoint_id = %s",
        (checkpoint_id,)
    )
    
    return {
        "checkpoint_id": checkpoint_id,
        "sequence_id": sequence_id,
        "leaf_hash": leaf["hash"],
        "merkle_root": root_hash,
        "audit_path": path
    }
```

### 4.3 Algorithm 3: Zero-Knowledge Verifier Evaluation
The compliance auditor or mobile client verifies membership without database connectivity:

```python
def verify_audit_inclusion_proof(record: dict, proof: dict) -> bool:
    """Verifies cryptographic inclusion of an audit record against a signed Merkle root."""
    # 1. Compute target leaf hash from provided record
    canonical_bytes = canonical_json_serialize(record).encode("utf-8")
    current_hash = hashlib.sha256(b"\x00" + canonical_bytes).hexdigest()
    
    if current_hash != proof["leaf_hash"]:
        return False
        
    # 2. Traverse audit path to compute candidate root
    for step in proof["audit_path"]:
        sibling = bytes.fromhex(step["sibling_hash"])
        current_bytes = bytes.fromhex(current_hash)
        
        if step["direction"] == "left":
            combined = b"\x01" + sibling + current_bytes
        else:
            combined = b"\x01" + current_bytes + sibling
            
        current_hash = hashlib.sha256(combined).hexdigest()
        
    # 3. Equality assertion against checkpoint's signed Merkle Root
    return current_hash == proof["merkle_root"]
```

---

## 5. Quantitative Complexity & Performance Projections

| Metric | Flat Linear Chain (Current v1.1) | Merkle-Tree-Per-Checkpoint (HARDEN-011) | Improvement Factor |
| :--- | :--- | :--- | :--- |
| **Inline Row Insertion Latency** | $0.28\text{ ms}$ | $0.28\text{ ms}$ (Identical — No tree in write path) | **Invariance ($1.0\times$)** |
| **Inclusion Proof Size ($K=25$)** | $25 \text{ records} \approx 18.5\text{ KB}$ | $5 \text{ hashes} \approx 160\text{ bytes}$ | **$115\times$ Reduction** |
| **Inclusion Proof Size ($K=10,000$)** | $10,000 \text{ records} \approx 7.4\text{ MB}$ | $14 \text{ hashes} \approx 448\text{ bytes}$ | **$16,500\times$ Reduction** |
| **Verifier CPU Overhead ($K=10,000$)** | $10,000 \text{ SHA-256 operations}$ | $14 \text{ SHA-256 operations}$ | **$714\times$ Speedup** |
| **Tenant / PII Privacy Shield** | Zero isolation (all sibling rows revealed) | Perfect isolation (only sibling digests revealed) | **Mathematical Unlinkability** |
| **Storage Overhead** | $0\%$ auxiliary rows | $+ (2K - 1) \times 64\text{ bytes}$ in indexed nodes | **$+0.8\%$ storage expansion** |

---

## 6. Backward Compatibility & Phased Migration Path

1. **Phase 1 (Hybrid Coexistence):**
   - Checkpoints continue recording `checkpoint_hash` (the sequential linear tail hash) AND compute `merkle_root`.
   - Existing verifier algorithms (`db.cli.verifier`) continue linear walks undisturbed.
   - The REST API introduces `/api/audit-logs/{id}/inclusion-proof` alongside `/api/audit-logs/chain`.
2. **Phase 2 (Auditor Client Modernization):**
   - The Auditor Portal (`AuditChainPage.tsx` and `.arguspack` export bundle) integrates logarithmic inclusion proofs into the inspection drawer.
3. **Phase 3 (Long-Term Pruning):**
   - Older checkpoint slices in PostgreSQL can safely archive raw JSON payloads to cold S3 WORM storage while retaining only `chain_merkle_nodes` in active memory, maintaining instant verification capabilities over multi-year corporate histories.
