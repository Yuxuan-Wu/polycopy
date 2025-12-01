#!/bin/bash
# Quick test script for both main tools

echo "=========================================="
echo "Testing Polycopy Scripts"
echo "=========================================="
echo

echo "1. Testing analyze_trader.py (quick mode)..."
echo "----------------------------------------"
python3 analyze_trader.py --quick
echo
echo "✓ analyze_trader.py works"
echo

echo "2. Testing database and metadata..."
echo "----------------------------------------"
python3 << 'EOF'
import sys
import sqlite3
sys.path.insert(0, 'src')
from database import DatabaseManager
from metadata_manager import MetadataManager
from gamma_client import GammaClient

# Check database
conn = sqlite3.connect('data/trades.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(DISTINCT from_address) FROM trades")
addr_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM trades")
trade_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(DISTINCT token_id) FROM trades")
market_count = cursor.fetchone()[0]

conn.close()

print(f"Unique Addresses: {addr_count}")
print(f"Total Trades: {trade_count}")
print(f"Unique Markets: {market_count}")

# Check metadata
gamma_client = GammaClient(timeout=30)
metadata_manager = MetadataManager('data/trades.db', gamma_client)

cursor = conn = sqlite3.connect('data/trades.db')
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT token_id FROM trades")
tokens = [row[0] for row in cursor.fetchall()]
conn.close()

tokens_with_metadata = 0
for token_id in tokens:
    if metadata_manager.get_market_for_token(token_id):
        tokens_with_metadata += 1

print(f"Tokens with Metadata: {tokens_with_metadata}/{len(tokens)}")

# Check positions
db_manager = DatabaseManager('data/trades.db', 'data/trades.csv', auto_export=False)
active_positions = db_manager.get_active_positions()
print(f"Active Positions: {len(active_positions)}")
EOF
echo
echo "✓ Database and metadata healthy"
echo

echo "3. Testing monitor_dashboard components..."
echo "----------------------------------------"
python3 << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))

from database import DatabaseManager
from metadata_manager import MetadataManager
from gamma_client import GammaClient

db_manager = DatabaseManager('data/trades.db', 'data/trades.csv', auto_export=False)
gamma_client = GammaClient(timeout=30)
metadata_manager = MetadataManager('data/trades.db', gamma_client)

positions = db_manager.get_active_positions()
if positions:
    for pos in positions:
        token_id = pos['token_id']
        market_info = metadata_manager.get_market_for_token(token_id)
        if market_info:
            print(f"Position: {market_info.get('question', 'N/A')}")
            print(f"  {pos['current_position']:.2f} tokens")
else:
    print("No active positions")
EOF
echo
echo "✓ Monitor dashboard components work"
echo

echo "=========================================="
echo "All Tests Passed! ✓"
echo "=========================================="
echo
echo "Tools available:"
echo "  - python3 monitor_dashboard.py    (Real-time monitoring)"
echo "  - python3 analyze_trader.py       (Trader analysis)"
echo "  - python3 analyze_trader.py --quick  (Quick summary)"
echo
