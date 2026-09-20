# Argus Multi-Witness Co-Signing via transparency-dev/witness Protocol Specification (HARDEN-012)

> **Document Version:** 1.0  
> **Date:** September 17, 2026  
> **Status:** Frontier Specification / Target Architecture  
> **Task Mapping:** `HARDEN-012` (Milestone 11.3, Step 11.C.2)  
> **Applicable Branch:** `feature/abhinav-core`  
> **Theoretical Foundations:** Google Transparency Dev (`transparency-dev/witness`), Sigstore Rekor, IETF draft-ietf-trans-rfc6962-bis Cosigning Protocol  

---

## 1. Threat Model & Architectural Motivation

### 1.1 The Single-Origin Vulnerability (Split-View Attacks)
In high-assurance enterprise deployments, anchoring audit checkpoints to a single external authority (e.g. one private Ed25519 key, one GitHub repository, or one cloud account) leaves a critical residual threat: **the Split-View (Forking) Attack**.

If a sophisticated adversary compromises the application host credentials ($A_{\text{APP}}$) or executes an advanced persistent threat (APT) against the corporate database infrastructure:
1. **Divergent Checkpoints:** The attacker can mint two conflicting checkpoints ($C_{\text{internal}}$ and $C_{\text{regulatory}}$) for the exact same sequence ID $S$.
2. **Targeted Presentation:** The internal HR team and internal auditors are presented with $C_{\text{internal}}$ (masking an executive salary embezzlement or unauthorized permission escalation), while external regulatory auditors (SOX/SOC 2) are presented with $C_{\text{regulatory}}$.
3. **Anchor Partitioning:** If the anchor store relies on a single origin signature, both views appear cryptographically valid to their respective audiences because neither party observes the alternate branch.

```
                            ┌───────────────────────────────────┐
                            │      Compromised Signer Key       │
                            │             (A_APP)               │
                            └─────────────────┬─────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         Branch A (Internal View)                         Branch B (Regulator View)
     Sequence 50: Bonus = $250,000                   Sequence 50: Bonus = $0
   Signed by: local:ed25519:v1                     Signed by: local:ed25519:v1
   Presented to: Internal Compliance               Presented to: External SEC / PCAOB
```

### 1.2 Target Resolution: Multi-Witness Cosigning
To mathematically eliminate split-view attacks, Argus adopts the **Witness Cosigning Protocol** developed by the **Google Transparency Dev** initiative (`transparency-dev/witness`) and standardized across the Sigstore Rekor and Certificate Transparency ecosystems.

Under this protocol:
1. **Decentralized Witness Network:** Checkpoint commitments are submitted to a network of $N$ independent, heterogeneous witnesses (e.g. AWS KMS witness, GCP Cloud KMS witness, Cloudflare worker witness, independent external compliance firm).
2. **Stateful Consistency Checks:** Before signing, a witness requires a **Consistency Proof** demonstrating that the new checkpoint's Merkle root is an append-only extension of the previous checkpoint root that the witness signed.
3. **Threshold Quorum ($M$-of-$N$):** A checkpoint is considered valid and sealed only if it carries valid signatures from the Origin plus at least $M$ independent, registered witnesses ($M \le N$, typically 2-of-3 or 3-of-5).
4. **Instant Split-View Detection:** If the origin attempts to fork the history or submit conflicting Merkle roots for the same sequence index, the witness rejects the update and broadcasts a cryptographic **Proof of Misbehavior (Forking Alert)**.

---

## 2. Checkpoint Note Format & Protocol Contracts

### 2.1 RFC 9162 Note Specification
Argus formats checkpoint commitments according to the standardized IETF RFC 9162 / `checkpoint` text representation. This canonical, whitespace-sensitive format ensures deterministic signing across heterogeneous architectures:

```text
argus.enterprise/v1/checkpoint
<sequence_id>
<merkle_root_base64>
<timestamp_iso8601>
<extension_metadata_json>

— argus.origin <origin_ed25519_signature_b64>
— witness.aws.compliance.net/v1 <witness_1_signature_b64>
— witness.gcp.trustcenter.org/v1 <witness_2_signature_b64>
```

#### Field Definitions:
- **Header Line (`argus.enterprise/v1/checkpoint`):** Origin ecosystem domain and note schema version.
- **Sequence ID (`<sequence_id>`):** Monotonically increasing audit log tail sequence integer.
- **Merkle Root (`<merkle_root_base64>`):** 32-byte binary SHA-256 Merkle root encoded in standard RFC 4648 Base64.
- **Timestamp (`<timestamp_iso8601>`):** UTC checkpoint minting timestamp.
- **Extension Metadata (`<extension_metadata_json>`):** Optional JSON-encoded metadata (e.g., `{"checkpoint_id": 42, "key_id": "kms:us-east-1:123"}`).
- **Signatures (`— <verifier_name> <signature_b64>`):** 
  - First signature line is always the Primary Origin Signer.
  - Subsequent lines are independent Witness Signatures prefixed with an em-dash (`— `).

---

## 3. The Witness Verification State Machine

Each witness maintains a local, persistent state record for each observed verifiable log:
$$\mathcal{S}_W = \{ \text{last\_seq}, \text{last\_root}, \text{last\_timestamp} \}$$

When Argus submits a new checkpoint note $N_{\text{new}}$ with size $S_{\text{new}}$ and root $R_{\text{new}}$:

```
                      ┌─────────────────────────────────┐
                      │    Receive Checkpoint Note:     │
                      │  (Seq_new, Root_new, Proof_c)   │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                     /───────────────────────────────────\
                    <      Is Seq_new > Seq_old?          >
                     \───────────────────────────────────/
                               /               \
                       NO     /                 \  YES
                             ▼                   ▼
                  /─────────────────────\   /───────────────────────\
                 <  Seq_new == Seq_old?  > < Validate Consistency    >
                  \─────────────────────/  < Proof (Root_old->Root)  >
                     /               \     \───────────────────────/
             YES    /                 \ NO         /            \
                   ▼                   ▼   FAILED /              \ PASSED
          /─────────────────\       REJECT       ▼                ▼
         <  Root_new ==      >      (Rollback  REJECT         Sign Note with
         <  Root_old?        >      Anomaly)   (Split-View    Witness Private Key
          \─────────────────/                  Fork Detected) Return Signature
             /           \
     YES    /             \ NO
           ▼               ▼
      Return Cached     CRITICAL ALERT:
      Signature         Equivocation Detected!
                        (Broadcast Proof of Misbehavior)
```

### 3.1 Verification Rules:
1. **Rule 1 (Monotonic Progress):** $S_{\text{new}} \ge S_{\text{old}}$. If $S_{\text{new}} < S_{\text{old}}$, the log has rolled backwards (stale or rewound state). Reject immediately.
2. **Rule 2 (Equivocation Guard):** If $S_{\text{new}} == S_{\text{old}}$ and $R_{\text{new}} \neq R_{\text{old}}$, the origin has presented two distinct histories for the exact same point in time. The witness MUST log this as an active cryptographic split-view compromise and publish both signed notes as indisputable proof of equivocation.
3. **Rule 3 (Consistency Proof Validation):** If $S_{\text{new}} > S_{\text{old}}$, the witness requires a cryptographic consistency proof showing that the Merkle tree of size $S_{\text{old}}$ with root $R_{\text{old}}$ is a strict prefix of the Merkle tree of size $S_{\text{new}}$ with root $R_{\text{new}}$.

---

## 4. API Endpoints & Witness Client Architecture

### 4.1 Checkpoint Submission: `POST /witness/v1/update`
Argus dispatches the checkpoint update asynchronously or synchronously during checkpoint creation:

```http
POST /witness/v1/update HTTP/1.1
Host: witness-1.compliance.example.com
Content-Type: application/json
User-Agent: Argus-Witness-Client/1.1

{
    "checkpoint_note": "argus.enterprise/v1/checkpoint\n50\nu7z...\n2026-09-17T21:00:00Z\n\n— argus.origin fK2...",
    "old_size": 25,
    "new_size": 50,
    "consistency_proof": [
        "a4f8b9...",
        "c1e2d3...",
        "f0a1b2..."
    ]
}
```

#### Response:
```http
HTTP/1.1 200 OK
Content-Type: text/plain

— witness.aws.compliance.net/v1 YWJjMTIz...
```

### 4.2 Python Witness Client Interface (`db/crypto/witness.py`)
```python
class WitnessClient(abc.ABC):
    """Abstract interface for communicating with external transparency witnesses."""
    
    @abc.abstractmethod
    def cosign_checkpoint(
        self, 
        note: str, 
        old_size: int, 
        new_size: int, 
        consistency_proof: list[str]
    ) -> str:
        """Submits checkpoint note to witness, returns witness signature line."""
        pass


class HttpWitnessClient(WitnessClient):
    """Standard HTTP client connecting to a transparency-dev/witness daemon."""
    
    def __init__(self, endpoint_url: str, public_key_der: bytes, timeout: float = 5.0):
        self.endpoint_url = endpoint_url
        self.public_key_der = public_key_der
        self.timeout = timeout

    def cosign_checkpoint(self, note: str, old_size: int, new_size: int, consistency_proof: list[str]) -> str:
        req_payload = {
            "checkpoint_note": note,
            "old_size": old_size,
            "new_size": new_size,
            "consistency_proof": consistency_proof
        }
        req = urllib.request.Request(
            f"{self.endpoint_url}/witness/v1/update",
            data=json.dumps(req_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            signature_line = resp.read().decode("utf-8").strip()
            return signature_line
```

---

## 5. Threshold Quorum Verification in Verifier Engine

In `db/cli/verifier.py` and `POST /api/verify`, verification is extended to assert witness quorum:

```python
def verify_witness_quorum(
    checkpoint_note: str, 
    witness_registry: dict[str, Ed25519PublicKey], 
    threshold_m: int = 2
) -> tuple[bool, str]:
    """Verifies that a checkpoint note contains at least M valid witness signatures."""
    lines = checkpoint_note.strip().split("\n")
    body = []
    signatures = []
    in_signatures = False
    
    for line in lines:
        if line.startswith("— "):
            in_signatures = True
            signatures.append(line[2:].strip())
        elif not in_signatures:
            body.append(line)
            
    body_text = "\n".join(body) + "\n"
    body_bytes = body_text.encode("utf-8")
    
    # 1. Verify Origin Signature (First signature)
    if not signatures:
        return False, "Missing origin signature"
        
    origin_name, origin_sig_b64 = signatures[0].split(" ", 1)
    # Validate origin...
    
    # 2. Count Valid Witness Signatures
    valid_witness_count = 0
    observed_witnesses = set()
    
    for sig_line in signatures[1:]:
        witness_name, sig_b64 = sig_line.split(" ", 1)
        if witness_name in observed_witnesses:
            continue  # Prevent double-counting duplicate signatures
            
        if witness_name in witness_registry:
            pubkey = witness_registry[witness_name]
            sig_bytes = base64.b64decode(sig_b64)
            try:
                pubkey.verify(sig_bytes, body_bytes)
                valid_witness_count += 1
                observed_witnesses.add(witness_name)
            except Exception:
                logger.warning(f"Invalid signature from witness {witness_name}")
                
    if valid_witness_count < threshold_m:
        return False, f"Quorum failure: {valid_witness_count}/{threshold_m} required witness signatures verified"
        
    return True, f"Quorum satisfied: {valid_witness_count} independent witness signatures valid"
```

---

## 6. Resilience, Fallback & Offline Policies

1. **Policy: Soft Quorum vs Hard Quorum:**
   - **Internal High-Availability Mode (Soft Quorum):** If fewer than $M$ witnesses respond within the $5.0\text{s}$ timeout (e.g. during cloud network partition), the checkpoint is sealed locally with the Origin signature and flagged with status `PENDING_WITNESS_QUORUM`. A background retry daemon re-attempts cosigning.
   - **Regulated High-Assurance Mode (Hard Quorum):** In banking or classified environments, checkpoints are not committed to external anchors until $M$ witness signatures are gathered, ensuring zero uncosigned windows.
2. **Key Rotation & Witness Deprecation:**
   - Witnesses are identified by canonical URI. The `KeyRegistry` maintains active time ranges for witness public keys. If a witness key is rotated or retired, historical signatures retain validity based on checkpoint timestamps.
