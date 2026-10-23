# Independent witness quorum

For the automatic free-hosted design that replaces the private GitHub anchor, see [Automatic independent witnesses](AUTOMATED_INDEPENDENT_WITNESSES.md). This document retains the older manual private-anchor procedure for rollback and historical reference.

Argus can verify a 2-of-2 quorum on its private GitHub checkpoint anchor. A Clerk Auditor account grants access to evidence; it is **not** a witness identity. Two different people must operate the witness keys and retained state on their own machines or separately administered services. Argus and Render receive only public keys. The private GitHub anchor repository holds signatures, never private keys.

This is Argus's versioned Ed25519 checkpoint-prefix format, not an RFC 9162 or C2SP witness implementation. A witness verifies the complete exported evidence pack against a previously trusted origin public key, checks its retained checkpoint state, then signs the full ordered prefix of published checkpoints. The API compares the private anchor with PostgreSQL and verifies each signature against a pinned public key and distinct configured custody domain. The status remains **Unverified** if signatures, trust configuration, or remote publication are missing.

## Provision two operators

1. Each person signs in to their own Clerk account and chooses **Auditor** during first setup. Role binding is permanent. `evillegend045@gmail.com` and `abhi459.projects1@gmail.com` are the two intended accounts; confirm that they belong to different people before treating their signatures as independent.
2. Each person creates an encrypted Ed25519 vault on **their own device and operating-system account**. In their own Argus checkout, run `python scripts/init_witness_vault.py --name auditor.one` or `--name auditor.two`. The command asks for a passphrase without placing it in shell history. It creates `~/.argus-witness/<name>/private.pem` and `public.pem` outside the checkout. Never send the private key, passphrase, or retained state to Argus, Render, GitHub, or the other operator. The two Chrome profiles on one shared computer are useful for checking each Auditor account, but they are not separate key storage.
3. Give each person the latest Auditor evidence pack, a trusted copy of the origin checkpoint public key, and a current checkout of the **private anchor repository**. The pack may contain personnel data; transfer and store it accordingly. The public key must be checked through a separate trusted channel rather than taken solely from the evidence pack.
4. On separate machines, one operator at a time runs:

   ```powershell
   python scripts/cosign_private_anchor.py --bundle C:\path\evidence.arguspack --trusted-origin-key C:\path\trusted-origin.pem --anchor-manifest C:\path\private-anchor-repo\anchors.json --witness-private-key "$HOME\.argus-witness\auditor.one\private.pem" --state "$HOME\.argus-witness\auditor.one\witness-state.json" --name auditor.one
   ```

   The second operator uses `--name auditor.two`, their own encrypted key and state paths, and a fresh checkout containing the first operator's published signature. Each operator checks the manifest diff, commits it to the private anchor repository's `main`, and pushes. The Argus repository and both Render services continue to deploy from the Argus `main` only; publishing checkpoint evidence to the separate private anchor repository does not deploy application code. The retained state is signed by the witness key to detect edits; each operator still needs a separately retained backup to detect rollback.
5. Each operator supplies **only their public key** and chosen witness name to the Argus deployment operator. Independently confirm that the two custody domains represent different people or administrative controls. The deployment operator configures the backend Render variable `WITNESS_TRUST_CONFIG_JSON` as an object like:

   ```json
   {
     "auditor.one": {"public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n", "trust_domain": "operator-one"},
     "auditor.two": {"public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n", "trust_domain": "operator-two"}
   }
   ```

   `trust_domain` is an operator attestation, not something cryptography can establish. Do not use two labels for keys held by one person. `WITNESS_REQUIRED_THRESHOLD` defaults to 2. If the variable is absent, local development may instead use `.pem` and `.domain` files in `WITNESS_PUBLIC_KEYS_DIR`; this directory is ignored by Git.
6. Deploy the backend from Argus `main`. Sign in as an Auditor and check `/api/anchor/status` and the Auditor dashboard. The quorum should show 2 of 2 verified for the latest **published** checkpoint. Replacing a signature, altering an earlier checkpoint, removing a trust key, or assigning both witnesses the same domain must prevent a verified quorum. The database and private anchor checks must also pass. Check new events and republish a completed checkpoint before treating a new ledger tail as witnessed.

## Operational limits

- The witness state file is essential to continuity. Back it up under each operator's control. If lost, stop and investigate before bootstrapping the witness again.
- The anchor repository owner can hide or delete witness signatures, causing an unverified or failed status; they cannot forge signatures without the witness private keys. Witnesses should keep their own copy of signed manifests and check for unexpected changes.
- A compromised origin signing key or dishonest pack export can still affect what a witness sees. Each person must verify the pack independently and compare against their retained state. This workflow does not replace database backup, audit log review, or independent monitoring.
- Auditor logins and two keys under one administrator do not create separate trust domains. The live badge is contingent on the two actual operators and their key custody, which requires operational verification beyond software checks.
