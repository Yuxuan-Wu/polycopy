#!/bin/bash
# Unified Analysis Tool - Easy access to all analysis functions

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

show_help() {
    cat << EOF
${GREEN}Polycopy Analysis Tool${NC}

USAGE:
    ./analyze.sh [COMMAND] [OPTIONS]

COMMANDS:
    ${BLUE}trader${NC} <address>              - Comprehensive trader behavior analysis
    ${BLUE}market${NC} <address> <token_id>   - Deep dive into specific market
    ${BLUE}clusters${NC} <address>            - Find correlated trade patterns
    ${BLUE}compare${NC} <addr1> <addr2>       - Compare two traders
    ${BLUE}summary${NC}                       - Quick summary of all monitored addresses
    ${BLUE}export${NC} <address>              - Export trader data to JSON

EXAMPLES:
    # Analyze a trader's behavior
    ./analyze.sh trader 0xCA8F0374E3Fc79b485499CC0b038D4F7e783D963

    # Analyze specific market
    ./analyze.sh market 0xCA8F... 0x1919337589...

    # Find trade clusters
    ./analyze.sh clusters 0xCA8F0374E3Fc79b485499CC0b038D4F7e783D963

    # Quick summary
    ./analyze.sh summary

EOF
}

# Command handlers
cmd_trader() {
    if [ -z "$1" ]; then
        echo -e "${RED}Error: Address required${NC}"
        echo "Usage: ./analyze.sh trader <address>"
        exit 1
    fi

    python3 trader_analysis.py "$1"
}

cmd_market() {
    if [ -z "$1" ] || [ -z "$2" ]; then
        echo -e "${RED}Error: Address and token_id required${NC}"
        echo "Usage: ./analyze.sh market <address> <token_id>"
        exit 1
    fi

    python3 market_analysis.py "$1" --market "$2"
}

cmd_clusters() {
    if [ -z "$1" ]; then
        echo -e "${RED}Error: Address required${NC}"
        echo "Usage: ./analyze.sh clusters <address>"
        exit 1
    fi

    python3 market_analysis.py "$1" --clusters
}

cmd_compare() {
    if [ -z "$1" ] || [ -z "$2" ]; then
        echo -e "${RED}Error: Two addresses required${NC}"
        echo "Usage: ./analyze.sh compare <addr1> <addr2>"
        exit 1
    fi

    echo -e "${BLUE}Analyzing Address 1: ${addr1:0:10}...${NC}"
    python3 trader_analysis.py "$1" > /tmp/trader1.txt

    echo -e "\n${BLUE}Analyzing Address 2: ${addr2:0:10}...${NC}"
    python3 trader_analysis.py "$2" > /tmp/trader2.txt

    echo -e "\n${GREEN}=== COMPARISON ===${NC}\n"

    # Extract key metrics
    freq1=$(grep "classification" /tmp/trader1.txt | head -1 | awk '{print $NF}')
    freq2=$(grep "classification" /tmp/trader2.txt | head -1 | awk '{print $NF}')

    echo -e "Trading Frequency:"
    echo -e "  Address 1: $freq1"
    echo -e "  Address 2: $freq2"

    echo -e "\nFull reports saved to:"
    echo -e "  /tmp/trader1.txt"
    echo -e "  /tmp/trader2.txt"
}

cmd_summary() {
    echo -e "${GREEN}=== MONITORED ADDRESSES SUMMARY ===${NC}\n"

    sqlite3 data/trades.db << EOF
.mode column
.headers on
SELECT
    from_address,
    COUNT(*) as trades,
    SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buys,
    SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sells,
    COUNT(DISTINCT token_id) as markets,
    ROUND(SUM(CAST(amount AS REAL)), 1) as volume,
    MIN(datetime(timestamp, 'unixepoch')) as first_trade,
    MAX(datetime(timestamp, 'unixepoch')) as last_trade
FROM trades
GROUP BY from_address;
EOF

    echo ""
    echo -e "${BLUE}For detailed analysis, use:${NC}"
    echo "  ./analyze.sh trader <address>"
}

cmd_export() {
    if [ -z "$1" ]; then
        echo -e "${RED}Error: Address required${NC}"
        echo "Usage: ./analyze.sh export <address>"
        exit 1
    fi

    OUTPUT_FILE="reports/trader_$(date +%Y%m%d_%H%M%S).json"
    mkdir -p reports

    echo -e "${BLUE}Exporting data for ${1:0:10}...${NC}"

    sqlite3 data/trades.db << EOF > "$OUTPUT_FILE"
.mode json
SELECT * FROM trades WHERE from_address = '$1' ORDER BY timestamp;
EOF

    echo -e "${GREEN}✓ Exported to: $OUTPUT_FILE${NC}"
    echo "$(wc -l < "$OUTPUT_FILE") records exported"
}

# Main
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

COMMAND=$1
shift

case "$COMMAND" in
    trader)
        cmd_trader "$@"
        ;;
    market)
        cmd_market "$@"
        ;;
    clusters)
        cmd_clusters "$@"
        ;;
    compare)
        cmd_compare "$@"
        ;;
    summary)
        cmd_summary "$@"
        ;;
    export)
        cmd_export "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
