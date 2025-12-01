#!/usr/bin/env python3
"""
Test dashboard display improvements
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import DatabaseManager
from metadata_manager import MetadataManager
from gamma_client import GammaClient

# Initialize
db_manager = DatabaseManager('data/trades.db', 'data/trades.csv', auto_export=False)
gamma_client = GammaClient(timeout=30)
metadata_manager = MetadataManager('data/trades.db', gamma_client)

print("=" * 100)
print("📋 RECENT TRADES TEST (Improved Display)")
print("=" * 100)

# Get recent trades
import sqlite3
conn = sqlite3.connect('data/trades.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT tx_hash, timestamp, from_address, token_id, amount, price, side, capture_delay_seconds
    FROM trades
    ORDER BY timestamp DESC
    LIMIT 5
""")

trades = [dict(row) for row in cursor.fetchall()]
conn.close()

from datetime import datetime

for trade in trades:
    token_id = trade['token_id']
    market_info = metadata_manager.get_market_for_token(token_id) if token_id else None

    # Show full question (up to 80 chars) with ellipsis if needed
    if market_info:
        full_question = market_info.get('question', 'N/A')
        market_question = full_question if len(full_question) <= 80 else full_question[:77] + '...'
    else:
        market_question = 'N/A'

    outcome = market_info.get('outcome_name', 'N/A') if market_info else 'N/A'

    delay_emoji = "⚡" if trade['capture_delay_seconds'] and trade['capture_delay_seconds'] < 60 else \
                 "⏱️" if trade['capture_delay_seconds'] and trade['capture_delay_seconds'] < 300 else \
                 "⚠️" if trade['capture_delay_seconds'] and trade['capture_delay_seconds'] < 3600 else "⏰"

    timestamp = datetime.fromtimestamp(trade['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

    print(f"{delay_emoji} {timestamp} | {trade['side'].upper():4} | "
          f"{trade['amount']:>10} @ ${trade['price']:<6} | {outcome:8}")
    print(f"   Market: {market_question}")
    print()

print("\n" + "=" * 100)
print("💼 ACTIVE POSITIONS TEST (Improved Display)")
print("=" * 100)

positions = db_manager.get_active_positions()
incomplete_count = 0

for pos in positions[:3]:  # Show first 3
    token_id = pos['token_id']
    market_info = metadata_manager.get_market_for_token(token_id) if token_id else None

    if market_info:
        question = market_info.get('question', 'N/A')
        outcome = market_info.get('outcome_name', 'N/A')
        current_price = market_info.get('outcome_price', 0)
    else:
        question = f"Token {token_id[:20]}..."
        outcome = 'N/A'
        current_price = 0

    current_value = pos['current_position'] * current_price
    cost_basis = pos['current_position'] * (pos['avg_buy_price'] or 0)
    unrealized_pnl = current_value - cost_basis

    # Status emoji with incomplete warning
    if pos.get('is_complete') == 0:
        status_emoji = '⚠️'
        incomplete_count += 1
        status_text = 'INCOMPLETE'
    elif pos['status'] == 'active':
        status_emoji = '🟢'
        status_text = 'ACTIVE'
    else:
        status_emoji = '⚪'
        status_text = pos['status'].upper()

    # Display full question (no truncation)
    print(f"{status_emoji} [{status_text}] {question}")
    print(f"   Outcome: {outcome:10} | Position: {pos['current_position']:>10.2f} tokens | "
          f"Avg: ${pos['avg_buy_price'] or 0:.4f} | Current: ${current_price:.4f}")
    print(f"   Bought: {pos['total_bought']:.2f} | Sold: {pos['total_sold']:.2f} | "
          f"Cost: ${cost_basis:.2f} | Value: ${current_value:.2f} | Unrealized: ${unrealized_pnl:+.2f}")
    print()

print("-" * 100)
print(f"Total: {len(positions)} active positions", end='')
if incomplete_count > 0:
    print(f" (⚠️  {incomplete_count} incomplete - missing trades >7 days old)")
else:
    print()
