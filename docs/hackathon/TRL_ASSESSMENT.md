# Argus Technology Readiness Assessment

## Provisional rating: TRL 4

Argus is best described for this review as a **TRL 4 software prototype: integrated components have been exercised in a controlled local environment**. This is a provisional, self-assessed rating using NASA's Technology Readiness Level descriptions as a reference; those levels were designed for technology maturity assessment and are only an analogy for this software project. NASA describes TRL 4 as component and/or breadboard validation in a laboratory environment. See [NASA: Technology Readiness Levels](https://www.nasa.gov/directorates/somd/space-communications-navigation-program/technology-readiness-levels/).

## Evidence supporting the rating

- The prototype combines PostgreSQL mutation triggers, hash-linked audit events, signed checkpoints, a verifier CLI, an API, and an auditor UI.
- The local demo has exercised attack and recovery scenarios using synthetic HR records.
- The browser demonstrates verification results, audit evidence, historical reconstruction, counterfactual replay, and selective evidence proofs.
- The downloaded selective evidence capsule has been verified offline using a separately supplied trusted public key.

This supports a controlled lab-prototype rating. It does not establish readiness for deployment in a real payroll environment.

## Why this is not rated TRL 5 or higher

No evidence in the current project record establishes validation in an operationally relevant customer environment with representative real-world workloads, independently managed signing keys, durable off-host witnesses, production incident handling, or a validated rollout and support process. The local anchor and synthetic dataset are not substitutes for those conditions. The current demo's witness quorum is not persisted, and production signing requires a managed signer.

## Panel wording

> “We assess Argus provisionally at TRL 4: an integrated software prototype validated through controlled local demonstrations. It has not been validated in a live payroll environment, so we do not claim production readiness.”

## Evidence needed to raise readiness

1. Validate against an operationally relevant staging environment and representative, privacy-safe workload.
2. Integrate managed key custody, key rotation, and independent external witness/anchor services.
3. Complete deployment, monitoring, backup/restore, incident-response, and access-control rehearsals.
4. Gather acceptance evidence from intended HR and compliance users and document limitations and failure recovery.
