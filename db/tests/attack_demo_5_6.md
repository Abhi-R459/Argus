# Attack Demo #5 & #6 — Checkpoint Integrity Validation

> **Task:** CRYPTO-006  
> **Date:** 2026-08-06  
> **Status:** Documented

---

## Overview

These demos prove that the Argus verification engine detects two critical
checkpoint-level attacks:

1. **Demo #5** — Deleting a checkpoint row from `chain_checkpoints`
2. **Demo #6** — Forging an anchor file with an invalid Ed25519 signature

Both scenarios demonstrate that even with database superuser access or
external-store write access, the cryptographic guarantees prevent silent
tampering.

---

## Attack Demo #5: Checkpoint Deletion

### Threat Model

An attacker with superuser access to the PostgreSQL database directly
deletes a row from `chain_checkpoints` to erase evidence of a specific
checkpoint.

### Simulation Steps

```sql
-- Step 1: Confirm checkpoint exists
SELECT checkpoint_id, sequence_id, checkpoint_hash
FROM   chain_checkpoints
WHERE  checkpoint_id = 1;

-- Step 2: As superuser, delete the checkpoint
DELETE FROM chain_checkpoints WHERE checkpoint_id = 1;

-- Step 3: Confirm deletion
SELECT COUNT(*) FROM chain_checkpoints WHERE checkpoint_id = 1;
-- Returns: 0
```

### Detection

Run the verifier with anchor verification:

```bash
python -m db.cli.verifier verify-chain --db-url $DATABASE_URL
```

The verifier walks the full chain. During checkpoint verification, it
detects that the expected checkpoint at the stored `sequence_id` is
missing from `chain_checkpoints`.

### Expected Output

```
ARGUS CHAIN VERIFICATION REPORT
============================================================
Total entries verified : 100
Hash mismatches        : 0
Sequence gaps          : 0
Orphaned entries       : 0
Chain status           : ✅ VALID

WARNING: Missing checkpoint at sequence_id = 25
  Expected checkpoint based on interval of 25 — not found in chain_checkpoints.
```

> **Key insight:** The chain itself remains valid (hashes are intact), but
> the checkpoint infrastructure has been tampered with. A full audit reveals
> the gap.

### Remediation

Re-run `create-checkpoint` to regenerate the missing checkpoint:

```bash
python -m db.cli.verifier create-checkpoint --db-url $DATABASE_URL --checkpoint-interval 25
```

The idempotent `ON CONFLICT DO NOTHING` means only the missing checkpoint
is recreated.

---

## Attack Demo #6: Forged Anchor File

### Threat Model

An attacker with write access to the external anchor store (local file
system or GitHub repository) creates a fake checkpoint JSON file with a
forged signature that does not correspond to the genuine Ed25519 private key.

### Simulation Steps

```bash
# Step 1: Generate a DIFFERENT (attacker's) keypair
python -c "
from db.cli.keygen import generate_keypair, save_keypair
priv, pub = generate_keypair()
save_keypair(priv, pub, directory='./attacker_keys')
print('Attacker keypair generated.')
"

# Step 2: Sign a fake checkpoint hash with the attacker's key
python -c "
from db.cli.keygen import load_private_key
from db.cli.signer import sign_checkpoint
import json

# Use attacker's key to sign a forged checkpoint hash
attacker_key = load_private_key('./attacker_keys/signing_key.pem')
fake_hash = 'a' * 64  # or a real checkpoint hash
fake_sig = sign_checkpoint(attacker_key, fake_hash)

# Create a forged anchor file
forged = {
    'checkpoint_id': 1,
    'sequence_id': 25,
    'checkpoint_hash': fake_hash,
    'signature_hex': fake_sig.hex(),
    'created_at': '2026-08-06 10:00:00+05:30',
}
with open('./anchors/1.json', 'w') as f:
    json.dump(forged, f)
print('Forged anchor file created.')
"
```

### Detection

Verify the anchor against the genuine public key:

```bash
python -m db.cli.verifier anchor --checkpoint-id 1 --type local --path ./anchors --verify-sig
```

Or programmatically:

```python
from db.cli.keygen import load_public_key, get_default_key_dir
from db.cli.signer import verify_signature
import json, os

# Load the GENUINE public key
pub_key = load_public_key(os.path.join(get_default_key_dir(), "public_key.pem"))

# Read the forged anchor
with open("./anchors/1.json") as f:
    anchor = json.load(f)

sig = bytes.fromhex(anchor["signature_hex"])
is_valid = verify_signature(pub_key, anchor["checkpoint_hash"], sig)

print(f"Signature valid: {is_valid}")  # False — forged signature detected!
```

### Expected Output

```
ERROR: Signature verification failed — aborting anchor.
  Checkpoint 1 signature does not match the registered public key.
  This indicates the anchor was forged or the signing key has been compromised.
```

> **Key insight:** Ed25519 signatures are non-forgeable without the private
> key (Decision #3).  Even if an attacker can write to the anchor store,
> they cannot produce a valid signature without possessing the genuine
> signing key stored at `~/.argus/signing_key.pem`.

---

## Security Properties Demonstrated

| Property | Demo #5 | Demo #6 |
|----------|---------|---------|
| **Completeness** | Missing checkpoint detected | ✅ |
| **Authenticity** | N/A | Forged signature rejected |
| **Non-repudiation** | Deletion is evident | Signing key proves origin |
| **Integrity** | Chain hashes remain valid | Anchor hash mismatch |

---

## References

- [Decision #3: Signed external anchor over unsigned hash anchor](../../.ai/DECISIONS.md)
- [Decision #8: Ed25519 via `cryptography` lib](../../.ai/DECISIONS.md)
- [SETUP-002: Hash-Input Serialization Agreement](../../.ai/TASKS.md)
