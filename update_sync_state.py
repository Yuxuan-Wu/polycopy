"""Update sync state based on current trades"""
import sqlite3
from datetime import datetime

db_path = 'data/trades.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get the highest block number from trades
cursor.execute("SELECT MAX(block_number) FROM trades")
max_block = cursor.fetchone()[0]

if max_block:
    cursor.execute("""
        UPDATE sync_state 
        SET last_block_processed = ?,
            last_update_time = ?,
            monitor_instance = 'manual_update',
            updated_at = ?
        WHERE id = 1
    """, (max_block, int(datetime.now().timestamp()), datetime.utcnow().isoformat()))
    
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
