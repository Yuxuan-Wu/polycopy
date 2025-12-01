#!/usr/bin/env python3
"""
Test the integrated backfill mechanism
"""
import sys
import logging
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

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


def main():
    """Test backfill mechanism"""
    print("=" * 80)
    print("TESTING INTEGRATED BACKFILL MECHANISM")
    print("=" * 80)

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize managers
    logger.info("Initializing RPC Manager...")
    rpc_manager = RPCManager(
        rpc_endpoints=config['rpc_endpoints'],
        max_retry=config['monitoring'].get('max_retry', 3),
        retry_delay=config['monitoring'].get('retry_delay', 5)
    )

    logger.info("Initializing Database Manager...")
    db_manager = DatabaseManager(
        db_path=config['database']['path'],
        csv_path=config['csv']['path'],
        auto_export=False  # Disable CSV export for testing
    )

    logger.info("Initializing Polymarket Monitor...")
    monitor = PolymarketMonitor(
        rpc_manager=rpc_manager,
        database_manager=db_manager,
        monitored_addresses=config['monitored_addresses'],
        config=config['monitoring']
    )

    # Test backfill
    logger.info("\nStarting backfill test...\n")
    try:
        stats = monitor.backfill_incomplete_positions()

        print("\n" + "=" * 80)
        print("BACKFILL TEST RESULTS")
        print("=" * 80)
        print(f"Total incomplete positions: {stats['total']}")
        print(f"Successfully backfilled: {stats['backfilled']}")
        print(f"Marked as incomplete (>7 days): {stats['marked_incomplete']}")
        print(f"Total trades found: {stats['trades_found']}")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Backfill test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
