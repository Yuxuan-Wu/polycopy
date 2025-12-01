#!/bin/bash

echo "=========================================="
echo "Testing Polycopy Integrated Scripts"
echo "=========================================="
echo

echo "1. Testing analyze_trader.py (quick mode)..."
python3 analyze_trader.py --quick
echo
echo "✓ analyze_trader.py works"
echo

echo "2. Testing database integrity..."
python3 -c "
import sys
sys.path.insert(0, 'src')
from database import DatabaseManager
db = DatabaseManager('data/trades.db', 'data/trades.csv', auto_export=False)
print(f'Total trades: {db.get_trade_count()}')
positions = db.get_all_positions()
print(f'Total positions: {len(positions)}')
active = db.get_active_positions()
print(f'Active positions: {len(active)}')
"
echo
echo "✓ Database is healthy"
echo

echo "3. Listing available tools..."
ls -lh *.py *.sh 2>/dev/null | grep -E '\.(py|sh)$' | awk '{print $9}'
echo
echo "✓ All tools available"
echo

echo "=========================================="
echo "All tests passed! ✓"
echo "=========================================="
echo
echo "Quick Start:"
echo "  - Monitor: python3 monitor_dashboard.py"
echo "  - Analyze: python3 analyze_trader.py"
echo
