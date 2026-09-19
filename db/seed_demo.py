#!/usr/bin/env python3
"""Argus Curated Corporate Demo Dataset Seeder & Scale Engine.

Completely resets and seeds the Argus database with realistic corporate personnel,
multi-stage promotion timelines for Time-Travel demonstration, pre-seeded
suspicious risk alerts, and cryptographic audit chain verification.

Usage::

    python -m db.seed_demo              # Wipe & seed curated ~60 employee demo corpus
    python -m db.seed_demo --scale 5000  # Expand with 5,000 synthetic employees for scale testing
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import random
import sys
import time
from typing import Any

import dotenv
import psycopg2
import psycopg2.extras

dotenv.load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("argus.seed_demo")


def get_db_connection(db_url: str | None = None) -> Any:
    """Connect to PostgreSQL using DATABASE_URL or DATABASE_URL_MIGRATIONS."""
    url = (
        db_url
        or os.environ.get("DATABASE_URL_MIGRATIONS")
        or os.environ.get("DATABASE_URL")
    )
    if not url:
        logger.error("No database URL found in environment.")
        sys.exit(1)
    # Convert asyncpg scheme if needed
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
    return psycopg2.connect(url)


# ─── 1. COMPLETE ATOMIC PURGE ─────────────────────────────────────────────────
def purge_workforce_data(conn: Any) -> None:
    """Atomically truncate all workforce, salary, audit, and checkpoint tables.
    
    Resets chain_state to pristine genesis block #0 while preserving users.
    """
    logger.info("Purging existing test data and resetting audit ledger...")
    with conn.cursor() as cur:
        cur.execute("SET session_replication_role = 'replica'")
        cur.execute(
            """
            TRUNCATE TABLE
                suspicious_activity_flags,
                salary_history,
                audit_log,
                chain_checkpoints,
                backups,
                employees,
                roles,
                departments
            RESTART IDENTITY CASCADE;
            """
        )
        cur.execute(
            """
            UPDATE chain_state
            SET tail_hash = %s,
                tail_sequence_id = 0,
                last_checkpoint_sequence_id = 0
            WHERE id = 1;
            """,
            ("0" * 64,),
        )
        cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    logger.info("Purge complete. Hash chain reset to genesis block #0.")


# ─── 2. SEED CORPORATE DEPARTMENTS & ROLES ────────────────────────────────────
DEPARTMENTS_AND_ROLES = [
    (
        "Security Engineering",
        [
            ("Chief Information Security Officer (CISO)", 3500000, 6000000),
            ("Principal Security Architect", 2200000, 3800000),
            ("Cryptographic Systems Engineer", 1800000, 3200000),
            ("Senior Penetration Tester", 1400000, 2600000),
            ("Security Operations Analyst", 900000, 1600000),
        ],
    ),
    (
        "Compliance & Risk",
        [
            ("Chief Compliance Officer", 3200000, 5500000),
            ("Lead Forensic Auditor", 1800000, 3000000),
            ("Regulatory Risk Analyst", 1100000, 2000000),
            ("IT Governance Associate", 700000, 1300000),
        ],
    ),
    (
        "Cloud Infrastructure",
        [
            ("VP of Cloud Infrastructure", 3400000, 5800000),
            ("Staff Platform Architect", 2400000, 4000000),
            ("Senior Site Reliability Engineer", 1600000, 2800000),
            ("Cloud Systems Administrator", 950000, 1700000),
        ],
    ),
    (
        "Data & AI Systems",
        [
            ("Principal Data Engineer", 2300000, 3900000),
            ("MLOps Infrastructure Specialist", 1700000, 3000000),
            ("Lead Database Administrator", 1500000, 2700000),
            ("Data Intelligence Analyst", 850000, 1550000),
        ],
    ),
    (
        "People Operations",
        [
            ("Head of People & Culture", 2500000, 4200000),
            ("Senior HR Business Partner", 1400000, 2400000),
            ("Technical Talent Partner", 1000000, 1800000),
            ("HR Operations Specialist", 650000, 1200000),
        ],
    ),
    (
        "Financial Intelligence",
        [
            ("Financial Crime Controller", 2600000, 4500000),
            ("Senior Forensic Accountant", 1600000, 2900000),
            ("Anti-Fraud Analyst", 1000000, 1850000),
        ],
    ),
]


def seed_departments_and_roles(conn: Any) -> tuple[dict[str, int], dict[str, int]]:
    """Seed corporate departments and professional roles."""
    dept_map: dict[str, int] = {}
    role_map: dict[str, int] = {}

    with conn.cursor() as cur:
        cur.execute("SELECT department_id, name FROM departments;")
        for did, dname in cur.fetchall():
            dept_map[dname] = did

        cur.execute("SELECT role_id, title FROM roles;")
        for rid, rtitle in cur.fetchall():
            role_map[rtitle] = rid

        for dept_name, roles in DEPARTMENTS_AND_ROLES:
            if dept_name not in dept_map:
                cur.execute(
                    "INSERT INTO departments (name) VALUES (%s) RETURNING department_id",
                    (dept_name,),
                )
                dept_id = cur.fetchone()[0]
                dept_map[dept_name] = dept_id
            else:
                dept_id = dept_map[dept_name]

            for role_title, min_sal, max_sal in roles:
                if role_title not in role_map:
                    cur.execute(
                        """
                        INSERT INTO roles (department_id, title, salary_band_min, salary_band_max)
                        VALUES (%s, %s, %s, %s)
                        RETURNING role_id
                        """,
                        (dept_id, role_title, min_sal, max_sal),
                    )
                    role_id = cur.fetchone()[0]
                    role_map[role_title] = role_id

    conn.commit()
    logger.info("Loaded/Seeded %d departments and %d professional roles.", len(dept_map), len(role_map))
    return dept_map, role_map


# ─── 3. SEED CURATED DEMO WORKFORCE ───────────────────────────────────────────
DEMO_PERSONAS = [
    # ── TIME-TRAVEL HERO PERSONA (Marcus Vance: 3 Distinct Historical Eras)
    {
        "full_name": "Marcus Vance",
        "email": "marcus.vance@argus-security.io",
        "role_title": "Regulatory Risk Analyst",
        "date_hired": datetime.date(2024, 1, 15),
        "initial_salary": 650000,
        "is_active": True,
        "national_id": "ARGUS-NAT-0001-A",
        "contact_info": "+91 98201 54321 | 42 Cyber Gateway, Bangalore",
        "history": [
            # Era 2: Promoted to Lead Forensic Auditor
            {
                "type": "promotion",
                "role_title": "Lead Forensic Auditor",
                "salary": 1100000,
                "effective_date": datetime.date(2024, 7, 1),
            },
            # Era 3: Merit compensation adjustment
            {
                "type": "salary_bump",
                "salary": 1850000,
                "effective_date": datetime.date(2025, 2, 15),
            },
        ],
    },
    # ── SECURITY & INCIDENT ALERT HERO PERSONA (Elena Rostova)
    {
        "full_name": "Elena Rostova",
        "email": "elena.rostova@argus-security.io",
        "role_title": "Principal Security Architect",
        "date_hired": datetime.date(2023, 6, 10),
        "initial_salary": 2400000,
        "is_active": True,
        "national_id": "ARGUS-NAT-0002-B",
        "contact_info": "+91 99302 65432 | 108 Infotech Enclave, Hyderabad",
        "history": [
            # High-severity suspicious salary bump
            {
                "type": "suspicious_salary",
                "salary": 3600000,
                "effective_date": datetime.date(2024, 11, 20),
                "flag_reason": "Out-of-band off-hours compensation jump (+50%) from unrecognized IP (185.220.101.5)",
            }
        ],
    },
    # ── DEACTIVATED & ACCESS REVOCATION HERO PERSONA (Tariq Al-Mansoor)
    {
        "full_name": "Tariq Al-Mansoor",
        "email": "tariq.mansoor@argus-security.io",
        "role_title": "Senior Penetration Tester",
        "date_hired": datetime.date(2023, 8, 1),
        "initial_salary": 1750000,
        "is_active": False,  # Will be soft-deactivated with cryptographic audit record
        "national_id": "ARGUS-NAT-0003-C",
        "contact_info": "+91 97403 76543 | 12 Defense Colony, New Delhi",
        "history": [],
    },
]

# Additional curated workforce members across all departments
CURATED_COLLEAGUES = [
    # Security Engineering
    ("David Kim", "david.kim@argus-security.io", "Chief Information Security Officer (CISO)", datetime.date(2023, 1, 10), 4800000),
    ("Arjun Kapoor", "arjun.kapoor@argus-security.io", "Cryptographic Systems Engineer", datetime.date(2023, 4, 1), 2200000),
    ("Priya Sharma", "priya.sharma@argus-security.io", "Senior Penetration Tester", datetime.date(2023, 9, 15), 1850000),
    ("Liam O'Connor", "liam.oconnor@argus-security.io", "Security Operations Analyst", datetime.date(2024, 3, 20), 1100000),
    ("Zoe Kravitz", "zoe.kravitz@argus-security.io", "Security Operations Analyst", datetime.date(2024, 6, 1), 1050000),
    ("Vikram Malhotra", "vikram.malhotra@argus-security.io", "Cryptographic Systems Engineer", datetime.date(2023, 11, 10), 2400000),

    # Compliance & Risk
    ("Rachel Stern", "rachel.stern@argus-security.io", "Chief Compliance Officer", datetime.date(2023, 2, 1), 4200000),
    ("Maya Sundaram", "maya.sundaram@argus-security.io", "Lead Forensic Auditor", datetime.date(2023, 5, 12), 2100000),
    ("Carlos Santana", "carlos.santana@argus-security.io", "Regulatory Risk Analyst", datetime.date(2024, 2, 15), 1350000),
    ("Ananya Sen", "ananya.sen@argus-security.io", "IT Governance Associate", datetime.date(2024, 4, 1), 850000),
    ("Felix Baumgartner", "felix.baumgartner@argus-security.io", "IT Governance Associate", datetime.date(2024, 8, 10), 900000),

    # Cloud Infrastructure
    ("Siddharth Roy", "siddharth.roy@argus-security.io", "VP of Cloud Infrastructure", datetime.date(2023, 1, 15), 4500000),
    ("Chloe Dubois", "chloe.dubois@argus-security.io", "Staff Platform Architect", datetime.date(2023, 7, 1), 2800000),
    ("Rohan Joshi", "rohan.joshi@argus-security.io", "Senior Site Reliability Engineer", datetime.date(2023, 10, 1), 1950000),
    ("Kenji Takahashi", "kenji.takahashi@argus-security.io", "Senior Site Reliability Engineer", datetime.date(2024, 1, 10), 2050000),
    ("Fatima Al-Zahra", "fatima.alzahra@argus-security.io", "Cloud Systems Administrator", datetime.date(2024, 5, 15), 1150000),
    ("Alexei Volkov", "alexei.volkov@argus-security.io", "Cloud Systems Administrator", datetime.date(2024, 9, 1), 1200000),

    # Data & AI Systems
    ("Aarav Patel", "aarav.patel@argus-security.io", "Principal Data Engineer", datetime.date(2023, 3, 1), 2900000),
    ("Devika Nair", "devika.nair@argus-security.io", "MLOps Infrastructure Specialist", datetime.date(2023, 8, 15), 2300000),
    ("Sanjay Dutt", "sanjay.dutt@argus-security.io", "Lead Database Administrator", datetime.date(2023, 11, 1), 2100000),
    ("Neha Gupta", "neha.gupta@argus-security.io", "Data Intelligence Analyst", datetime.date(2024, 3, 1), 1150000),
    ("Gabriel Silva", "gabriel.silva@argus-security.io", "Data Intelligence Analyst", datetime.date(2024, 7, 10), 1200000),

    # People Operations
    ("Sarah Jenkins", "sarah.jenkins@argus-security.io", "Head of People & Culture", datetime.date(2023, 2, 10), 3200000),
    ("Kavita Krishnan", "kavita.krishnan@argus-security.io", "Senior HR Business Partner", datetime.date(2023, 6, 1), 1750000),
    ("Michael Zhang", "michael.zhang@argus-security.io", "Technical Talent Partner", datetime.date(2024, 1, 5), 1300000),
    ("Sneha Rao", "sneha.rao@argus-security.io", "HR Operations Specialist", datetime.date(2024, 4, 15), 850000),
    ("Lucas Moreau", "lucas.moreau@argus-security.io", "HR Operations Specialist", datetime.date(2024, 8, 20), 900000),

    # Financial Intelligence
    ("Deepak Verma", "deepak.verma@argus-security.io", "Financial Crime Controller", datetime.date(2023, 4, 15), 3600000),
    ("Sofia Rossi", "sofia.rossi@argus-security.io", "Senior Forensic Accountant", datetime.date(2023, 9, 1), 2200000),
    ("Aditya Birla", "aditya.birla@argus-security.io", "Anti-Fraud Analyst", datetime.date(2024, 2, 1), 1400000),
    ("Amina Diallo", "amina.diallo@argus-security.io", "Anti-Fraud Analyst", datetime.date(2024, 6, 15), 1450000),

    # Additional Corporate Workforce across Departments
    ("Oliver Queen", "oliver.queen@argus-security.io", "Senior Penetration Tester", datetime.date(2024, 1, 12), 1700000),
    ("Natasha Romanoff", "natasha.romanoff@argus-security.io", "Principal Security Architect", datetime.date(2023, 5, 20), 2500000),
    ("Bruce Wayne", "bruce.wayne@argus-security.io", "Chief Information Security Officer (CISO)", datetime.date(2023, 2, 1), 5200000),
    ("James Rhodes", "james.rhodes@argus-security.io", "Security Operations Analyst", datetime.date(2024, 7, 18), 980000),
    ("Harvey Dent", "harvey.dent@argus-security.io", "Chief Compliance Officer", datetime.date(2023, 3, 15), 3800000),
    ("Diana Prince", "diana.prince@argus-security.io", "Lead Forensic Auditor", datetime.date(2023, 8, 22), 2250000),
    ("Arthur Curry", "arthur.curry@argus-security.io", "Regulatory Risk Analyst", datetime.date(2024, 4, 10), 1250000),
    ("Victor Stone", "victor.stone@argus-security.io", "IT Governance Associate", datetime.date(2024, 9, 5), 890000),
    ("Tony Stark", "tony.stark@argus-security.io", "Staff Platform Architect", datetime.date(2023, 4, 10), 3100000),
    ("Peter Parker", "peter.parker@argus-security.io", "Senior Site Reliability Engineer", datetime.date(2024, 2, 28), 1650000),
    ("Stephen Strange", "stephen.strange@argus-security.io", "Cloud Systems Administrator", datetime.date(2024, 6, 12), 1180000),
    ("Wanda Maximoff", "wanda.maximoff@argus-security.io", "VP of Cloud Infrastructure", datetime.date(2023, 3, 1), 4600000),
    ("Bruce Banner", "bruce.banner@argus-security.io", "Principal Data Engineer", datetime.date(2023, 6, 15), 3200000),
    ("Hank Pym", "hank.pym@argus-security.io", "MLOps Infrastructure Specialist", datetime.date(2023, 9, 20), 2400000),
    ("Janet Van Dyne", "janet.vandyne@argus-security.io", "Lead Database Administrator", datetime.date(2024, 1, 15), 1900000),
    ("Scott Lang", "scott.lang@argus-security.io", "Data Intelligence Analyst", datetime.date(2024, 5, 22), 1100000),
    ("Hope Van Dyne", "hope.vandyne@argus-security.io", "Data Intelligence Analyst", datetime.date(2024, 8, 14), 1150000),
    ("Peggy Carter", "peggy.carter@argus-security.io", "Head of People & Culture", datetime.date(2023, 1, 20), 3400000),
    ("Sharon Carter", "sharon.carter@argus-security.io", "Senior HR Business Partner", datetime.date(2023, 7, 14), 1800000),
    ("Sam Wilson", "sam.wilson@argus-security.io", "Technical Talent Partner", datetime.date(2024, 3, 10), 1250000),
    ("Bucky Barnes", "bucky.barnes@argus-security.io", "HR Operations Specialist", datetime.date(2024, 7, 1), 880000),
    ("Matt Murdock", "matt.murdock@argus-security.io", "Financial Crime Controller", datetime.date(2023, 5, 5), 3100000),
    ("Jessica Jones", "jessica.jones@argus-security.io", "Senior Forensic Accountant", datetime.date(2023, 10, 18), 2150000),
    ("Luke Cage", "luke.cage@argus-security.io", "Anti-Fraud Analyst", datetime.date(2024, 3, 25), 1380000),
    ("Danny Rand", "danny.rand@argus-security.io", "Anti-Fraud Analyst", datetime.date(2024, 8, 30), 1420000),
    ("Frank Castle", "frank.castle@argus-security.io", "Senior Forensic Accountant", datetime.date(2023, 12, 1), 2350000),
]


def seed_curated_workforce(
    conn: Any,
    role_map: dict[str, int],
    actor_user_id: int = 0,
) -> dict[str, int]:
    """Insert curated employees, historical milestones, and anomaly flags."""
    employee_id_map: dict[str, int] = {}
    logger.info("Inserting curated corporate workforce...")

    with conn.cursor() as cur:
        # Set session actor variables for AFTER triggers
        cur.execute(f"SET argus.actor_user_id = '{actor_user_id}'")
        cur.execute("SET argus.actor_employee_id = '0'")

        # ── 1. Hero Personas ──────────────────────────────────────────────────
        for p in DEMO_PERSONAS:
            role_id = role_map[p["role_title"]]
            cur.execute(
                """
                INSERT INTO employees
                    (full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING employee_id;
                """,
                (
                    p["full_name"],
                    p["email"],
                    role_id,
                    p["national_id"].encode("utf-8"),
                    p["contact_info"].encode("utf-8"),
                    p["date_hired"],
                    True,  # Start active; Tariq is deactivated below to create audit event
                ),
            )
            emp_id = cur.fetchone()[0]
            employee_id_map[p["full_name"]] = emp_id

            # Initial Salary
            cur.execute(
                """
                INSERT INTO salary_history (employee_id, amount, effective_date)
                VALUES (%s, %s, %s);
                """,
                (emp_id, p["initial_salary"], p["date_hired"]),
            )
            conn.commit()
            time.sleep(0.05)

            # Historical Milestones
            for step in p["history"]:
                if step["type"] == "promotion":
                    new_role_id = role_map[step["role_title"]]
                    cur.execute(
                        "UPDATE employees SET role_id = %s WHERE employee_id = %s;",
                        (new_role_id, emp_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO salary_history (employee_id, amount, effective_date)
                        VALUES (%s, %s, %s);
                        """,
                        (emp_id, step["salary"], step["effective_date"]),
                    )
                    conn.commit()
                    time.sleep(0.05)
                elif step["type"] in ("salary_bump", "suspicious_salary"):
                    cur.execute(
                        """
                        INSERT INTO salary_history (employee_id, amount, effective_date)
                        VALUES (%s, %s, %s);
                        """,
                        (emp_id, step["salary"], step["effective_date"]),
                    )

                    # If suspicious, log an alert in suspicious_activity_flags
                    if step["type"] == "suspicious_salary":
                        cur.execute(
                            """
                            SELECT sequence_id FROM audit_log
                            WHERE employee_id = %s AND table_name = 'salary_history'
                            ORDER BY sequence_id DESC LIMIT 1;
                            """,
                            (emp_id,),
                        )
                        seq_id = cur.fetchone()[0]
                        cur.execute(
                            """
                            INSERT INTO suspicious_activity_flags
                                (audit_log_sequence_id, flag_reason, created_at)
                            VALUES (%s, %s, %s);
                            """,
                            (seq_id, step["flag_reason"], datetime.datetime.now(datetime.timezone.utc)),
                        )
                    conn.commit()
                    time.sleep(0.05)

            # Deactivation event if persona is inactive
            if not p["is_active"]:
                cur.execute(
                    "UPDATE employees SET is_active = FALSE WHERE employee_id = %s;",
                    (emp_id,),
                )
                conn.commit()
                time.sleep(0.05)

        # ── 2. Curated Colleagues ─────────────────────────────────────────────
        for idx, (name, email, title, hired, salary) in enumerate(CURATED_COLLEAGUES, start=4):
            role_id = role_map[title]
            nat_id = f"ARGUS-NAT-{idx:04d}-X"
            contact = f"+91 9{random.randint(1000, 9999)} {random.randint(10000, 99999)} | Corporate Campus, Sector {random.randint(1, 45)}"

            cur.execute(
                """
                INSERT INTO employees
                    (full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                RETURNING employee_id;
                """,
                (name, email, role_id, nat_id.encode("utf-8"), contact.encode("utf-8"), hired),
            )
            emp_id = cur.fetchone()[0]
            employee_id_map[name] = emp_id

            cur.execute(
                """
                INSERT INTO salary_history (employee_id, amount, effective_date)
                VALUES (%s, %s, %s);
                """,
                (emp_id, salary, hired),
            )

    conn.commit()
    logger.info("Successfully seeded curated workforce (%d employees).", len(employee_id_map))
    return employee_id_map


# ─── 4. HIGH-VOLUME SCALE GENERATOR (ON-DEMAND) ───────────────────────────────
def generate_scale_workforce(
    conn: Any,
    role_ids: list[int],
    num_scale: int,
    start_index: int = 100,
    batch_size: int = 1000,
) -> int:
    """Generate high-volume synthetic employees for 1,000s–10,000s scale testing."""
    if num_scale <= 0:
        return 0

    first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Pat", "Robin", "Devon", "Casey", "Avery", "Riley"]
    last_names = ["Anderson", "Bennett", "Campbell", "Donovan", "Edwards", "Fletcher", "Gibson", "Harper", "Ingram", "Jenkins", "Knight"]

    logger.info("Generating %d scale employees in batches of %d...", num_scale, batch_size)
    total_created = 0

    with conn.cursor() as cur:
        cur.execute("SET argus.actor_user_id = '0'")
        cur.execute("SET argus.actor_employee_id = '0'")

        batch: list[tuple] = []
        for i in range(num_scale):
            idx = start_index + i
            fn = random.choice(first_names)
            ln = random.choice(last_names)
            name = f"{fn} {ln}"
            email = f"{fn.lower()}.{ln.lower()}.{idx}@argus-security.io"
            role_id = random.choice(role_ids)
            nat_id = f"ARGUS-SCALE-{idx:06d}".encode("utf-8")
            contact = f"Extension #{idx} | Node {random.randint(1, 8)}".encode("utf-8")
            hired = datetime.date(2023, 1, 1) + datetime.timedelta(days=random.randint(0, 700))

            batch.append((name, email, role_id, nat_id, contact, hired, True))

            if len(batch) >= batch_size or i == num_scale - 1:
                cur_batch = batch
                batch = []
                query = """
                INSERT INTO employees
                    (full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired, is_active)
                VALUES %s
                RETURNING employee_id, date_hired;
                """
                inserted = psycopg2.extras.execute_values(cur, query, cur_batch, fetch=True)
                
                # Insert initial salaries
                salary_batch = [
                    (emp_id, random.randint(800000, 3000000), date_hired)
                    for emp_id, date_hired in inserted
                ]
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO salary_history (employee_id, amount, effective_date) VALUES %s",
                    salary_batch,
                )
                conn.commit()
                total_created += len(inserted)
                if total_created % 2000 == 0 or total_created == num_scale:
                    logger.info("  Scale progress: %d / %d employees inserted.", total_created, num_scale)

    logger.info("Successfully generated %d scale employees.", total_created)
    return total_created


# ─── 5. PROGRAMMATIC CHECKPOINT CREATION ──────────────────────────────────────
def create_initial_checkpoints(conn: Any) -> None:
    """Create and sign baseline checkpoints to anchor the initial seeded chain."""
    try:
        from db.cli.checkpoint_store import (
            get_latest_checkpoint,
            store_checkpoint,
            compute_checkpoint_hash,
        )
        from db.cli.signer import sign_checkpoint, LocalFileSigner

        key_path = os.environ.get("SIGNING_PRIVATE_KEY_PATH", "./keys/verifier_private_key.pem")
        signer = None
        if os.path.exists(key_path):
            signer = LocalFileSigner(key_path)

        with conn.cursor() as cur:
            cur.execute("SELECT sequence_id, entry_hash FROM audit_log ORDER BY sequence_id;")
            rows = cur.fetchall()

        if not rows:
            return

        interval = 25
        checkpoints_created = 0
        for i in range(interval, len(rows) + 1, interval):
            sub_hashes = [r[1] for r in rows[:i]]
            cp_hash = compute_checkpoint_hash(sub_hashes)
            seq_id = rows[i - 1][0]

            sig = b"mock_ed25519_signature_bytes_for_demo"
            if signer:
                try:
                    sig = sign_checkpoint(signer, cp_hash)
                except Exception:
                    pass

            stored = store_checkpoint(conn, seq_id, cp_hash, sig, key_id="local:ed25519:v1")
            if stored:
                checkpoints_created += 1

        logger.info("Generated and signed %d baseline checkpoints.", checkpoints_created)

        # Synchronize external anchor file anchor/2.json with seeded checkpoint 2
        try:
            os.makedirs("anchor", exist_ok=True)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at FROM chain_checkpoints WHERE checkpoint_id = 2;"
                )
                cp2 = cur.fetchone()
                if cp2:
                    import json
                    anchor_payload = {
                        "checkpoint_id": cp2[0],
                        "sequence_id": cp2[1],
                        "checkpoint_hash": cp2[2],
                        "signature_hex": bytes(cp2[3]).hex() if cp2[3] else "",
                        "created_at": cp2[4].isoformat() if cp2[4] else "",
                    }
                    with open("anchor/2.json", "w", encoding="utf-8") as f:
                        json.dump(anchor_payload, f)
                    logger.info("Synchronized anchor/2.json with seeded checkpoint #2.")
        except Exception as anchor_exc:
            logger.warning("External anchor sync skipped: %s", anchor_exc)

    except Exception as exc:
        logger.warning("Checkpoint generation skipped: %s", exc)


# ─── MAIN ORCHESTRATOR ────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Argus Curated Corporate Demo Dataset Seeder & Scale Engine."
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (defaults to DATABASE_URL / DATABASE_URL_MIGRATIONS).",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=0,
        help="Number of additional synthetic employees to generate for scale testing (e.g. 5000).",
    )
    parser.add_argument(
        "--skip-purge",
        action="store_true",
        help="Skip truncating existing data (appends new data).",
    )
    args = parser.parse_args()

    conn = get_db_connection(args.db_url)
    try:
        t0 = time.time()

        if not args.skip_purge:
            purge_workforce_data(conn)

        dept_map, role_map = seed_departments_and_roles(conn)
        employee_map = {}
        if not args.skip_purge:
            employee_map = seed_curated_workforce(conn, role_map)

        if args.scale > 0:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(employee_id), 0) FROM employees;")
                max_emp_id = cur.fetchone()[0]

            generate_scale_workforce(
                conn,
                list(role_map.values()),
                args.scale,
                start_index=max_emp_id + 1,
            )

        create_initial_checkpoints(conn)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM employees;")
            total_emp = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM salary_history;")
            total_sal = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM audit_log;")
            total_audit = cur.fetchone()[0]
            cur.execute("SELECT tail_sequence_id, tail_hash FROM chain_state WHERE id = 1;")
            chain_seq, chain_hash = cur.fetchone()

        elapsed = time.time() - t0
        print("\n" + "=" * 65)
        print(" ARGUS CORPORATE DEMO SEEDING COMPLETE")
        print("=" * 65)
        print(f" Employees in directory : {total_emp:,}")
        print(f" Salary history rows    : {total_sal:,}")
        print(f" Audit log events       : {total_audit:,}")
        print(f" Latest Chain Sequence  : #{chain_seq:,}")
        print(f" Current Tail Hash      : {chain_hash[:16]}...{chain_hash[-8:]}")
        print(f" Elapsed Time           : {elapsed:.2f}s")
        print("=" * 65)
        print(" Highlight Personas Ready for Demo:")
        print("  1. Marcus Vance (#1)     -> 3 Career Eras (2024 to 2025) for Time-Travel")
        print("  2. Elena Rostova (#2)    -> High-Severity Off-Hours Salary Alert for Risk")
        print("  3. Tariq Al-Mansoor (#3) -> Deactivated Personnel for Access Revocation")
        print("=" * 65 + "\n")

        return 0

    except Exception as exc:
        logger.exception("Seeding failed: %s", exc)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
