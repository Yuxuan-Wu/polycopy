#!/usr/bin/env python3
"""
Metadata Backfill Script
Fetches and stores market metadata for all trades in database
"""
import sys
import logging
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from metadata_manager import MetadataManager
from gamma_client import GammaClient


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Backfill market metadata from Polymarket Gamma API'
    )
    parser.add_argument(
        '--db',
        default='data/trades.db',
        help='Path to SQLite database (default: data/trades.db)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force refresh all metadata, even if already exists'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show metadata coverage statistics and exit'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     POLYMARKET METADATA BACKFILL TOOL                    ║
║     Fetch market data from Gamma API                     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    try:
        # Initialize managers
        logger.info("Initializing Gamma client and metadata manager...")
        gamma_client = GammaClient()
        metadata_manager = MetadataManager(args.db, gamma_client)

        # Show stats if requested
        if args.stats:
            logger.info("Fetching metadata coverage statistics...")
            stats = metadata_manager.get_metadata_stats()

            print("\n" + "=" * 60)
            print("METADATA COVERAGE STATISTICS")
            print("=" * 60)
            print(f"Total trades:              {stats.get('total_trades', 0):,}")
            print(f"Unique token IDs:          {stats.get('unique_tokens', 0):,}")
            print(f"Token IDs with metadata:   {stats.get('tokens_with_metadata', 0):,}")
            print(f"Total markets:             {stats.get('total_markets', 0):,}")
            print(f"Coverage:                  {stats.get('coverage_percent', 0):.2f}%")
            print("=" * 60 + "\n")

            if stats.get('coverage_percent', 0) < 100:
                missing = stats.get('unique_tokens', 0) - stats.get('tokens_with_metadata', 0)
                print(f"💡 {missing} token IDs are missing metadata")
                print("   Run without --stats flag to backfill missing data\n")
            else:
                print("✅ All token IDs have metadata!\n")

            gamma_client.close()
            return

        # Run backfill
        logger.info(f"Starting metadata backfill (force_refresh={args.force})...")
        stats = metadata_manager.backfill_metadata(force_refresh=args.force)

        # Show final stats
        final_stats = metadata_manager.get_metadata_stats()

        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print(f"Total trades:              {final_stats.get('total_trades', 0):,}")
        print(f"Unique token IDs:          {final_stats.get('unique_tokens', 0):,}")
        print(f"Token IDs with metadata:   {final_stats.get('tokens_with_metadata', 0):,}")
        print(f"Total markets:             {final_stats.get('total_markets', 0):,}")
        print(f"Coverage:                  {final_stats.get('coverage_percent', 0):.2f}%")
        print("=" * 60 + "\n")

        if final_stats.get('coverage_percent', 0) >= 100:
            print("✅ Backfill complete! All token IDs now have metadata.\n")
        else:
            missing = final_stats.get('unique_tokens', 0) - final_stats.get('tokens_with_metadata', 0)
            print(f"⚠️  {missing} token IDs still missing metadata (may not exist in Gamma API)\n")

        # Close client
        gamma_client.close()

    except KeyboardInterrupt:
        logger.info("\nBackfill interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
