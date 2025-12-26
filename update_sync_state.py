"""Update sync state based on current trades"""
import sqlite3
from datetime import datetime, timezone

db_path = 'data/trades.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create sync_state table if it doesn't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS sync_state (
        id INTEGER PRIMARY KEY,
        last_block_processed INTEGER,
        last_update_time INTEGER,
        monitor_instance TEXT,
        updated_at TEXT
    )
""")

# Insert initial row if table is empty
cursor.execute("SELECT COUNT(*) FROM sync_state")
if cursor.fetchone()[0] == 0:
    cursor.execute("""
        INSERT INTO sync_state (id, last_block_processed, last_update_time, monitor_instance, updated_at)
        VALUES (1, 0, 0, 'init', '')
    """)
    conn.commit()

# Get the highest block number from trades
cursor.execute("SELECT MAX(block_number) FROM trades")
max_block = cursor.fetchone()[0]

if max_block:
    now = datetime.now(timezone.utc)
    cursor.execute("""
        UPDATE sync_state
        SET last_block_processed = ?,
            last_update_time = ?,
            monitor_instance = 'manual_update',
            updated_at = ?
        WHERE id = 1
    """, (max_block, int(now.timestamp()), now.isoformat()))

    conn.commit()
    print(f"✓ Updated sync state to block {max_block:,}")

    cursor.execute("SELECT * FROM sync_state")
    row = cursor.fetchone()
    print(f"\nCurrent sync state:")
    print(f"  Last block processed: {row[1]:,}")
    print(f"  Last update: {datetime.fromtimestamp(row[2])}")
    print(f"  Instance: {row[3]}")
else:
    print("No trades found in database")

conn.close()
