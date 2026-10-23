CREATE TABLE IF NOT EXISTS checkpoints (
    ordinal INTEGER PRIMARY KEY CHECK (ordinal > 0),
    checkpoint_id INTEGER NOT NULL UNIQUE CHECK (checkpoint_id > 0),
    sequence_id INTEGER NOT NULL UNIQUE CHECK (sequence_id > 0),
    checkpoint_hash TEXT NOT NULL
        CHECK (length(checkpoint_hash) = 64 AND checkpoint_hash NOT GLOB '*[^0-9a-f]*'),
    merkle_root TEXT NOT NULL
        CHECK (length(merkle_root) = 64 AND merkle_root NOT GLOB '*[^0-9a-f]*'),
    signature_hex TEXT NOT NULL
        CHECK (length(signature_hex) = 128 AND signature_hex NOT GLOB '*[^0-9a-f]*'),
    key_id TEXT NOT NULL CHECK (length(key_id) BETWEEN 1 AND 120)
);

CREATE TRIGGER IF NOT EXISTS checkpoints_append_only
BEFORE INSERT ON checkpoints
BEGIN
    SELECT CASE WHEN NEW.ordinal != COALESCE((SELECT MAX(ordinal) FROM checkpoints), 0) + 1
        OR NEW.checkpoint_id <= COALESCE((SELECT MAX(checkpoint_id) FROM checkpoints), 0)
        OR NEW.sequence_id <= COALESCE((SELECT MAX(sequence_id) FROM checkpoints), 0)
        THEN RAISE(ABORT, 'checkpoint history must be appended in order') END;
END;

CREATE TRIGGER IF NOT EXISTS checkpoints_no_update
BEFORE UPDATE ON checkpoints
BEGIN
    SELECT RAISE(ABORT, 'checkpoint history is immutable');
END;

CREATE TRIGGER IF NOT EXISTS checkpoints_no_delete
BEFORE DELETE ON checkpoints
BEGIN
    SELECT RAISE(ABORT, 'checkpoint history is immutable');
END;
