#!/bin/bash
# Polymarket Copy Trading System - Status Monitor
# 监控脚本 - 检查系统运行状态

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Status indicators
CHECK_OK="${GREEN}✓${NC}"
CHECK_FAIL="${RED}✗${NC}"
CHECK_WARN="${YELLOW}⚠${NC}"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║     POLYMARKET COPY TRADING SYSTEM                        ║"
echo "║     Status Monitor / 状态监控                               ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo -e "${CHECK_FAIL} Error: Not in polycopy directory"
    exit 1
fi

# 1. Check if process is running
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Process Status / 进程状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PID=$(pgrep -f "python3 main.py" | tail -1)
if [ -n "$PID" ]; then
    echo -e "${CHECK_OK} Monitor is RUNNING"
    echo -e "   Process ID: ${BLUE}$PID${NC}"

    # Get process uptime
    UPTIME=$(ps -p $PID -o etime= | xargs)
    echo -e "   Uptime: ${BLUE}$UPTIME${NC}"

    # Get memory usage
    MEM=$(ps -p $PID -o rss= | awk '{printf "%.1f MB", $1/1024}')
    echo -e "   Memory: ${BLUE}$MEM${NC}"

    PROCESS_RUNNING=true
else
    echo -e "${CHECK_FAIL} Monitor is STOPPED"
    echo -e "   ${YELLOW}Run: python3 main.py${NC}"
    PROCESS_RUNNING=false
fi

# 2. Check log file
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Log File Status / 日志状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "logs/polycopy.log" ]; then
    echo -e "${CHECK_OK} Log file exists"

    # Get file size
    LOG_SIZE=$(du -h logs/polycopy.log | cut -f1)
    echo -e "   Size: ${BLUE}$LOG_SIZE${NC}"

    # Get last modification time
    if [[ "$OSTYPE" == "darwin"* ]]; then
        LAST_MOD=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" logs/polycopy.log)
    else
        LAST_MOD=$(stat -c "%y" logs/polycopy.log | cut -d'.' -f1)
    fi
    echo -e "   Last updated: ${BLUE}$LAST_MOD${NC}"

    # Check if log was updated recently (within 1 minute)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        LAST_MOD_SEC=$(stat -f "%m" logs/polycopy.log)
    else
        LAST_MOD_SEC=$(stat -c "%Y" logs/polycopy.log)
    fi
    CURRENT_SEC=$(date +%s)
    AGE=$((CURRENT_SEC - LAST_MOD_SEC))

    if [ $AGE -lt 60 ] && [ "$PROCESS_RUNNING" = true ]; then
        echo -e "   ${CHECK_OK} Log is being actively updated (${AGE}s ago)"
    elif [ "$PROCESS_RUNNING" = true ]; then
        echo -e "   ${CHECK_WARN} Log last updated ${AGE}s ago"
    fi
else
    echo -e "${CHECK_FAIL} Log file not found"
fi

# 3. Check database
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Database Status / 数据库状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "data/trades.db" ]; then
    echo -e "${CHECK_OK} Database exists"

    # Get database size
    DB_SIZE=$(du -h data/trades.db | cut -f1)
    echo -e "   Size: ${BLUE}$DB_SIZE${NC}"

    # Get trade count
    TRADE_COUNT=$(sqlite3 data/trades.db "SELECT COUNT(*) FROM trades;" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo -e "   Total trades: ${BLUE}$TRADE_COUNT${NC}"

        if [ "$TRADE_COUNT" -gt 0 ]; then
            # Get latest trade
            LATEST=$(sqlite3 data/trades.db "SELECT datetime(timestamp, 'unixepoch'), from_address FROM trades ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null)
            echo -e "   Latest trade: ${BLUE}$LATEST${NC}"
        fi
    fi
else
    echo -e "${CHECK_FAIL} Database not found"
fi

# 4. Check CSV file
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. CSV Export Status / CSV导出状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "data/trades.csv" ]; then
    echo -e "${CHECK_OK} CSV file exists"

    # Get CSV size
    CSV_SIZE=$(du -h data/trades.csv | cut -f1)
    echo -e "   Size: ${BLUE}$CSV_SIZE${NC}"

    # Count lines (subtract 1 for header)
    LINE_COUNT=$(wc -l < data/trades.csv)
    TRADE_LINES=$((LINE_COUNT - 1))
    echo -e "   Trade records: ${BLUE}$TRADE_LINES${NC}"
else
    echo -e "${CHECK_FAIL} CSV file not found"
fi

# 5. Check configuration
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Configuration / 配置状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "config.yaml" ]; then
    echo -e "${CHECK_OK} Configuration file exists"

    # Extract monitored addresses
    echo ""
    echo "   Monitored addresses:"
    grep -A 3 "monitored_addresses:" config.yaml | grep "0x" | while read line; do
        ADDR=$(echo $line | grep -o "0x[a-fA-F0-9]*" | head -1)
        if [ -n "$ADDR" ] && [ "$ADDR" != "0x0000000000000000000000000000000000000000" ]; then
            echo -e "   ${CHECK_OK} ${BLUE}${ADDR}${NC}"
        fi
    done
else
    echo -e "${CHECK_FAIL} Configuration file not found"
fi

# 6. Recent activity
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. Recent Activity / 最近活动"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "logs/polycopy.log" ]; then
    echo ""
    echo "Last 5 log entries:"
    echo "-----------------------------------------------------------"
    tail -5 logs/polycopy.log
    echo "-----------------------------------------------------------"
fi

# 7. Overall status
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Overall Status / 总体状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$PROCESS_RUNNING" = true ]; then
    echo -e "${CHECK_OK} ${GREEN}System is operational and monitoring trades${NC}"
    echo ""
    echo "Commands:"
    echo "  • View live logs:  tail -f logs/polycopy.log"
    echo "  • Stop monitor:    pkill -f 'python3 main.py'"
    echo "  • View trades:     cat data/trades.csv"
    EXIT_CODE=0
else
    echo -e "${CHECK_FAIL} ${RED}System is not running${NC}"
    echo ""
    echo "Start the monitor with: python3 main.py"
    EXIT_CODE=1
fi

echo ""
exit $EXIT_CODE
