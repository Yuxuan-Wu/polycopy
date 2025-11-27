# Quick Start Guide

Get your Polymarket copy trading monitor running in 3 steps.

## Step 1: Configure Monitored Addresses

Edit `config.yaml` and replace the placeholder addresses:

```yaml
monitored_addresses:
  - "0xYourPolygonAddress1"
  - "0xYourPolygonAddress2"  # Optional
  - "0xYourPolygonAddress3"  # Optional
```

**Where to find addresses:**
- Polymarket leaderboard: https://polymarket.com/leaderboard
- Copy any Polygon wallet address you want to track

## Step 2: Start the Monitor

```bash
python3 main.py
```

You should see:
```
╔═══════════════════════════════════════════════════════════╗
║     POLYMARKET COPY TRADING SYSTEM                        ║
╚═══════════════════════════════════════════════════════════╝

✓ Connected to RPC: https://polygon-rpc.com (Chain ID: 137)
✓ Database initialized: data/trades.db
✓ CSV file initialized: data/trades.csv
🔍 POLYMARKET MONITOR STARTED
```

## Step 3: Monitor Trades

The system will:
- Check for new blocks every 12 seconds
- Detect Polymarket trades from your monitored addresses
- Save trades to `data/trades.csv` automatically
- Log all activity to `logs/polycopy.log`

### View Trades

**Check CSV file:**
```bash
cat data/trades.csv
```

**Check logs:**
```bash
tail -f logs/polycopy.log
```

**Query database:**
```bash
sqlite3 data/trades.db "SELECT tx_hash, datetime(timestamp, 'unixepoch'), method, status FROM trades;"
```

## Stop the Monitor

Press `Ctrl+C` to stop gracefully.

## Troubleshooting

### No trades detected?

This is normal if:
- The monitored addresses haven't traded recently
- You started from the latest block (historical trades won't be captured)

**To capture historical trades:**
Edit `config.yaml`:
```yaml
monitoring:
  start_block: 79000000  # Set to a block number from ~1 week ago
```

### RPC connection errors?

The system tries multiple RPC endpoints automatically. If all fail:
1. Check internet connection
2. Wait a few minutes and retry
3. Check RPC status at: https://chainlist.org/chain/137

## Example Output

When a trade is detected, you'll see:
```
📊 TRADE DETECTED | Block: 79519835 | From: 0x1234abcd... | Method: fillOrder | Status: success
✓ Trade recorded: 0xabcd1234...
```

## Configuration Tips

### Faster Monitoring
```yaml
monitoring:
  poll_interval: 6  # Check every 6 seconds instead of 12
```

### Debug Mode
```yaml
logging:
  level: "DEBUG"  # More detailed logs
```

### Multiple Addresses
You can monitor 1-3 addresses. More addresses = more chances to detect trades.

## Next Steps

- Set up automatic startup (systemd service)
- Analyze trades in CSV with Excel/Python
- Build your copy trading strategy based on the data

## Support

Check `README.md` for full documentation.
