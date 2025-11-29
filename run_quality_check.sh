#!/bin/bash
# Data Quality Check Script for Polycopy Monitor
# Comprehensive checks on database integrity and data quality

set -e

DB_FILE="data/trades.db"
REPORT_DIR="reports"
ALERT_LOG="logs/quality_alerts.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORT_DIR/quality_report_$TIMESTAMP.txt"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================="
echo "  Polycopy Data Quality Check"
echo "  $(date)"
echo "========================================="
echo ""

# Create reports directory if not exists
mkdir -p "$REPORT_DIR"

# Check if database exists
if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}✗ Database not found: $DB_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Database found${NC}"
echo ""

# Initialize report
cat > "$REPORT_FILE" <<EOF
========================================
Polycopy Data Quality Report
Generated: $(date)
========================================

EOF

# Function to run query and add to report
run_check() {
    local check_name="$1"
    local query="$2"
    local threshold="$3"
    local operator="$4"  # gt, lt, eq

    echo "Checking: $check_name..."
    result=$(sqlite3 "$DB_FILE" "$query")

    echo "$check_name: $result" >> "$REPORT_FILE"

    # Evaluate threshold if provided
    if [ -n "$threshold" ]; then
        case "$operator" in
            "gt")
                if [ "$result" -gt "$threshold" ]; then
                    echo -e "${RED}✗ ALERT: $check_name = $result (expected <= $threshold)${NC}"
                    echo "[$(date)] ALERT: $check_name = $result (threshold: $threshold)" >> "$ALERT_LOG"
                    return 1
                fi
                ;;
            "lt")
                if [ "$result" -lt "$threshold" ]; then
                    echo -e "${RED}✗ ALERT: $check_name = $result (expected >= $threshold)${NC}"
                    echo "[$(date)] ALERT: $check_name = $result (threshold: $threshold)" >> "$ALERT_LOG"
                    return 1
                fi
                ;;
            "eq")
                if [ "$result" -ne "$threshold" ]; then
                    echo -e "${YELLOW}⚠ WARNING: $check_name = $result (expected: $threshold)${NC}"
                    return 1
                fi
                ;;
        esac
        echo -e "${GREEN}✓ $check_name: $result${NC}"
    else
        echo -e "${BLUE}ℹ $check_name: $result${NC}"
    fi

    return 0
}

echo "=== Basic Statistics ===" | tee -a "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

run_check "Total Trades" "SELECT COUNT(*) FROM trades"
run_check "Unique Addresses" "SELECT COUNT(DISTINCT from_address) FROM trades"
run_check "Block Range" "SELECT MAX(block_number) - MIN(block_number) FROM trades"
run_check "Time Range (hours)" "SELECT CAST((MAX(timestamp) - MIN(timestamp)) / 3600.0 AS INTEGER) FROM trades"

echo "" | tee -a "$REPORT_FILE"
echo "=== Data Quality Checks ===" | tee -a "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Critical checks with thresholds
run_check "Invalid Prices (<0 or >1)" "SELECT COUNT(*) FROM trades WHERE CAST(price AS REAL) < 0 OR CAST(price AS REAL) > 1" 0 "eq"
run_check "Invalid Amounts (<=0)" "SELECT COUNT(*) FROM trades WHERE CAST(amount AS REAL) <= 0" 0 "eq"
run_check "Failed Transactions" "SELECT COUNT(*) FROM trades WHERE status != 'success'" 0 "eq"
run_check "Missing Token IDs" "SELECT COUNT(*) FROM trades WHERE token_id IS NULL OR token_id = ''" 0 "eq"
run_check "Missing Side Info" "SELECT COUNT(*) FROM trades WHERE side IS NULL OR side = ''" 0 "eq"

echo "" | tee -a "$REPORT_FILE"
echo "=== Performance Metrics ===" | tee -a "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

run_check "Real-time Trades (<60s)" "SELECT COUNT(*) FROM trades WHERE capture_delay_seconds < 60"
run_check "Slow Trades (60-300s)" "SELECT COUNT(*) FROM trades WHERE capture_delay_seconds BETWEEN 60 AND 300"
run_check "Delayed Trades (>300s)" "SELECT COUNT(*) FROM trades WHERE capture_delay_seconds > 300"
run_check "Avg Capture Delay (s)" "SELECT CAST(AVG(capture_delay_seconds) AS INTEGER) FROM trades"

echo "" | tee -a "$REPORT_FILE"
echo "=== Trade Distribution ===" | tee -a "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Trade distribution by side
sqlite3 "$DB_FILE" "SELECT side, COUNT(*) as count FROM trades GROUP BY side ORDER BY count DESC;" | while IFS='|' read -r side count; do
    echo "  $side: $count trades" | tee -a "$REPORT_FILE"
done

echo "" | tee -a "$REPORT_FILE"
echo "=== Recent Activity ===" | tee -a "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

run_check "Trades in last hour" "SELECT COUNT(*) FROM trades WHERE timestamp > strftime('%s', 'now', '-1 hour')"
run_check "Trades in last 24h" "SELECT COUNT(*) FROM trades WHERE timestamp > strftime('%s', 'now', '-24 hours')"

echo "" | tee -a "$REPORT_FILE"
echo "=== Latest 5 Trades ===" | tee -a "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

sqlite3 "$DB_FILE" "
SELECT
    datetime(timestamp, 'unixepoch') as time,
    substr(tx_hash, 1, 10) || '...' as tx,
    side,
    printf('%.3f', CAST(price AS REAL)) as price,
    capture_delay_seconds || 's' as delay
FROM trades
ORDER BY timestamp DESC
LIMIT 5;
" >> "$REPORT_FILE"

# Display latest trades
echo "Latest 5 trades:"
sqlite3 "$DB_FILE" "
SELECT
    datetime(timestamp, 'unixepoch') as time,
    substr(tx_hash, 1, 10) || '...' as tx,
    side,
    printf('%.3f', CAST(price AS REAL)) as price,
    capture_delay_seconds || 's' as delay
FROM trades
ORDER BY timestamp DESC
LIMIT 5;
" | column -t -s '|'

echo ""
echo "========================================="
echo -e "${GREEN}Quality check completed!${NC}"
echo "Report saved to: $REPORT_FILE"
echo "========================================="
