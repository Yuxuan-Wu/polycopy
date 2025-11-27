#!/bin/bash
# Polymarket Monitor - Live Dashboard (Optimized Version)
# Usage: ./watch.sh [refresh_interval_seconds]

REFRESH_INTERVAL=${1:-5}  # Default 5 seconds
LOG_FILE="logs/polycopy.log"
DB_FILE="data/trades.db"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to convert seconds to human-readable format
format_time() {
    local seconds=$1
    if [ -z "$seconds" ]; then
        echo "N/A"
        return
    fi

    # Remove 's' suffix if present
    seconds=${seconds%s}

    local hours=$((seconds / 3600))
    local minutes=$(( (seconds % 3600) / 60 ))
    local secs=$((seconds % 60))

    if [ $hours -gt 0 ]; then
        echo "${hours}h ${minutes}m ${secs}s"
    elif [ $minutes -gt 0 ]; then
        echo "${minutes}m ${secs}s"
    else
        echo "${secs}s"
    fi
}

clear

while true; do
    # Move cursor to top
    tput cup 0 0

    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}            ${GREEN}POLYMARKET MONITOR - LIVE DASHBOARD${NC}                       ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Current time
    echo -e "${BLUE}⏰ Current Time:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Process Status
    PROCESS_PID=$(pgrep -f "python3.*main.py" | head -1)
    if [ -n "$PROCESS_PID" ]; then
        UPTIME=$(ps -p $PROCESS_PID -o etime= | xargs)
        MEM=$(ps -p $PROCESS_PID -o rss= | awk '{printf "%.1f MB", $1/1024}')
        CPU=$(ps -p $PROCESS_PID -o %cpu= | xargs)
        echo -e "${GREEN}✓ Process Status:${NC} RUNNING (PID: $PROCESS_PID)"
        echo -e "  Uptime: $UPTIME | Memory: $MEM | CPU: ${CPU}%"
    else
        echo -e "${RED}✗ Process Status:${NC} NOT RUNNING"
    fi
    echo ""

    # RPC Status (from logs) - check both recent and startup logs
    RPC_LINE=$(grep "Connected to RPC" "$LOG_FILE" 2>/dev/null | tail -1)
    if [ -n "$RPC_LINE" ]; then
        if [[ "$RPC_LINE" == *"infura"* ]] || [[ "$RPC_LINE" == *"***"* ]]; then
            echo -e "${GREEN}🌐 RPC Endpoint:${NC} Infura (Primary)"
        else
            RPC_ENDPOINT=$(echo "$RPC_LINE" | grep -o "https://[^ ]*" | sed 's/https:\/\///' | cut -d'/' -f1)
            echo -e "${YELLOW}🌐 RPC Endpoint:${NC} $RPC_ENDPOINT (Fallback)"
        fi
    else
        echo -e "${RED}🌐 RPC Endpoint:${NC} Unknown (check logs)"
    fi
    echo ""

    # Database Stats
    if [ -f "$DB_FILE" ]; then
        TOTAL_TRADES=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM trades;" 2>/dev/null)
        DB_SIZE=$(du -h "$DB_FILE" | cut -f1)

        echo -e "${GREEN}📊 Database Stats:${NC}"
        echo -e "  Total Trades: $TOTAL_TRADES | Size: $DB_SIZE"

        # Trades per address
        echo -e "\n${BLUE}👤 Trades per Address:${NC}"
        sqlite3 "$DB_FILE" "SELECT from_address, COUNT(*) as cnt FROM trades GROUP BY from_address ORDER BY cnt DESC;" 2>/dev/null | while IFS='|' read -r addr count; do
            short_addr="${addr:0:10}...${addr: -4}"
            echo -e "  $short_addr: $count trades"
        done
    else
        echo -e "${RED}📊 Database:${NC} Not found"
    fi
    echo ""

    # Recent Activity
    echo -e "${BLUE}📈 Recent Activity:${NC}"
    if [ -f "$LOG_FILE" ]; then
        # Last trade detected with delay
        LAST_TRADE_LINE=$(tail -200 "$LOG_FILE" 2>/dev/null | grep -B 6 "Capture delay" | tail -7)
        if [ -n "$LAST_TRADE_LINE" ]; then
            TRADE_BLOCK=$(echo "$LAST_TRADE_LINE" | grep "TRADE DETECTED" | grep -o "Block: [0-9,]*" | cut -d' ' -f2)
            TRADE_TIME=$(echo "$LAST_TRADE_LINE" | grep "Time:" | grep -o "Time: [0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} [0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}" | cut -d' ' -f2-)
            DELAY_RAW=$(echo "$LAST_TRADE_LINE" | grep "Capture delay" | grep -o "[0-9]*s")
            DELAY_FORMATTED=$(format_time "$DELAY_RAW")

            if [ -n "$TRADE_BLOCK" ] && [ -n "$TRADE_TIME" ]; then
                echo -e "  Last Trade: Block $TRADE_BLOCK (${TRADE_TIME})"
                echo -e "  Capture Delay: $DELAY_FORMATTED"
            else
                echo -e "  ${YELLOW}No complete trade info available${NC}"
            fi
        else
            echo -e "  ${YELLOW}No trades detected yet${NC}"
        fi

        # Processing progress
        PROCESSING=$(tail -50 "$LOG_FILE" 2>/dev/null | grep "Processing blocks" | tail -1)
        if [ -n "$PROCESSING" ]; then
            BLOCKS=$(echo "$PROCESSING" | grep -o "Processing blocks [0-9,]* to [0-9,]*" | sed 's/Processing blocks //')
            BEHIND=$(echo "$PROCESSING" | grep -o "[0-9,]* behind" | cut -d' ' -f1)
            echo -e "  Current Range: $BLOCKS"
            if [ -n "$BEHIND" ]; then
                echo -e "  Backlog: $BEHIND blocks"
            fi
        fi

        # Trades found in recent batches
        RECENT_FOUND=$(tail -50 "$LOG_FILE" 2>/dev/null | grep "Found.*trades in this batch" | tail -3)
        if [ -n "$RECENT_FOUND" ]; then
            echo -e "\n  ${BLUE}Recent Batches:${NC}"
            echo "$RECENT_FOUND" | while read -r line; do
                FOUND=$(echo "$line" | grep -o "[0-9]* trades")
                TIME=$(echo "$line" | grep -o "^[^ ]* [^ ]*")
                echo -e "    [$TIME] $FOUND"
            done
        fi
    fi
    echo ""

    # Log Activity
    echo -e "${BLUE}📝 Recent Logs (last 5 lines):${NC}"
    if [ -f "$LOG_FILE" ]; then
        tail -5 "$LOG_FILE" 2>/dev/null | while read -r line; do
            # Truncate long lines to prevent cutoff
            if [ ${#line} -gt 120 ]; then
                line="${line:0:117}..."
            fi

            # Highlight errors and warnings
            if [[ "$line" == *"ERROR"* ]]; then
                echo -e "  ${RED}$line${NC}"
            elif [[ "$line" == *"WARNING"* ]]; then
                echo -e "  ${YELLOW}$line${NC}"
            elif [[ "$line" == *"TRADE DETECTED"* ]]; then
                echo -e "  ${GREEN}$line${NC}"
            else
                echo -e "  $line"
            fi
        done
    else
        echo -e "  ${RED}Log file not found${NC}"
    fi
    echo ""

    # Footer
    echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
    echo -e "Refresh: ${REFRESH_INTERVAL}s | Ctrl+C to exit | $(date '+%H:%M:%S')"

    sleep $REFRESH_INTERVAL
done
