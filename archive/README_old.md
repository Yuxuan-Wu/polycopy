# Polymarket Copy Trading System

A backend monitoring system that tracks Polymarket trades from specified wallet addresses on the Polygon blockchain.

## Features

- **Multi-Address Monitoring**: Monitor up to 3 wallet addresses simultaneously
- **RPC Redundancy**: Multiple Polygon RPC endpoints with automatic failover
- **Data Persistence**: SQLite database for reliable trade storage
- **CSV Export**: Automatic real-time export to CSV files
- **Error Recovery**: Automatic retry and RPC node rotation on failures
- **Resume Support**: Automatically resumes from last processed block

## System Requirements

**Tested Hardware:**
- RAM: 1.9 GB (859 MB available)
- CPU: 2 cores
- Disk: 21 GB available

**Software:**
- Python 3.10+
- SQLite3

## Project Structure

```
polycopy/
├── config.yaml              # Configuration file
├── main.py                  # Main entry point
├── requirements.txt         # Python dependencies
├── src/
│   ├── __init__.py
│   ├── rpc_manager.py      # RPC node management with failover
│   ├── database.py         # SQLite + CSV export
│   └── monitor.py          # Transaction monitoring logic
├── data/
│   ├── trades.db           # SQLite database (auto-created)
│   └── trades.csv          # CSV export (auto-created)
├── logs/
│   └── polycopy.log        # Application logs (auto-created)
└── README.md
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Monitored Addresses

Edit `config.yaml` and replace the placeholder addresses with actual Polygon addresses you want to monitor:

```yaml
monitored_addresses:
  - "0xYourAddress1Here"
  - "0xYourAddress2Here"
  - "0xYourAddress3Here"
```

### 3. (Optional) Adjust Settings

You can customize:
- **RPC endpoints**: Add/remove Polygon RPC nodes
- **Poll interval**: Adjust block checking frequency
- **Start block**: Set specific block number or use 'latest'
- **Logging level**: DEBUG, INFO, WARNING, ERROR

## Usage

### Start Monitoring

```bash
python3 main.py
```

The system will:
1. Connect to Polygon RPC nodes
2. Initialize database and CSV file
3. Start monitoring from latest block (or resume from last processed)
4. Display real-time trade detections

### Stop Monitoring

Press `Ctrl+C` to gracefully stop the monitor.

### View Trades

**CSV File:**
```bash
cat data/trades.csv
```

**SQLite Database:**
```bash
sqlite3 data/trades.db "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;"
```

## Configuration Reference

### Monitored Addresses
List of Polygon wallet addresses to monitor (up to 3):
```yaml
monitored_addresses:
  - "0x..."
```

### RPC Endpoints
Multiple Polygon RPC nodes for redundancy:
```yaml
rpc_endpoints:
  - "https://polygon-rpc.com"
  - "https://rpc-mainnet.matic.network"
  # Add more for better redundancy
```

### Monitoring Settings
```yaml
monitoring:
  poll_interval: 12        # Check for new blocks every N seconds
  start_block: "latest"    # Or specific block number
  max_retry: 3            # Retry attempts per RPC call
  retry_delay: 5          # Seconds between retries
```

### Database & CSV
```yaml
database:
  path: "data/trades.db"

csv:
  path: "data/trades.csv"
  auto_export: true       # Export to CSV on every trade
```

### Logging
```yaml
logging:
  level: "INFO"           # DEBUG, INFO, WARNING, ERROR
  file: "logs/polycopy.log"
```

## Trade Data Schema

### Database Table: `trades`

| Column        | Type    | Description                          |
|---------------|---------|--------------------------------------|
| id            | INTEGER | Auto-increment primary key           |
| tx_hash       | TEXT    | Transaction hash (unique)            |
| block_number  | INTEGER | Block number                         |
| timestamp     | INTEGER | Unix timestamp                       |
| from_address  | TEXT    | Sender address (monitored address)   |
| to_address    | TEXT    | Recipient (Polymarket contract)      |
| method        | TEXT    | Contract method (fillOrder, etc.)    |
| token_id      | TEXT    | Token/market ID                      |
| amount        | TEXT    | Trade amount                         |
| price         | TEXT    | Trade price                          |
| side          | TEXT    | Buy/sell (if determinable)           |
| gas_used      | TEXT    | Gas consumed                         |
| gas_price     | TEXT    | Gas price                            |
| value         | TEXT    | ETH value sent                       |
| status        | TEXT    | success/failed                       |
| created_at    | TEXT    | Record creation time                 |

### CSV Export

Same fields as database, with additional `datetime` column (human-readable timestamp).

## How It Works

### 1. RPC Manager (`rpc_manager.py`)
- Manages multiple Polygon RPC endpoints
- Automatic failover on connection errors
- Retries with exponential backoff
- Health checking and rotation

### 2. Database Manager (`database.py`)
- SQLite for persistent storage
- Automatic CSV export on new trades
- Deduplication (tx_hash unique constraint)
- Indexed queries for performance

### 3. Monitor (`monitor.py`)
- Polls Polygon blockchain for new blocks
- Filters transactions involving monitored addresses
- Identifies Polymarket contract interactions
- Parses transaction data (method, amounts, etc.)
- Records trades to database

### 4. Main Loop (`main.py`)
- Orchestrates all components
- Configuration loading and validation
- Graceful shutdown handling
- Error recovery

## Polymarket Contract

The system monitors interactions with the Polymarket CTF Exchange contract:
- **Address**: `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`
- **Network**: Polygon (Chain ID: 137)

Supported methods:
- `fillOrder`: Execute a single order
- `fillOrders`: Execute multiple orders
- `matchOrders`: Match maker/taker orders
- `cancelOrder`: Cancel an order
- `cancelOrders`: Cancel multiple orders

## Troubleshooting

### RPC Connection Issues

If all RPC nodes fail:
1. Check internet connectivity
2. Verify RPC endpoints are online
3. Add more RPC endpoints to `config.yaml`
4. Increase `retry_delay` in config

### No Trades Detected

Possible reasons:
- Monitored addresses haven't made Polymarket trades yet
- Start block is set too recent (missed historical trades)
- RPC node is behind (try different node)

### Database Locked

If SQLite shows "database is locked":
- Ensure only one instance is running
- Check file permissions on `data/` directory

### High Memory Usage

- Reduce `poll_interval` to check blocks less frequently
- Process fewer blocks per iteration (modify `_monitor_loop`)

## Future Enhancements

Phase 2 features (not yet implemented):
- Real wallet integration for copy trading execution
- Web API for remote monitoring
- Dashboard UI for visualization
- Advanced trade parsing with full ABI decoding
- Webhook notifications
- Multi-chain support

## License

MIT License

## Disclaimer

This software is for educational and monitoring purposes only. Use at your own risk. Always verify trades independently before executing any financial transactions.

## Support

For issues or questions, please check:
1. Application logs: `logs/polycopy.log`
2. Configuration: `config.yaml`
3. Database queries: `sqlite3 data/trades.db`
