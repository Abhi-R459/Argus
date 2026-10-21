# Argus Hackathon Evaluation

## Status at the time this document was prepared

Argus has a working PostgreSQL prototype and has been exercised with four adversary scenarios in the local demo: historical row mutation, forward hash recomputation, checkpoint-signature forgery, and audit-row deletion. The corresponding UI and CLI flows expose verification evidence and recovery. This is functional security evidence, but it is not a statistically estimated detection rate or a production security certification.

The repository contains benchmark tooling and a historical report. Do **not** present the values in `db/bench/results/benchmark_report.md` as fresh measurements without rerunning them. In particular, `db/bench/run_full_benchmarks.py` writes fixed result rows rather than measuring a live database. Those fixtures are useful for checking report and plotting formats, not as current experimental evidence.

Accordingly, the project can demonstrate implemented behavior today, but its current measured improvement is **not yet established by a reproducible run in this checkout**. Fill in the results below after running the experiment on the stated isolated benchmark database.

## Evaluation question

Does checkpoint-bounded parallel verification reduce end-to-end audit-chain verification time as the audit history grows, while returning the same integrity result as the sequential verifier?

This evaluates the verifier's parallelization. It does not claim that Argus is faster than every conventional audit product, and it does not measure payroll fraud reduction.

## Design

| Element | Specification |
|---|---|
| Workload | Synthetic employee and salary-history mutations in PostgreSQL; use the seeder's fixed seed and report the actual number of generated audit rows. |
| Independent variable | Verification mode and worker count: sequential baseline, then parallel verifier at 1, 2, 4, and 8 workers. |
| Dependent measures | Median elapsed time, entries/second, speedup over the sequential median, and verifier validity/anomaly counts. |
| Repetitions | One warm-up invocation followed by at least 5 measured runs for each mode. Keep all individual observations in the CSV. |
| Controlled conditions | Same database snapshot, host, container limits, checkpoint boundaries, page size, Python version, and warm-cache policy for both modes. Record hardware and software versions. |
| Correctness check | Every mode must return valid for an intact chain. Run the same verifier after a controlled tamper on a disposable copy and record whether it detects the expected anomaly. |

Use the sequential verifier as the baseline. Compute `speedup = sequential median seconds / parallel median seconds`; report medians and the raw per-run CSV, not only the best run. Parallel verification can add overhead at low worker counts, so preserve and report results even when speedup is below 1×.

## Safe reproduction procedure

Run only against a dedicated disposable benchmark database. The benchmark's default setup clears seeded business, audit, checkpoint, and backup data. Never point it at the current demo, a shared database, or production.

1. Create a separate local PostgreSQL database and apply the project migrations and required benchmark roles/configuration.
2. Set `DATABASE_URL` to that disposable database. Use synthetic data only.
3. Seed a fixed synthetic workload once. This command clears the benchmark tables first; use it only on the disposable database:

   ```powershell
   $env:DATABASE_URL = "postgresql://<user>:<password>@localhost:5432/argus_benchmark"
   python -m db.bench.seed --db-url $env:DATABASE_URL --employees 35000 --salary-records 65000 --seed 20261008 --clear
   ```

4. Run one warm-up invocation on the seeded database, then run five measured repetitions against the same rows. `--skip-seed` is essential here so the benchmark will not clear or replace the dataset:

   ```powershell
   python -m db.bench.bench_parallel --db-url $env:DATABASE_URL --skip-seed --workers 1 2 4 8 --runs 1 --checkpoint-interval 250 --output docs/hackathon/results/parallel_100k_warmup.csv
   python -m db.bench.bench_parallel --db-url $env:DATABASE_URL --skip-seed --workers 1 2 4 8 --runs 5 --checkpoint-interval 250 --output docs/hackathon/results/parallel_100k.csv
   ```

   The first invocation also creates checkpoint boundaries on the fresh dataset. The second invocation reuses the same data and checkpoints.

5. Record the commit/revision identifier, database image/version, CPU, memory, OS, Docker resource limits, commands, actual audit-row count, checkpoint count, warm-up policy, and any failed runs in the results notes.
6. Confirm all measured rows report `is_valid=true` for the intact workload. Report sequential median and each parallel median, throughput, speedup, and any anomalies.
7. Preserve the generated CSV files and a short run log under `docs/hackathon/results/`. Do not hand-edit measurements.

The seeder's `--clear` option truncates benchmark tables and resets chain state. The parallel benchmark's default also clears and reseeds unless `--skip-seed` is specified. Even `--skip-seed` may append placeholder checkpoint rows if none exist, so run every step only on the dedicated disposable database.

## Results record — fill after a fresh run

| Mode | Workers | Median seconds | Entries/second | Speedup vs sequential | Valid runs / total |
|---|---:|---:|---:|---:|---:|
| Sequential baseline | 1 | Pending | Pending | 1.00× | Pending |
| Parallel | 1 | Pending | Pending | Pending | Pending |
| Parallel | 2 | Pending | Pending | Pending | Pending |
| Parallel | 4 | Pending | Pending | Pending | Pending |
| Parallel | 8 | Pending | Pending | Pending | Pending |

**Dataset size:** Pending. **Checkpoint interval:** 250 (configured). **Host and database configuration:** Pending. **Raw CSV:** Pending.

## Functional attack evidence

The project history records local CLI/browser demonstrations of the following scenarios and their subsequent self-healing. Present these as functional demonstrations, not a statistical benchmark:

| Scenario | Expected verifier evidence | Demo evidence |
|---|---|---|
| Mutate a historical business row | Hash-chain mismatch at or after the changed event | Local CLI/browser attack demonstration recorded; healed afterward |
| Recompute forward hashes after a historical edit | Chain may appear continuous, but trusted checkpoint/anchor evidence no longer matches | Local CLI/browser attack demonstration recorded; healed afterward |
| Forge a checkpoint signature | Signature verification fails; show checkpoint identity and before/stored signature evidence when available | Local CLI/browser attack demonstration recorded; healed afterward |
| Delete a historical audit row | Sequence gap and/or checkpoint/anchor mismatch, with saved event context when available | Local CLI/browser attack demonstration recorded; healed afterward |

For a panel demo, show one intact verification, one attack, the resulting verifier evidence, and the recovery result. Be explicit that the local file anchor is not an independent trust domain and that the witness quorum is not configured in the local demo.

## Limits and next measurement

- The four attack scenarios establish that the shown cases are demonstrable; they do not establish a general false-positive or false-negative rate.
- Synthetic employee data does not establish impact on a real payroll operation.
- Salary-rate exposure is not payroll disbursement reconciliation.
- The local demo does not establish independent off-host key custody, durable external witnesses, or production readiness.
- The next evaluation deliverable is a fresh benchmark run with raw CSV, documented environment, repeatable workload, and an independent correctness check. Only then replace the pending table with measured values.
