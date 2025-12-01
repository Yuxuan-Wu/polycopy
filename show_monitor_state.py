"""Show monitor sync state"""
import sqlite3

db_path = 'data/trades.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if there's any sync state tracking
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print("Database tables:", tables)
print("\nLooking for sync state...")

# Check if trades table has any block tracking
cursor.execute("SELECT MAX(block_number), MIN(block_number), COUNT(*) FROM trades")
max_block, min_block, count = cursor.fetchone()

print(f"\nTrades table:")
print(f"  Total trades: {count}")
print(f"  Block range: {min_block:,} to {max_block:,}")
print(f"  Span: {max_block - min_block:,} blocks")

conn.close()
