#!/bin/bash
# Polycopy Monitor - Restart Script
# This script will:
# 1. Stop the running monitor process
# 2. Clean all database and CSV files
# 3. Restart the monitor

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================="
echo "  Polycopy Monitor - Restart"
echo "========================================="
echo ""

# Step 1: Stop the running process
echo -e "${BLUE}[1/3] Stopping running process...${NC}"
PROCESS_PID=$(pgrep -f "python3.*main.py" | head -1)
if [ -n "$PROCESS_PID" ]; then
    kill $PROCESS_PID
    sleep 2
    # Force kill if still running
    if ps -p $PROCESS_PID > /dev/null 2>&1; then
        kill -9 $PROCESS_PID
        sleep 1
    fi
    echo -e "${GREEN}✓ Process stopped (PID: $PROCESS_PID)${NC}"
else
    echo -e "${YELLOW}⚠ No running process found${NC}"
fi
echo ""

# Step 2: Clean all data files
echo -e "${BLUE}[2/3] Cleaning all data files...${NC}"
# Remove database files
rm -f data/*.db data/*.db-journal data/*.db-shm data/*.db-wal
# Remove CSV files
rm -f data/*.csv
# Remove backup files
rm -f data/*.backup data/*.old
echo -e "${GREEN}✓ All data files cleaned${NC}"
echo ""

# Step 3: Restart the monitor
echo -e "${BLUE}[3/3] Starting monitor...${NC}"
# Ensure directories exist
mkdir -p logs data

# Start the monitor in background
nohup python3 main.py > /dev/null 2>&1 &
NEW_PID=$!
sleep 3

# Verify it's running
if ps -p $NEW_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Monitor started successfully (PID: $NEW_PID)${NC}"
else
    echo -e "${RED}✗ Failed to start monitor${NC}"
    echo "Check logs/polycopy.log for details"
    exit 1
fi
echo ""

echo "========================================="
echo -e "${GREEN}Restart completed successfully!${NC}"
echo ""
echo "Use these commands to monitor:"
echo "  ./status.sh  - Quick status check"
echo "  ./watch.sh   - Live dashboard"
echo "========================================="
