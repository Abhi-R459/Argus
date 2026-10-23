# Automatic independent witnesses without a GitHub anchor

Argus can use two separately operated Cloudflare Workers and D1 databases as its external checkpoint anchor. GitHub Actions runs the publisher every ten minutes, but GitHub is **only the scheduler**; it does not hold the anchor. A signed-in customer does not create keys, run commands, or manage witness services.

## Trust and data flow

1. The Argus database stores signed checkpoints. The scheduled publisher connects with the read-only `compliance_auditor` role and, in one repeatable-read snapshot, verifies the full audit hash chain and checkpoint bindings before sending anything.
2. The publisher sends only checkpoint IDs, sequence IDs, hashes, Merkle roots, origin signatures, and key IDs. It does not send personnel rows, compensation values, or audit payloads.
3. Each operator's Worker verifies the origin signature, compares the entire submitted prefix with its own D1 history, and atomically appends new rows. It refuses changed or shortened history. Each Worker signs the complete retained prefix with its own Ed25519 key and exposes a signed readback.
4. The Argus API reads both Workers with **read-only** tokens. It compares their histories to PostgreSQL, verifies signatures against pinned public keys, and requires two distinct configured custody domains. A missing service is **Unverified**; a conflicting retained history is **Mismatch**. Neither the API nor the publisher holds a witness private key.

This is Argus's versioned checkpoint-prefix protocol, **not** RFC 9162 or C2SP consistency proofs. It establishes that independently operated witnesses retained a specific ordered checkpoint history. As with any anchor, it does not make a false origin-signed checkpoint true; the scheduled publisher independently verifies the current database evidence before submitting it. Loss or rollback of an operator's D1 state requires investigation and recovery from that operator's retained backup, never silent rebootstrap.

## Operator provisioning

These steps are performed once by the Argus release operator and the two witness operators, not by customers. Ordinary HR and Auditor accounts do not connect to Cloudflare. A future in-app "Connect witness" flow could use Cloudflare OAuth for operator provisioning, but each independent operator would still need to sign in to their own Cloudflare account and approve access once. No such connection flow is currently deployed.

- Each witness operator provisions a separate Cloudflare account, Worker, D1 database, and Ed25519 private key. Use `witness_service/cloudflare/worker.mjs`, `schema.sql`, and `wrangler.toml.example`. The signing key is a Cloudflare Worker secret in that operator's account. Keep the account, key, D1 database, and state backups under that person's control; Chrome profiles or two Argus Auditor logins on one computer do not create independent custody.
- Each D1 store keeps checkpoint fields in constrained columns. Database triggers reject out-of-order inserts and all updates and deletes. The Worker also verifies origin signatures and the retained prefix before signing a receipt; application checks and database constraints protect different failure paths.
- Each Worker has `WITNESS_NAME`, `WITNESS_PRIVATE_KEY_PEM`, `ORIGIN_PUBLIC_KEY_PEM`, `WITNESS_READ_TOKEN`, and `WITNESS_PUBLISH_TOKEN` secrets. Read and publish tokens must differ, be independently random, and stay out of source control. The origin public key is checked through a trusted channel and must match Argus's checkpoint signing key. Only the operator's **public** witness key is given to Argus.
- The release operator pins each witness's public key and distinct `trust_domain` in `WITNESS_TRUST_CONFIG_JSON`. This setting is public-key material, but keep it consistent across the publisher and backend.
- The GitHub Actions workflow `publish-witness-quorum.yml` receives the read-only `DATABASE_URL_COMPLIANCE_AUDITOR`, `ORIGIN_PUBLIC_KEY_PEM`, `WITNESS_PUBLISH_ENDPOINTS_JSON`, `WITNESS_READ_ENDPOINTS_JSON`, and `WITNESS_TRUST_CONFIG_JSON` as repository secrets. Each endpoints value is an array of `{"name":"operator.one","url":"https://...","token":"<token>"}` objects. Names and URLs match between arrays; publish and read tokens differ. After the two services and a first signed checkpoint are verified, set repository variable `WITNESS_AUTOMATION_ENABLED=true`. The workflow is limited to Argus `main` and has read-only repository permissions.
- The backend Render service receives `WITNESS_READ_ENDPOINTS_JSON` with the same names and URLs but **read tokens**, plus `WITNESS_TRUST_CONFIG_JSON` and `WITNESS_MIN_SEQUENCE` pinned to the first externally retained checkpoint. Set `ANCHOR_STORE=witness_services` after live readback passes. Both Render services continue to deploy application code from Argus `main` only.

No service uses the old private GitHub anchor write credential. Keep the old GitHub anchor and its read-only configuration available during migration so the existing app release rollback can restore the prior path. Switching the backend to `witness_services` is a separate production change and should be followed by authenticated `/api/anchor/status`, `/api/verify`, and Auditor dashboard checks.

## Limits and operations

The current protocol caps a prefix at 1,000 checkpoints and a request at 1 MB. Plan an archival or epoch format before either limit is reached. At the October 2026 published limits, Workers Free allows 100,000 requests a day and D1 Free includes 5 million rows read, 100,000 rows written per day, and 5 GB total storage. Free allowances can change or fail closed when exceeded; alert on a failed scheduled publication or an unverified quorum. Two accounts on Cloudflare provide separate **operators and keys**, but still share one cloud provider and its availability risk. For stronger provider diversity, run the same protocol on a second provider with durable storage.

The signed head is read during every Auditor status check. There is no claim of a live production quorum until both independently controlled deployments, publisher schedule, pinned keys, and signed-in readback have passed.
