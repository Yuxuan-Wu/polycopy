#!/usr/bin/env python3
"""
Detect and mark incomplete positions (where sold > bought)
"""

import sqlite3
from datetime import datetime

def add_backfill_columns(db_path: str):
    """Add backfill tracking columns"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns exist
    cursor.execute("PRAGMA table_info(positions)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'is_complete' not in columns:
        print("Adding is_complete column...")
        cursor.execute("ALTER TABLE positions ADD COLUMN is_complete INTEGER DEFAULT NULL")
    
    if 'backfill_attempted' not in columns:
        print("Adding backfill_attempted column...")
        cursor.execute("ALTER TABLE positions ADD COLUMN backfill_attempted INTEGER DEFAULT 0")
    
    if 'backfill_date' not in columns:
        print("Adding backfill_date column...")
        cursor.execute("ALTER TABLE positions ADD COLUMN backfill_date TEXT DEFAULT NULL")
    
    conn.commit()
    conn.close()
    print("✓ Backfill columns added\n")

def detect_incomplete_positions(db_path: str):
    """Detect positions where sold > bought"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Find incomplete positions
    cursor.execute("""
        SELECT p.*, 
               (SELECT COUNT(*) FROM trades t 
                WHERE t.from_address = p.address AND t.token_id = p.token_id) as trade_count,
               (SELECT MIN(datetime(timestamp, 'unixepoch')) FROM trades t 
                WHERE t.from_address = p.address AND t.token_id = p.token_id) as first_trade
        FROM positions p
        WHERE (p.total_sold > p.total_bought + 0.01)
           OR (p.total_bought = 0 AND p.total_sold > 0)
        ORDER BY p.updated_at DESC
    """)
    
    positions = [dict(row) for row in cursor.fetchall()]
    
    print(f"Found {len(positions)} incomplete positions:\n")
    print("=" * 100)
    
    for idx, pos in enumerate(positions, 1):
        print(f"\n{idx}. Position: {pos['address'][:10]}.../{pos['token_id'][:16]}...")
        print(f"   Status: {pos['status']}")
        print(f"   Bought: {pos['total_bought']:.2f} tokens")
        print(f"   Sold: {pos['total_sold']:.2f} tokens")
        print(f"   Gap: {pos['total_sold'] - pos['total_bought']:.2f} tokens ({pos['trade_count']} trades recorded)")
        print(f"   First trade: {pos['first_trade']}")
        print(f"   Settlement: {pos.get('settlement_type', 'N/A')} @ ${pos.get('settlement_price', 0):.2f}")
        
        # Mark as incomplete
        cursor.execute("""
            UPDATE positions
            SET is_complete = 0
            WHERE address = ? AND token_id = ?
        """, (pos['address'], pos['token_id']))
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 100)
    print(f"\n✓ Marked {len(positions)} positions as incomplete")
    print("\nThese positions likely have missing buy transactions from before monitoring started.")
    print("To backfill historical data, run the full backfill script (will query blockchain history).")
    
    return positions

if __name__ == '__main__':
    db_path = 'data/trades.db'
    
    print("INCOMPLETE POSITION DETECTOR")
    print("=" * 100 + "\n")
    
    # Add columns
    add_backfill_columns(db_path)
    
    # Detect and mark incomplete positions
    detect_incomplete_positions(db_path)
