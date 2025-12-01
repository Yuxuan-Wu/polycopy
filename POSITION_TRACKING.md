# Position Tracking Guide

## Overview

The Polycopy system now tracks positions (holdings) for monitored addresses in real-time. This allows you to see:

- Current holdings for each token/market
- Average buy price and total P&L
- Settlement detection (winning/losing positions)
- Position history and status

## How It Works

### Automatic Tracking

When the monitor detects a trade:

1. **Buy Transaction**: Increases position, updates average buy price
2. **Sell Transaction**: Decreases position, calculates realized P&L
3. **Settlement Detection**: Automatically detects market settlements:
   - Price ≥ $0.95 = Winning settlement (market resolved in your favor)
   - Price ≤ $0.05 = Losing settlement (market resolved against you)

### Database Schema

The `positions` table stores:

```sql
- current_position: Current number of tokens held
- total_bought: Total tokens bought
- total_sold: Total tokens sold
- avg_buy_price: Average purchase price
- total_buy_value: Total amount spent
- total_sell_value: Total amount received from sales
- realized_pnl: Profit/Loss from closed trades
- status: active, closed, settled_win, settled_loss
```

## Using Position Tracking

### View Active Positions

```bash
python3 view_positions.py
```

Shows only positions with current holdings > 0.

### View All Positions (Including Closed)

```bash
python3 view_positions.py --all
```

Shows all positions including closed and settled ones.

### View Summary Only

```bash
python3 view_positions.py --summary
# or
python3 view_positions.py --all --summary
```

Shows statistics without individual position details.

### Filter by Address

```bash
python3 view_positions.py --address 0x0f37Cb80DEe49D55B5F6d9E595D52591D6371410
```

## Backfilling Historical Data

If you want to rebuild positions from historical trades:

```bash
python3 backfill_positions.py
```

This will:
1. Clear existing positions
2. Replay all trades in chronological order
3. Rebuild all position data
4. Detect settlements from historical data

## Position Status Types

- **🟢 active**: Position is open (current_position > 0)
- **⚪ closed**: Position was fully closed through trading (current_position = 0)
- **🟩 settled_win**: Market settled, position won (sold at ~$1.00)
- **🟥 settled_loss**: Market settled, position lost (sold at ~$0.00)

## Settlement Detection Logic

The system automatically detects when a sell transaction is a settlement:

```python
# Winning settlement
if sell_price >= 0.95:
    status = 'settled_win'
    settlement_price = 1.00

# Losing settlement
if sell_price <= 0.05:
    status = 'settled_loss'
    settlement_price = 0.00
```

## Example Output

```
================================================================================
                               📊 ACTIVE POSITIONS
================================================================================

📈 Summary:
   Total Positions: 3
   🟢 Active: 3
   ⚪ Closed: 0
   🟩 Settled (Win): 1
   🟥 Settled (Loss): 4
   💰 Total Realized P&L: $-2.00

🟢 Position: ACTIVE
================================================================================
📊 Market: Will Salvador Nasralla win the 2025 Honduras presidential election?
   Outcome: No
   Category: Politics

💼 Position Details:
   Current Position: 193.0211 tokens
   Total Bought: 193.0211 tokens
   Total Sold: 0.0000 tokens

💰 Financial Summary:
   Average Buy Price: $0.3600
   Total Buy Value: $69.49
   Total Sell Value: $0.00
   Realized P&L: $0.00

⏱️  Timeline:
   First Trade: 2025-11-30 09:04:12
   Last Trade: 2025-11-30 09:05:56
================================================================================
```

## Monitoring Logs

When the monitor detects a trade, it now also logs position updates:

```
📊 TRADE DETECTED | Block: 79,693,725
   ...
   💼 Position Update: 193.02 tokens (Avg: $0.360, PnL: $0.00)
```

For settlements:

```
🎯 SETTLEMENT DETECTED: WIN - Price: $0.980
📊 Position settled (WIN): 0x6da962ecc... at $1.0
```

## Notes

- Position tracking starts from when you first run the updated monitor
- Use `backfill_positions.py` to rebuild from historical data
- Negative positions can occur if you sell before buying (system started mid-cycle)
- Settlement detection is automatic based on sale price thresholds
