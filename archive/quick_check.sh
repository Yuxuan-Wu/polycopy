#!/bin/bash
# Quick health check
echo "Quick System Check / 快速检查"
echo "================================"
PID=$(pgrep -f "python3 main.py" | tail -1)
if [ -n "$PID" ]; then
    echo "✓ Process running (PID: $PID)"
    echo "✓ Uptime: $(ps -p $PID -o etime= | xargs)"
    echo "✓ Memory: $(ps -p $PID -o rss= | awk '{printf "%.1f MB", $1/1024}')"
    echo ""
    echo "Monitored addresses:"
    grep "0x" config.yaml | grep -v "0x0000000000000000000000000000000000000000" | head -3
    echo ""
    echo "Trades detected: $(sqlite3 data/trades.db "SELECT COUNT(*) FROM trades;" 2>/dev/null || echo "0")"
else
    echo "✗ Process not running"
    exit 1
fi
