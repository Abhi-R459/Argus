# Argus Hackathon ER Diagram

![Panel-ready Argus data model](./ER_DIAGRAM.svg)

For a standalone image to place in slides, open or download [`ER_DIAGRAM.svg`](./ER_DIAGRAM.svg). Adminer remains useful for inspecting the live database, but its generated schema layout is not the presentation diagram.

This conceptual ER diagram shows the core relational model used in the HR audit prototype. Alembic migrations are the implementation source of truth; this diagram focuses on the entities needed to explain the payroll audit workflow to the review panel.

```mermaid
erDiagram
    DEPARTMENTS ||--o{ ROLES : contains
    ROLES ||--o{ EMPLOYEES : assigned_to
    EMPLOYEES ||--o{ SALARY_HISTORY : has_effective_dated_pay
    USERS ||--o{ AUDIT_LOG : performs
    EMPLOYEES o|--o{ AUDIT_LOG : is_subject_of
    AUDIT_LOG ||--o{ SUSPICIOUS_ACTIVITY_FLAGS : may_raise
    USERS o|--o{ SUSPICIOUS_ACTIVITY_FLAGS : reviews
    AUDIT_LOG ||--o{ CHAIN_CHECKPOINTS : checkpoint_boundary
    CHAIN_CHECKPOINTS o|--o{ BACKUPS : may_cover

    DEPARTMENTS {
        int department_id PK
        string name UK
    }
    ROLES {
        int role_id PK
        int department_id FK
        string title
        decimal salary_band_min
        decimal salary_band_max
    }
    USERS {
        int user_id PK
        string clerk_user_id UK
        string email UK
        string role
        boolean is_active
    }
    EMPLOYEES {
        int employee_id PK
        int role_id FK
        string email UK
        bytes national_id_encrypted
        bytes contact_info_encrypted
        boolean is_active
    }
    SALARY_HISTORY {
        int salary_history_id PK
        int employee_id FK
        decimal amount
        date effective_date
        datetime created_at
    }
    AUDIT_LOG {
        bigint sequence_id PK
        int actor_user_id FK
        int employee_id FK
        string action
        string table_name
        int row_id
        json old_value
        json new_value
        string previous_hash
        string entry_hash
        datetime created_at
    }
    SUSPICIOUS_ACTIVITY_FLAGS {
        int flag_id PK
        bigint audit_log_sequence_id FK
        int reviewed_by_user_id FK
        string flag_reason
        datetime reviewed_at
    }
    CHAIN_CHECKPOINTS {
        int checkpoint_id PK
        bigint sequence_id FK
        string checkpoint_hash
        bytes signature
        string key_id
        string merkle_root
        int merkle_leaf_count
        datetime created_at
    }
    CHAIN_STATE {
        int id PK
        bigint tail_sequence_id
        string tail_hash
        bigint last_checkpoint_sequence_id
    }
    BACKUPS {
        int backup_id PK
        int chain_checkpoint_id FK
        string backup_hash
        string file_reference
        datetime created_at
    }
```

## How to explain it

- `departments`, `roles`, `employees`, and `salary_history` are the HR business data. Salary rows are effective-dated so past and future compensation changes can be reconstructed.
- Each business mutation produces an `audit_log` event that identifies the actor and affected employee when known. The event stores before/after payloads and links to the previous event by hash.
- `chain_checkpoints` records signed boundaries in the audit sequence. A checkpoint covers the audit interval ending at its referenced sequence; inclusion proofs use the checkpoint's Merkle metadata when available.
- `suspicious_activity_flags` links a review item to the event that triggered it. A user can be recorded as the reviewer.
- `chain_state` is a singleton serialization point for safe hash-chain appends. It is shown separately because it is operational state, not a business entity.
- A backup may optionally reference a checkpoint that was current when the backup was made.

The diagram is a presentation view, not a migration. It omits implementation-only columns and tables. The compact schema contract is [`contracts/schema_contract.sql`](../../contracts/schema_contract.sql), and the migration set is under [`db/alembic/versions/`](../../db/alembic/versions/).
