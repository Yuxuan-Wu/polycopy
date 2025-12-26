#!/usr/bin/env python3
"""
Backfill incomplete positions by querying historical blockchain data.

This script:
1. Detects positions where total_sold > total_bought (incomplete data)
2. Queries blockchain history (up to 7 days back) to find missing trades
3. Updates positions with complete data
4. Marks positions as 'incomplete' if data cannot be found after 7 days
"""

import sys
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import sqlite3

# Add src to path
sys.path.insert(0, '/root/polycopy/src')

from rpc_manager import RPCManager
from database import DatabaseManager
from monitor import PolymarketMonitor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PositionBackfiller:
    """Backfill incomplete positions with historical blockchain data"""

    # Maximum lookback period
    MAX_LOOKBACK_DAYS = 7
    BLOCKS_PER_DAY = 43200  # Polygon: ~2 seconds per block

    def __init__(self, db_manager: DatabaseManager, rpc_manager: RPCManager, monitored_address: str, config: dict):
        self.db = db_manager
        self.rpc = rpc_manager
        self.monitored_address = monitored_address
        self.config = config
        self.monitor = PolymarketMonitor(rpc_manager, db_manager, monitored_addresses=[monitored_address], config=config.get('monitoring', {}))

    def detect_incomplete_positions(self) -> List[Dict]:
        """
        Detect positions that are incomplete (sold > bought without proper history)

        Returns:
            List of incomplete position dictionaries
        """
        try:
            conn = sqlite3.connect(self.db.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Find positions where sold > bought or bought = 0 with sells
            cursor.execute("""
                SELECT p.*,
                       (SELECT COUNT(*) FROM trades t
                        WHERE t.from_address = p.address
                        AND t.token_id = p.token_id) as trade_count,
                       (SELECT MIN(timestamp) FROM trades t
                        WHERE t.from_address = p.address
                        AND t.token_id = p.token_id) as first_trade_ts
                FROM positions p
                WHERE (p.total_sold > p.total_bought + 0.01)
                   OR (p.total_bought = 0 AND p.total_sold > 0)
                   AND (p.is_complete IS NULL OR p.is_complete = 0)
                ORDER BY p.updated_at DESC
            """)

            positions = [dict(row) for row in cursor.fetchall()]
            conn.close()

            logger.info(f"Found {len(positions)} incomplete positions")
            return positions

        except Exception as e:
            logger.error(f"Failed to detect incomplete positions: {e}")
            return []

    def backfill_position(self, position: Dict) -> Tuple[bool, int]:
        """
        Backfill a single position by querying historical blockchain data

        Args:
            position: Position dictionary from database

        Returns:
            (success: bool, trades_found: int)
        """
        address = position['address']
        token_id = position['token_id']
        first_trade_ts = position.get('first_trade_ts', int(time.time()))

        logger.info(f"Backfilling position: {address[:10]}.../{token_id[:16]}...")
        logger.info(f"  Current: bought={position['total_bought']:.2f}, sold={position['total_sold']:.2f}")

        # Calculate lookback range
        current_block = self.rpc.get_latest_block()
        first_trade_dt = datetime.fromtimestamp(first_trade_ts)
        lookback_start = first_trade_dt - timedelta(days=self.MAX_LOOKBACK_DAYS)
        lookback_start_ts = int(lookback_start.timestamp())

        # Estimate block number from timestamp
        # Use average block time of 2 seconds for Polygon
        blocks_to_lookback = int((first_trade_ts - lookback_start_ts) / 2)
        from_block = max(0, current_block - blocks_to_lookback)

        # Actually we want to search BEFORE first_trade
        # So calculate block at first_trade_ts, then go back 7 days
        current_ts = int(time.time())
        blocks_since_first_trade = int((current_ts - first_trade_ts) / 2)
        first_trade_block = current_block - blocks_since_first_trade
        from_block = max(0, first_trade_block - (self.MAX_LOOKBACK_DAYS * self.BLOCKS_PER_DAY))
        to_block = first_trade_block

        logger.info(f"  Searching blocks {from_block:,} to {to_block:,} ({to_block - from_block:,} blocks)")
        logger.info(f"  Time range: {lookback_start.strftime('%Y-%m-%d %H:%M')} to {first_trade_dt.strftime('%Y-%m-%d %H:%M')}")

        # Query trades in batches
        batch_size = 100
        total_trades_found = 0
        current_from = from_block

        while current_from < to_block:
            current_to = min(current_from + batch_size - 1, to_block)

            # Query this batch
            try:
                trades = self.monitor._query_trades(current_from, current_to)
                total_trades_found += trades

                if trades > 0:
                    logger.info(f"    Found {trades} trades in blocks {current_from:,}-{current_to:,}")

                current_from = current_to + 1
                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.warning(f"    Error querying blocks {current_from:,}-{current_to:,}: {e}")
                current_from = current_to + 1
                continue

        logger.info(f"  Backfill complete: found {total_trades_found} historical trades")

        # Mark position as backfill attempted
        self._mark_backfill_attempted(address, token_id, total_trades_found > 0)

        return (total_trades_found > 0, total_trades_found)

    def _mark_backfill_attempted(self, address: str, token_id: str, success: bool):
        """Mark a position as backfill attempted"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            # Update position
            cursor.execute("""
                UPDATE positions
                SET backfill_attempted = 1,
                    backfill_date = ?,
                    is_complete = ?
                WHERE address = ? AND token_id = ?
            """, (datetime.utcnow().isoformat(), 1 if success else 0, address, token_id))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Failed to mark backfill attempted: {e}")

    def add_backfill_columns(self):
        """Add backfill tracking columns to positions table if they don't exist"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            # Check if columns exist
            cursor.execute("PRAGMA table_info(positions)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'is_complete' not in columns:
                logger.info("Adding is_complete column to positions table")
                cursor.execute("""
                    ALTER TABLE positions
                    ADD COLUMN is_complete INTEGER DEFAULT NULL
                """)

            if 'backfill_attempted' not in columns:
                logger.info("Adding backfill_attempted column to positions table")
                cursor.execute("""
                    ALTER TABLE positions
                    ADD COLUMN backfill_attempted INTEGER DEFAULT 0
                """)

            if 'backfill_date' not in columns:
                logger.info("Adding backfill_date column to positions table")
                cursor.execute("""
                    ALTER TABLE positions
                    ADD COLUMN backfill_date TEXT DEFAULT NULL
                """)

            conn.commit()
            conn.close()
            logger.info("✓ Backfill columns ready")

        except Exception as e:
            logger.error(f"Failed to add backfill columns: {e}")

    def run(self, auto_confirm: bool = False):
        """Run the backfill process"""
        logger.info("="*80)
        logger.info("POSITION BACKFILL PROCESS STARTED")
        logger.info("="*80)

        # Add necessary columns
        self.add_backfill_columns()

        # Detect incomplete positions
        incomplete_positions = self.detect_incomplete_positions()

        if not incomplete_positions:
            logger.info("No incomplete positions found. All positions are complete!")
            return

        logger.info(f"\nFound {len(incomplete_positions)} incomplete positions to backfill\n")

        # Show summary
        print("\nIncomplete Positions Summary:")
        print("-" * 80)
        for idx, pos in enumerate(incomplete_positions[:10], 1):  # Show first 10
            print(f"{idx}. Token: {pos['token_id'][:16]}...")
            print(f"   Bought: {pos['total_bought']:.2f}, Sold: {pos['total_sold']:.2f}")
            print(f"   Gap: {pos['total_sold'] - pos['total_bought']:.2f} tokens")
        if len(incomplete_positions) > 10:
            print(f"... and {len(incomplete_positions) - 10} more")

        # Ask for confirmation
        if not auto_confirm:
            print("\nThis will query historical blockchain data going back up to 7 days.")
            print(f"Estimated time: {len(incomplete_positions) * 2} - {len(incomplete_positions) * 10} minutes")
            confirm = input("\nProceed with backfill? (yes/no): ").strip().lower()

            if confirm != 'yes':
                logger.info("Backfill cancelled by user")
                return

        # Backfill each position
        total_success = 0
        total_trades_found = 0

        for idx, position in enumerate(incomplete_positions, 1):
            logger.info(f"\n[{idx}/{len(incomplete_positions)}] Processing position...")

            success, trades_found = self.backfill_position(position)

            if success:
                total_success += 1
            total_trades_found += trades_found

            # Brief pause between positions
            if idx < len(incomplete_positions):
                time.sleep(2)

        logger.info("\n" + "="*80)
        logger.info("BACKFILL COMPLETE")
        logger.info("="*80)
        logger.info(f"Positions processed: {len(incomplete_positions)}")
        logger.info(f"Successfully backfilled: {total_success}")
        logger.info(f"Total trades found: {total_trades_found}")
        logger.info(f"Marked as incomplete: {len(incomplete_positions) - total_success}")
        logger.info("="*80)


def main():
    """Main entry point"""
    import yaml
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Get monitored address from config
    monitored_address = config['monitored_addresses'][0]

    # Initialize managers
    rpc_manager = RPCManager(
        rpc_endpoints=config['rpc_endpoints'],
        max_retry=config['monitoring'].get('max_retry', 3),
        retry_delay=config['monitoring'].get('retry_delay', 5)
    )
    db_manager = DatabaseManager(
        db_path=config['database']['path'],
        csv_path=config['csv']['path'],
        auto_export=config['csv'].get('auto_export', False)
    )

    # Create and run backfiller
    backfiller = PositionBackfiller(db_manager, rpc_manager, monitored_address, config)
    backfiller.run()


if __name__ == '__main__':
    main()
