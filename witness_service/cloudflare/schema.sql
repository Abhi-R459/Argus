CREATE TABLE IF NOT EXISTS checkpoints (
    ordinal INTEGER PRIMARY KEY,
    checkpoint_id INTEGER NOT NULL UNIQUE,
    sequence_id INTEGER NOT NULL UNIQUE,
    row_json TEXT NOT NULL
);
