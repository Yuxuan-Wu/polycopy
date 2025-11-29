#!/bin/bash
# Quick status check for Polycopy Monitor

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================="
echo "  Polycopy Monitor Status"
echo "========================================="
echo ""

# Check if process is running
PROCESS_PID=$(pgrep -f "python3.*main.py" | head -1)
if [ -n "$PROCESS_PID" ]; then
    UPTIME=$(ps -p $PROCESS_PID -o etime= | xargs)
    MEM=$(ps -p $PROCESS_PID -o rss= | awk '{printf "%.1f MB", $1/1024}')
    CPU=$(ps -p $PROCESS_PID -o %cpu= | xargs)
    echo -e "${GREEN}✓ Process Status: RUNNING${NC}"
    echo "  PID: $PROCESS_PID"
    echo "  Uptime: $UPTIME"
    echo "  Memory: $MEM"
    echo "  CPU: ${CPU}%"
else
    echo -e "${RED}✗ Process Status: NOT RUNNING${NC}"
fi
echo ""

# Check database
DB_FILE="data/trades.db"
if [ -f "$DB_FILE" ]; then
    TOTAL_TRADES=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM trades;" 2>/dev/null)
    DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
    echo -e "${GREEN}✓ Database: EXISTS${NC}"
    echo "  Total Trades: $TOTAL_TRADES"
    echo "  Size: $DB_SIZE"

    # Show trades per address
    echo ""
    echo "  Trades per Address:"
    sqlite3 "$DB_FILE" "SELECT from_address, COUNT(*) as cnt FROM trades GROUP BY from_address ORDER BY cnt DESC;" 2>/dev/null | while IFS='|' read -r addr count; do
        short_addr="${addr:0:10}...${addr: -4}"
        echo "    $short_addr: $count trades"
    done
else
    echo -e "${YELLOW}⚠ Database: NOT FOUND${NC}"
fi
echo ""

# Check log file
LOG_FILE="logs/polycopy.log"
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)
    LAST_LOG=$(tail -1 "$LOG_FILE" 2>/dev/null)
    echo -e "${GREEN}✓ Log File: EXISTS${NC}"
    echo "  Size: $LOG_SIZE"
    echo "  Last Entry: ${LAST_LOG:0:80}..."
else
    echo -e "${YELLOW}⚠ Log File: NOT FOUND${NC}"
fi
echo ""

# Show monitored addresses from config
echo "Monitored Addresses (from config.yaml):"
grep -A 10 "monitored_addresses:" config.yaml | grep "0x" | sed 's/^[ -]*/  /'
echo ""

echo "========================================="
