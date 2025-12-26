#!/usr/bin/env python3
"""
Polymarket Copy Trading System - Optimized Version
Main entry point

Traffic Routing (configurable via PROXY_MODE env var):
- PROXY_MODE=split (default): RPC direct, Copy trading via Clash
- PROXY_MODE=all: All traffic via Clash proxy
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

# Check proxy mode: "split" (default) or "all"
PROXY_MODE = os.environ.get("PROXY_MODE", "split").lower()

# For split mode, clear proxy env vars so RPC goes direct
# For all mode, we'll set proxy after Clash is confirmed running
if PROXY_MODE == "split":
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        if key in os.environ:
            del os.environ[key]

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from rpc_manager import RPCManager
from database import DatabaseManager
from monitor import PolymarketMonitor
from clash_proxy_manager import ClashProxyManager, get_proxy_manager


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


def find_optimal_region(proxy_manager, logger) -> str:
    """
    Test all regions and find the one with lowest latency

    Args:
        proxy_manager: ClashProxyManager instance
        logger: Logger instance

    Returns:
        str: Best region name
    """
    import time
    import requests

    results = []
    test_url = proxy_manager.POLYMARKET_TEST_URL

    logger.info("Testing all regions for optimal latency...")

    for region in proxy_manager.REGIONS:
        try:
            if proxy_manager.switch_to_region(region):
                # Test 3 times and average
                times = []
                for _ in range(3):
                    start = time.time()
                    try:
                        resp = requests.get(
                            test_url,
                            proxies=proxy_manager.get_proxies_for_requests(),
                            timeout=10
                        )
                        if resp.status_code == 200:
                            times.append(time.time() - start)
                    except:
                        times.append(10.0)  # Penalty for failed requests

                avg_time = sum(times) / len(times) if times else 10.0
                results.append((region, avg_time))
                logger.info(f"  {region}: {avg_time*1000:.0f}ms avg")
            else:
                logger.warning(f"  {region}: FAILED to connect")
                results.append((region, 999.0))
        except Exception as e:
            logger.warning(f"  {region}: ERROR - {e}")
            results.append((region, 999.0))

    # Sort by latency and pick best
    results.sort(key=lambda x: x[1])
    best_region = results[0][0] if results else proxy_manager.REGIONS[0]

    logger.info(f"Optimal region: {best_region} ({results[0][1]*1000:.0f}ms)")
    return best_region


def init_clash_proxy(config: dict, logger) -> bool:
    """
    Initialize Clash proxy if copy trading is enabled or PROXY_MODE=all

    Args:
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        bool: True if proxy is ready (or not needed)
    """
    copy_config = config.get('copy_trading', {})
    need_proxy = copy_config.get('enabled', False) or PROXY_MODE == "all"

    if not need_proxy:
        logger.info("Copy trading disabled and PROXY_MODE=split, skipping proxy setup")
        return True

    logger.info("=" * 60)
    logger.info(f"INITIALIZING CLASH PROXY (MODE: {PROXY_MODE.upper()})")
    logger.info("=" * 60)

    try:
        proxy_manager = get_proxy_manager()

        # Start Clash if not running
        if not proxy_manager.is_clash_running():
            logger.info("Starting Clash...")
            if not proxy_manager.start_clash():
                logger.error("Failed to start Clash")
                return False

        # Find optimal region
        best_region = find_optimal_region(proxy_manager, logger)

        # Switch to optimal region
        logger.info(f"Switching to optimal region: {best_region}")
        if not proxy_manager.switch_to_region(best_region):
            # Fallback: use ensure_connectivity to find any working region
            logger.warning(f"Optimal region {best_region} failed, trying others...")
            if not proxy_manager.ensure_connectivity():
                logger.error("Cannot establish proxy connectivity")
                return False

        current = proxy_manager.get_current_proxy()
        logger.info(f"Proxy ready: {current}")

        # For PROXY_MODE=all, set env proxy for all traffic
        if PROXY_MODE == "all":
            proxy_manager.set_env_proxy()
            logger.info("All traffic will be routed through Clash proxy")

        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Proxy initialization error: {e}")
        return False


def main():
    """Main entry point"""
    mode_desc = "All via Clash" if PROXY_MODE == "all" else "RPC Direct, API via Clash"
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     POLYMARKET COPY TRADING SYSTEM - OPTIMIZED           ║
║     Using eth_getLogs with 3-hour rolling window        ║
║                                                           ║
║     Traffic: {mode_desc:<40}║
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

    # Initialize Clash proxy if copy trading is enabled
    copy_trading_enabled = config.get('copy_trading', {}).get('enabled', False)
    if copy_trading_enabled:
        proxy_ready = init_clash_proxy(config, logger)
        if not proxy_ready:
            logger.warning("Proxy not available, disabling copy trading")
            config['copy_trading']['enabled'] = False

    # Initialize components
    try:
        # For split mode, ensure RPC goes direct (no proxy)
        if PROXY_MODE == "split":
            for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
                if key in os.environ:
                    del os.environ[key]

        # RPC Manager
        conn_type = "via Clash" if PROXY_MODE == "all" else "DIRECT"
        logger.info(f"Initializing RPC Manager ({conn_type} connection)...")
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
        # Merge monitoring config with copy_trading config
        monitor_config = config['monitoring'].copy()
        monitor_config['copy_trading'] = config.get('copy_trading', {})
        monitor = PolymarketMonitor(
            rpc_manager=rpc_manager,
            database_manager=db_manager,
            monitored_addresses=config['monitored_addresses'],
            config=monitor_config
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
