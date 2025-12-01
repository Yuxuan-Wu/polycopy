#!/usr/bin/env python3
"""
Polymarket Copy Trading System - Optimized Version
Main entry point
"""
import sys
import logging
import signal
import yaml
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from rpc_manager import RPCManager
from database import DatabaseManager
from monitor import PolymarketMonitor


def setup_logging(config: dict):
    """
    Setup logging configuration

    Args:
        config: Configuration dictionary
    """
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_file = log_config.get('file', 'logs/polycopy.log')

    # Create logs directory
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_config(config_path: str = 'config.yaml') -> dict:
    """
    Load configuration from YAML file

    Args:
        config_path: Path to configuration file

    Returns:
        dict: Configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)


def validate_config(config: dict) -> bool:
    """
    Validate configuration

    Args:
        config: Configuration dictionary

    Returns:
        bool: True if valid
    """
    errors = []

    # Check monitored addresses
    addresses = config.get('monitored_addresses', [])
    if not addresses or not any(addr != "0x0000000000000000000000000000000000000000" for addr in addresses):
        errors.append("⚠️  No valid monitored addresses configured in config.yaml")
        errors.append("   Please update 'monitored_addresses' with real Polygon addresses")

    # Check RPC endpoints
    if not config.get('rpc_endpoints'):
        errors.append("⚠️  No RPC endpoints configured")

    # Check Polymarket contracts (should be a list with 2 contracts)
    if not config.get('polymarket_contracts'):
        errors.append("⚠️  Polymarket contracts not configured")
        errors.append("   Need both CTF Exchange and Neg Risk CTF Exchange")

    # Check if Infura API key is set when using Infura
    if 'infura' in [e.lower() for e in config.get('rpc_endpoints', [])]:
        if not os.getenv('INFURA_API_KEY'):
            errors.append("⚠️  Infura endpoint configured but INFURA_API_KEY not found in .env file")

    if errors:
        print("\n" + "=" * 60)
        print("CONFIGURATION ERRORS:")
        print("=" * 60)
        for error in errors:
            print(error)
        print("=" * 60 + "\n")
        return False

    return True


def main():
    """Main entry point"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     POLYMARKET COPY TRADING SYSTEM - OPTIMIZED           ║
║     Using eth_getLogs with 3-hour rolling window        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    # Load configuration
    config = load_config()

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)

    # Validate configuration
    if not validate_config(config):
        logger.error("Configuration validation failed. Please check config.yaml")
        sys.exit(1)

    logger.info("Configuration loaded and validated")

    # Initialize components
    try:
        # RPC Manager
        logger.info("Initializing RPC Manager...")
        rpc_manager = RPCManager(
            rpc_endpoints=config['rpc_endpoints'],
            max_retry=config['monitoring'].get('max_retry', 3),
            retry_delay=config['monitoring'].get('retry_delay', 5)
        )

        # Database Manager
        logger.info("Initializing Database Manager...")
        db_manager = DatabaseManager(
            db_path=config['database']['path'],
            csv_path=config['csv']['path'],
            auto_export=config['csv'].get('auto_export', True)
        )

        # Monitor (new initialization with config dict)
        logger.info("Initializing Polymarket Monitor...")
        monitor = PolymarketMonitor(
            rpc_manager=rpc_manager,
            database_manager=db_manager,
            monitored_addresses=config['monitored_addresses'],
            config=config['monitoring']  # Pass entire monitoring config
        )

        # Setup signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal...")
            monitor.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Backfill incomplete positions (if enabled)
        backfill_config = config.get('backfill', {})
        if backfill_config.get('enabled', True):
            logger.info("Checking for incomplete positions...")
            try:
                stats = monitor.backfill_incomplete_positions()

                if stats['total'] > 0:
                    logger.info(f"Backfill summary: {stats['backfilled']} complete, "
                              f"{stats['marked_incomplete']} incomplete (>7 days old)")
            except Exception as e:
                logger.error(f"Error during backfill: {e}")
                logger.warning("Continuing with monitoring despite backfill error...")

        # Determine start block (ignored if rolling window is enabled)
        start_block_config = config['monitoring'].get('start_block', 'latest')
        start_block = None if start_block_config == 'latest' else int(start_block_config)

        # Start monitoring
        logger.info("Starting monitor...")
        monitor.start(start_block=start_block)

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
