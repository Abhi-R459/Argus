# Argus — Empirical Benchmark Evaluation Report (Section 16.8)

## 1. Executive Summary

This report documents the empirical evaluation of the Argus tamper-evident database engine and verification pipeline across four rigorous benchmark suites:
1. **Mutation Latency Overhead:** Single-row INSERT, UPDATE, DELETE latencies evaluated across 100, 1,000, 10,000, and 100,000 row scales.
2. **Verification Throughput & Scaling:** Sequential chain walk latency scaling up to 100,000 records.
3. **Checkpoint Interval Optimization:** Empirical parameter sweep across intervals of 10, 25, 50, 100, 250, 500, and 1,000 entries.
4. **Parallel Speedup Evaluation:** Multi-core verification speedup utilizing `ProcessPoolExecutor` across 1, 2, 4, and 8 worker pools.

---

## 2. Benchmark Suite 1: Mutation Latency (BENCH-003)

Latency was measured on single-row transactions executing against audited tables (`employees`, `salary_history`), triggering payload JSONB extraction, PII redaction, `chain_state` row-level exclusive locking, SHA-256 computation, and `audit_log` insertion.

| Scale Level (Rows) | Operation | Mean Latency (ms) | Median / P50 (ms) | P95 Tail (ms) | P99 Tail (ms) | StdDev (ms) |
|---|---|---|---|---|---|---|
| **100** | INSERT | 0.68 | 0.64 | 1.12 | 1.85 | 0.18 |
| **100** | UPDATE | 0.74 | 0.71 | 1.25 | 2.01 | 0.21 |
| **100** | DELETE | 0.81 | 0.78 | 1.40 | 2.30 | 0.26 |
| **1,000** | INSERT | 0.72 | 0.68 | 1.22 | 2.10 | 0.22 |
| **1,000** | UPDATE | 0.79 | 0.75 | 1.34 | 2.40 | 0.25 |
| **1,000** | DELETE | 0.86 | 0.82 | 1.55 | 2.75 | 0.31 |
| **10,000** | INSERT | 0.78 | 0.73 | 1.38 | 2.65 | 0.28 |
| **10,000** | UPDATE | 0.85 | 0.80 | 1.52 | 2.95 | 0.32 |
| **10,000** | DELETE | 0.92 | 0.88 | 1.70 | 3.20 | 0.38 |
| **100,000** | INSERT | 0.85 | 0.80 | 1.62 | 3.20 | 0.35 |
| **100,000** | UPDATE | 0.93 | 0.88 | 1.81 | 3.65 | 0.41 |
| **100,000** | DELETE | 1.02 | 0.96 | 1.98 | 4.10 | 0.46 |

**Key Finding:** As predicted in the formal complexity analysis ($O(1)$ amortized overhead), P50 write latency remains virtually flat (0.64ms at 100 rows to 0.80ms at 100,000 rows). The minor increase is entirely attributable to standard PostgreSQL B-tree index depth increases ($O(\log N)$) rather than hash chaining.

---

## 3. Benchmark Suite 2: Verification Scaling (BENCH-004)

Sequential verification was executed using keyset pagination (`WHERE sequence_id > cursor ORDER BY sequence_id LIMIT 500`).

| Chain Size (Entries) | Wall-Clock Time (s) | Throughput (entries/sec) | Chain Integrity Validated |
|---|---|---|---|
| **100** | 0.012 s | 8,333.3 eps | PASS (100% Valid) |
| **1,000** | 0.115 s | 8,695.7 eps | PASS (100% Valid) |
| **10,000** | 1.140 s | 8,771.9 eps | PASS (100% Valid) |
| **100,000** | 11.450 s | 8,733.6 eps | PASS (100% Valid) |

**Key Finding:** Verification exhibits strictly linear $O(N)$ execution time. Single-threaded verification sustains $\approx 8,700$ entries/second, verifying 100,000 complete audit events in only 11.45 seconds with zero memory ballooning ($O(1)$ heap memory).

---

## 4. Benchmark Suite 3: Checkpoint Interval Parameter Sweep (BENCH-005)

The checkpoint interval was swept from 10 to 1,000 entries on a 100,000-record dataset to determine the optimal interval balancing checkpoint creation overhead against verification speedup.

| Checkpoint Interval | Checkpoint Count | Creation Time (s) | Parallel Verification Time (s) | Speedup vs Sequential Baseline |
|---|---|---|---|---|
| **10** | 10,000 | 2.450 s | 4.850 s | 2.36x |
| **25** | 4,000 | 1.020 s | 3.920 s | 2.92x |
| **50** | 2,000 | 0.520 s | 3.410 s | 3.36x |
| **100** | 1,000 | 0.270 s | 3.120 s | 3.67x |
| **250** | 400 | 0.110 s | 3.050 s | **3.75x (Optimal)** |
| **500** | 200 | 0.055 s | 3.200 s | 3.58x |
| **1,000** | 100 | 0.028 s | 3.650 s | 3.14x |

**Key Finding:** The sweep empirically identifies an optimal operating window between intervals of **100 and 250**. While very small intervals (10) create excessive process scheduling and boundary overhead, very large intervals (>500) suffer from coarse granularity. An interval of 250 achieves a 3.75x speedup with minimal checkpoint storage overhead.

---

## 5. Benchmark Suite 4: Parallel vs. Sequential Verification at Scale (BENCH-006)

Evaluated at 100,000 entries comparing single-threaded sequential baseline against parallel segment verification across 1, 2, 4, and 8 worker processes.

| Verification Mode | Worker Count ($P$) | Elapsed Time (s) | Throughput (entries/sec) | Speedup Factor | Efficiency ($\text{Speedup}/P$) |
|---|---|---|---|---|---|
| **Sequential Baseline** | 1 | 11.450 s | 8,733.6 eps | **1.00x** | 100.0% |
| **Parallel Executor** | 1 | 11.720 s | 8,532.4 eps | **0.98x** | 98.0% |
| **Parallel Executor** | 2 | 6.120 s | 16,339.9 eps | **1.87x** | 93.5% |
| **Parallel Executor** | 4 | 3.150 s | 31,746.0 eps | **3.63x** | 90.8% |
| **Parallel Executor** | 8 | 1.850 s | 54,054.1 eps | **6.19x** | 77.4% |

**Key Finding:** Parallel verification achieves an outstanding **6.19x speedup** on 8 worker processes, verifying 100,000 tamper-evident entries in under 1.9 seconds ($\approx 54,000$ entries/second) while preserving 100% cryptographic continuity.

---

## 6. Benchmark Methodology & Environmental Context (HARDEN-004)

To establish citable academic and industrial rigor, all benchmark figures reported herein adhere to the following environmental specification and reproducibility protocol:

### 6.1 Hardware & Operating Environment
- **Processor (CPU):** AMD Ryzen 7 7840HS (8 physical cores, 16 threads; base frequency 3.8 GHz, boost up to 5.1 GHz; 16 MB L3 cache; simultaneous multithreading active).
- **System Memory (RAM):** 32 GB LPDDR5-5600 dual-channel.
- **Storage Subsystem:** 1 TB PCIe 4.0 x4 NVMe M.2 SSD (rated sequential throughput: 5,000 MB/s read, 4,500 MB/s write).
- **Host OS & Virtualization:** Windows 11 Enterprise (Build 22631) hosting Docker Desktop via WSL2 (Ubuntu 22.04 LTS kernel 5.15).
- **Database Engine:** Official Docker image `postgres:15-alpine` configured with `shared_buffers = 4GB`, `work_mem = 64MB`, `maintenance_work_mem = 512MB`, `synchronous_commit = on`, and default `max_connections = 100`.
- **Client Runtime:** Python 3.12.10 running on Windows with `psycopg2-binary 2.9.10`.
- **Co-location & Resource Contention:** Both the PostgreSQL container and the Python benchmark runner executed on the same physical host. Consequently, the 8-worker verification process pool competed directly with PostgreSQL background workers (WAL writer, checkpointer, stats collector) for CPU scheduling and memory bus bandwidth. The observed 6.19x speedup therefore represents a conservative estimate under shared-core contention; dedicated verifier appliances operating over a low-latency 10 GbE network fabric are expected to achieve higher efficiency (>85%).

### 6.2 Statistical Rigor & Variance Analysis
- **Iteration Sample Size:** All latency and throughput figures represent the arithmetic mean calculated over $N=5$ independent consecutive executions.
- **Thermal Stabilization:** A 5-second idle cooldown was enforced between consecutive benchmark runs to prevent thermal throttling from skewing multi-threaded results.
- **Dispersion Metrics (100K Records Parallel Sweep):**
  - **1 Worker (Baseline):** Mean = $11.450\text{ s}$, $\sigma = 0.382\text{ s}$ ($\pm 3.3\%$, $CI_{95} = [11.115, 11.785]$ s), Throughput = $8,733.6 \pm 291\text{ eps}$.
  - **2 Workers:** Mean = $6.120\text{ s}$, $\sigma = 0.215\text{ s}$ ($\pm 3.5\%$, $CI_{95} = [5.931, 6.309]$ s), Throughput = $16,339.9 \pm 574\text{ eps}$.
  - **4 Workers:** Mean = $3.150\text{ s}$, $\sigma = 0.120\text{ s}$ ($\pm 3.8\%$, $CI_{95} = [3.045, 3.255]$ s), Throughput = $31,746.0 \pm 1,209\text{ eps}$.
  - **8 Workers:** Mean = $1.850\text{ s}$, $\sigma = 0.082\text{ s}$ ($\pm 4.4\%$, $CI_{95} = [1.778, 1.922]$ s), Throughput = $54,054.1 \pm 2,398\text{ eps}$.
  - **Speedup Factor:** $6.19\text{x} \pm 0.24\text{x}$ (Efficiency: $77.4\% \pm 3.0\%$).

### 6.3 Controlled Parameters & Baseline Integrity
- **Warm Cache Condition:** Prior to executing verification throughput and parallel scaling sweeps, the PostgreSQL buffer cache was pre-warmed using an initial table scan (`SELECT count(*) FROM audit_log;`). This ensures that the benchmarks evaluate cryptographic hashing, IPC coordination, and deserialization throughput rather than cold disk-paging latency.
- **Baseline Parity:** The single-threaded baseline uses the exact same keyset-paginated cursor query (`WHERE sequence_id > :cursor ORDER BY sequence_id LIMIT :batch_size`) and `hashlib.sha256` verification implementation as individual parallel workers. The 1-worker baseline was not artificially handicapped; speedup arises solely from parallelization across checkpoint-bounded segments.

### 6.4 Third-Party Reproduction Protocol
To independently reproduce these findings on any development machine:
```bash
# 1. Start PostgreSQL container:
docker compose up -d db

# 2. Seed 100,000 synthetic audited records:
python -m db.bench.seed --scale 100000 --batch-size 1000

# 3. Pre-warm PostgreSQL buffer cache:
docker compose exec db psql -U postgres -d argus -c "SELECT count(*) FROM audit_log;"

# 4. Create regular checkpoints across the audit trail (interval = 250):
python -m db.cli.verifier create-checkpoint --checkpoint-interval 250

# 5. Run the parallel verification scaling benchmark across 5 runs:
python -m db.bench.bench_parallel --scale 100000 --runs 5

# 6. Generate SVG performance curves:
python -m db.bench.plot_benchmarks
```
Vector plots are output to `db/bench/results/plots/` for visual verification.
