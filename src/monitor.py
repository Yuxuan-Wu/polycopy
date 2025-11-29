"""
Transaction monitor for Polymarket trades - Optimized with eth_getLogs
"""
import logging
import time
from datetime import datetime, timedelta
from typing import List, Set, Dict, Optional
from web3 import Web3
from monitor_events import EventDecoder

logger = logging.getLogger(__name__)


class PolymarketMonitor:
    """Monitor Polymarket trades for specific addresses using eth_getLogs"""

    # OrderFilled event signature
    ORDER_FILLED_SIGNATURE = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"

    # Polymarket contract addresses (BOTH must be monitored!)
    POLYMARKET_CONTRACTS = [
        Web3.to_checksum_address("0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"),  # CTF Exchange
        Web3.to_checksum_address("0xc5d563a36ae78145c45a50134d48a1215220f80a"),  # Neg Risk CTF Exchange
    ]

    # Data validation thresholds
    MAX_REASONABLE_PRICE = 1.0  # Polymarket prices should be 0-1 (probability)
    MIN_REASONABLE_PRICE = 0.0001  # Minimum reasonable price
    MAX_REASONABLE_AMOUNT = 1000000.0  # Maximum reasonable token amount (after decimals)
    MIN_REASONABLE_AMOUNT = 0.000001  # Minimum reasonable token amount

    def __init__(
        self,
        rpc_manager,
        database_manager,
        monitored_addresses: List[str],
        config: Dict
    ):
        """
        Initialize Polymarket Monitor

        Args:
            rpc_manager: RPC Manager instance
            database_manager: Database Manager instance
            monitored_addresses: List of addresses to monitor
            config: Configuration dictionary
        """
        self.rpc_manager = rpc_manager
        self.db_manager = database_manager
        self.w3 = rpc_manager.get_web3()

        # Convert addresses to checksum format
        self.monitored_addresses = [
            Web3.to_checksum_address(addr) for addr in monitored_addresses
        ]

        # Configuration
        self.poll_interval = config.get('poll_interval', 60)
        self.batch_size = config.get('batch_size', 100)
        self.request_delay = config.get('request_delay', 0.1)
        self.use_rolling_window = config.get('use_rolling_window', True)
        self.window_hours = config.get('window_hours', 24)
        self.max_consecutive_errors = config.get('max_consecutive_errors', 5)

        # Initialize event decoder
        self.event_decoder = EventDecoder(self.w3, self.POLYMARKET_CONTRACTS[1])

        # State
        self.last_block_processed: Optional[int] = None
        self.start_block: Optional[int] = None
        self.is_running = False
        self.processed_txs: Set[str] = set()  # Track processed transactions to avoid duplicates

        logger.info("=" * 60)
        logger.info("🚀 Polymarket Monitor Initialized (Optimized)")
        logger.info("=" * 60)
        logger.info(f"Monitoring method: eth_getLogs")
        logger.info(f"Monitored addresses: {len(self.monitored_addresses)}")
        for i, addr in enumerate(self.monitored_addresses, 1):
            logger.info(f"  {i}. {addr}")
        logger.info(f"Polymarket contracts: {len(self.POLYMARKET_CONTRACTS)}")
        logger.info(f"  - CTF Exchange: {self.POLYMARKET_CONTRACTS[0]}")
        logger.info(f"  - Neg Risk CTF: {self.POLYMARKET_CONTRACTS[1]}")
        logger.info(f"Batch size: {self.batch_size} blocks")
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info(f"Request delay: {self.request_delay}s")
        logger.info(f"Rolling window: {self.use_rolling_window} ({self.window_hours}h)")
        logger.info("=" * 60)

    def start(self, start_block: Optional[int] = None):
        """
        Start monitoring

        Args:
            start_block: Block number to start from (None = calculate based on window)
        """
        self.is_running = True

        # Determine starting block
        current_block = self.rpc_manager.get_latest_block()

        if self.use_rolling_window:
            # Calculate block number from configured hours ago
            # Polygon: ~2 seconds per block = ~1,800 blocks per hour
            blocks_per_hour = 1800  # 3600 / 2
            blocks_to_subtract = blocks_per_hour * self.window_hours
            self.start_block = current_block - blocks_to_subtract
            self.last_block_processed = self.start_block - 1

            logger.info("=" * 60)
            logger.info(f"🕐 {self.window_hours}-HOUR ROLLING WINDOW MODE")
            logger.info("=" * 60)
            logger.info(f"Current block: {current_block}")
            logger.info(f"Window: {self.window_hours} hours ({blocks_to_subtract:,} blocks)")
            logger.info(f"Start block: {self.start_block:,}")
            logger.info(f"Blocks to sync: {current_block - self.start_block:,}")
            logger.info("=" * 60)
        else:
            if start_block:
                self.start_block = start_block
            else:
                # Try to resume from database
                db_last_block = self.db_manager.get_latest_block()
                if db_last_block:
                    self.start_block = db_last_block
                    logger.info(f"Resuming from database block: {self.start_block}")
                else:
                    self.start_block = current_block
                    logger.info(f"Starting from current block: {self.start_block}")

            self.last_block_processed = self.start_block - 1

        logger.info("🔍 POLYMARKET MONITOR STARTED")
        logger.info(f"Ready to process from block {self.last_block_processed + 1}")

        self._monitor_loop()

    def stop(self):
        """Stop monitoring"""
        self.is_running = False
        logger.info("Monitor stopped")

    def _validate_trade_data(self, trade_data: Dict) -> tuple[bool, List[str]]:
        """
        Validate trade data before saving

        Args:
            trade_data: Trade data dictionary

        Returns:
            Tuple of (is_valid, list of warnings)
        """
        warnings = []
        is_valid = True

        # Validate price
        try:
            price = float(trade_data.get('price', 0))
            if price > self.MAX_REASONABLE_PRICE:
                warnings.append(f"Unusually high price: {price:.6f} (max expected: {self.MAX_REASONABLE_PRICE})")
            elif price < self.MIN_REASONABLE_PRICE and price > 0:
                warnings.append(f"Unusually low price: {price:.6f} (min expected: {self.MIN_REASONABLE_PRICE})")
            elif price <= 0:
                warnings.append(f"Invalid price: {price}")
                is_valid = False
        except (ValueError, TypeError):
            warnings.append(f"Price is not a valid number: {trade_data.get('price')}")
            is_valid = False

        # Validate amount
        try:
            amount = float(trade_data.get('amount', 0))
            if amount > self.MAX_REASONABLE_AMOUNT:
                warnings.append(f"Unusually large amount: {amount:.6f} (max expected: {self.MAX_REASONABLE_AMOUNT})")
            elif amount < self.MIN_REASONABLE_AMOUNT and amount > 0:
                warnings.append(f"Unusually small amount: {amount:.6f} (min expected: {self.MIN_REASONABLE_AMOUNT})")
            elif amount <= 0:
                warnings.append(f"Invalid amount: {amount}")
                is_valid = False
        except (ValueError, TypeError):
            warnings.append(f"Amount is not a valid number: {trade_data.get('amount')}")
            is_valid = False

        # Validate required fields
        required_fields = ['token_id', 'side']
        for field in required_fields:
            if not trade_data.get(field):
                warnings.append(f"Missing required field: {field}")
                is_valid = False

        return is_valid, warnings

    def _monitor_loop(self):
        """Main monitoring loop using eth_getLogs"""
        consecutive_errors = 0

        while self.is_running:
            try:
                latest_block = self.rpc_manager.get_latest_block()

                # Check if there are new blocks to process
                if latest_block > self.last_block_processed:
                    blocks_behind = latest_block - self.last_block_processed

                    # Determine batch size (adaptive)
                    max_batch = self.rpc_manager.get_max_block_range()
                    batch_size = min(self.batch_size, max_batch, blocks_behind)

                    # Process one batch
                    from_block = self.last_block_processed + 1
                    to_block = min(from_block + batch_size - 1, latest_block)

                    logger.info(f"Processing blocks {from_block:,} to {to_block:,} ({to_block - from_block + 1} blocks, {blocks_behind} behind)")

                    # Query trades for all monitored addresses
                    trades_found = self._query_trades(from_block, to_block)

                    if trades_found > 0:
                        logger.info(f"✅ Found {trades_found} trades in this batch")

                    # Update last processed block
                    self.last_block_processed = to_block

                    # Reset error counter on success
                    consecutive_errors = 0

                    # If we're caught up, wait for next poll interval
                    if to_block >= latest_block:
                        logger.debug(f"Caught up to latest block. Waiting {self.poll_interval}s...")
                        time.sleep(self.poll_interval)

                else:
                    # Already caught up, wait for new blocks
                    time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                self.stop()
                break

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in monitor loop (attempt {consecutive_errors}/{self.max_consecutive_errors}): {e}")

                if consecutive_errors >= self.max_consecutive_errors:
                    logger.critical(f"Too many consecutive errors ({self.max_consecutive_errors}), stopping monitor")
                    self.stop()
                    break

                time.sleep(self.poll_interval * 2)  # Wait longer on error

    def _query_trades(self, from_block: int, to_block: int) -> int:
        """
        Query trades for all monitored addresses using eth_getLogs
        OPTIMIZED: Query all events once, filter on client-side (reduces from 6 to 2 RPC calls)

        Args:
            from_block: Starting block number
            to_block: Ending block number

        Returns:
            int: Number of trades found
        """
        trades_found = 0

        # Convert addresses to lowercase set for faster lookup
        monitored_addresses_lower = {addr.lower() for addr in self.monitored_addresses}

        # Query ALL maker events (for all addresses) - 1 RPC call instead of 3
        try:
            logs_maker = self.rpc_manager.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': self.POLYMARKET_CONTRACTS,
                'topics': [
                    self.ORDER_FILLED_SIGNATURE,  # topic[0]: OrderFilled event
                    None,                          # topic[1]: orderHash (any)
                    None                           # topic[2]: maker (any - filter client-side)
                ]
            })

            # Filter logs client-side for our monitored addresses
            for log in logs_maker:
                # Extract maker address from topic[2] (32 bytes, address is last 20 bytes)
                if len(log['topics']) >= 3:
                    maker_topic = log['topics'][2].hex()
                    maker_address = '0x' + maker_topic[-40:]  # Last 40 hex chars = 20 bytes

                    if maker_address.lower() in monitored_addresses_lower:
                        # Find the checksum version of the address
                        matched_address = next(addr for addr in self.monitored_addresses if addr.lower() == maker_address.lower())
                        if self._process_trade_log(log, matched_address, 'maker'):
                            trades_found += 1

            logger.debug(f"Maker query returned {len(logs_maker)} events, {trades_found} matched our addresses")

        except Exception as e:
            logger.warning(f"Error querying maker logs: {e}")

        # Delay between requests to avoid rate limiting
        time.sleep(self.request_delay)

        # Query ALL taker events (for all addresses) - 1 RPC call instead of 3
        try:
            logs_taker = self.rpc_manager.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': self.POLYMARKET_CONTRACTS,
                'topics': [
                    self.ORDER_FILLED_SIGNATURE,  # topic[0]: OrderFilled event
                    None,                          # topic[1]: orderHash (any)
                    None,                          # topic[2]: maker (any)
                    None                           # topic[3]: taker (any - filter client-side)
                ]
            })

            # Filter logs client-side for our monitored addresses
            for log in logs_taker:
                # Extract taker address from topic[3] (32 bytes, address is last 20 bytes)
                if len(log['topics']) >= 4:
                    taker_topic = log['topics'][3].hex()
                    taker_address = '0x' + taker_topic[-40:]  # Last 40 hex chars = 20 bytes

                    if taker_address.lower() in monitored_addresses_lower:
                        # Find the checksum version of the address
                        matched_address = next(addr for addr in self.monitored_addresses if addr.lower() == taker_address.lower())
                        if self._process_trade_log(log, matched_address, 'taker'):
                            trades_found += 1

            logger.debug(f"Taker query returned {len(logs_taker)} events, {trades_found} total matched")

        except Exception as e:
            logger.warning(f"Error querying taker logs: {e}")

        return trades_found

    def _process_trade_log(self, log, monitored_address: str, role: str) -> bool:
        """
        Process a single trade log event

        Args:
            log: Event log from eth_getLogs
            monitored_address: The monitored address involved
            role: 'maker' or 'taker'

        Returns:
            bool: True if trade was processed and saved, False if skipped (duplicate)
        """
        try:
            tx_hash = log['transactionHash'].hex()

            # Check if already processed (avoid duplicates)
            if tx_hash in self.processed_txs:
                logger.debug(f"Skipping duplicate tx: {tx_hash[:10]}...")
                return False

            # Get transaction details
            tx = self.rpc_manager.get_transaction(log['transactionHash'])
            receipt = self.rpc_manager.get_transaction_receipt(log['transactionHash'])

            # Decode the event
            try:
                trade_data = self.event_decoder.decode_order_filled(log)
            except Exception as e:
                logger.warning(f"Failed to decode event for {tx_hash[:10]}...: {e}")
                trade_data = {}

            # Validate trade data
            is_valid, validation_warnings = self._validate_trade_data(trade_data)
            if not is_valid:
                logger.error(f"Invalid trade data for {tx_hash[:10]}...: {', '.join(validation_warnings)}")
                logger.error(f"Trade data: {trade_data}")
                return False  # Skip invalid trades

            if validation_warnings:
                logger.warning(f"Trade data warnings for {tx_hash[:10]}...: {', '.join(validation_warnings)}")

            # Get block timestamp
            block = self.rpc_manager.get_block(log['blockNumber'])
            timestamp = block['timestamp']

            # Calculate capture delay
            current_time = int(time.time())
            capture_delay = current_time - timestamp

            # Prepare trade record
            trade_record = {
                'tx_hash': tx_hash,
                'block_number': log['blockNumber'],
                'timestamp': timestamp,
                'from_address': monitored_address,  # The monitored address
                'to_address': tx['to'],
                'method': trade_data.get('side', role),
                'token_id': trade_data.get('token_id', ''),
                'amount': trade_data.get('amount', ''),
                'price': trade_data.get('price', ''),
                'side': trade_data.get('side', role),
                'gas_used': str(receipt['gasUsed']),
                'gas_price': str(tx['gasPrice']),
                'value': str(tx['value']),
                'status': 'success' if receipt['status'] == 1 else 'failed',
                'capture_delay_seconds': capture_delay
            }

            # Save to database
            self.db_manager.insert_trade(trade_record)

            # Mark as processed
            self.processed_txs.add(tx_hash)

            # Log the trade with delay classification
            delay_emoji = ""
            delay_note = ""
            if capture_delay > 3600:  # > 1 hour (historical data)
                delay_emoji = "⏰"
                delay_note = f" ({capture_delay/3600:.1f}h - HISTORICAL DATA)"
            elif capture_delay > 300:  # > 5 minutes (delayed)
                delay_emoji = "⚠️"
                delay_note = f" ({capture_delay/60:.1f}m - DELAYED)"
            elif capture_delay > 60:  # > 1 minute (slow)
                delay_emoji = "⏱️"
                delay_note = f" ({capture_delay}s - SLOW)"
            else:  # < 1 minute (real-time)
                delay_emoji = "⚡"
                delay_note = f" ({capture_delay}s - REAL-TIME)"

            logger.info("=" * 80)
            logger.info(f"📊 TRADE DETECTED | Block: {log['blockNumber']:,}")
            logger.info(f"   Tx Hash: {tx_hash}")
            logger.info(f"   Address: {monitored_address[:10]}... ({role})")
            logger.info(f"   Side: {trade_data.get('side', 'unknown')}")
            logger.info(f"   Price: {trade_data.get('price', 'N/A')} USDC")
            logger.info(f"   Amount: {trade_data.get('amount', 'N/A')} tokens")
            logger.info(f"   Time: {datetime.fromtimestamp(timestamp)}")
            logger.info(f"   {delay_emoji} Capture delay: {capture_delay}s{delay_note}")
            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.error(f"Error processing trade log: {e}")
            return False
