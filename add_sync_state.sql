-- Create sync state table
CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- 只允许一行
    last_block_processed INTEGER NOT NULL,
    last_update_time INTEGER NOT NULL,
    monitor_instance TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Insert initial state if not exists
INSERT OR IGNORE INTO sync_state (id, last_block_processed, last_update_time, created_at, updated_at)
VALUES (1, 0, 0, datetime('now'), datetime('now'));
