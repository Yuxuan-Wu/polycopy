#!/bin/bash
#
# Polymarket Copy Trading System - Startup Script
#
# Features:
# - Starts Clash proxy (if needed for copy trading)
# - Tests proxy connectivity
# - Starts the monitoring system
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║     POLYMARKET COPY TRADING SYSTEM                       ║"
echo "║     Startup Script                                       ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check if copy trading is enabled
COPY_TRADING_ENABLED=$(python3 -c "
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
print('true' if config.get('copy_trading', {}).get('enabled', False) else 'false')
")

if [ "$COPY_TRADING_ENABLED" = "true" ]; then
    echo -e "${YELLOW}Copy trading is ENABLED - checking Clash proxy...${NC}"
    echo ""

    # Check if Clash is running
    if ! pgrep -f "clash" > /dev/null; then
        echo "Starting Clash..."
        nohup clash -d /root/.config/clash > /tmp/clash.log 2>&1 &
        sleep 3
    fi

    # Verify Clash ports
    if ss -tlnp | grep -q "7890"; then
        echo -e "${GREEN}✓ Clash is running (port 7890)${NC}"
    else
        echo -e "${RED}✗ Clash failed to start${NC}"
        echo "Check /tmp/clash.log for errors"
        exit 1
    fi

    # Test proxy connectivity
    echo ""
    echo "Testing proxy connectivity to Polymarket..."

    PROXY_TEST=$(python3 -c "
import sys
sys.path.insert(0, 'src')
from clash_proxy_manager import get_proxy_manager
pm = get_proxy_manager()
success, error = pm.test_connectivity()
if success:
    print('OK')
else:
    # Try rotation
    rotated, region = pm.rotate_region()
    if rotated:
        print(f'OK (via {region})')
    else:
        print(f'FAIL: {error}')
")

    if [[ "$PROXY_TEST" == OK* ]]; then
        echo -e "${GREEN}✓ Proxy connectivity: $PROXY_TEST${NC}"
    else
        echo -e "${RED}✗ Proxy connectivity failed: $PROXY_TEST${NC}"
        echo "Copy trading will be disabled"
    fi
    echo ""
else
    echo "Copy trading is DISABLED - skipping proxy setup"
    echo ""
fi

# Kill any existing main.py processes
if pgrep -f "python3 main.py" > /dev/null; then
    echo "Stopping existing main.py processes..."
    pkill -f "python3 main.py" || true
    sleep 2
fi

# Start the monitoring system
echo "Starting Polymarket Monitor..."
echo ""

# Run in foreground
python3 main.py
