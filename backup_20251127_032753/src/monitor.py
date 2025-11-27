"""
Transaction monitor for Polymarket trades
"""
import logging
import time
from datetime import datetime
from typing import List, Set, Dict, Optional
from web3 import Web3
from monitor_events import EventDecoder

logger = logging.getLogger(__name__)


class PolymarketMonitor:
    """Monitor Polymarket trades for specific addresses"""

    # Common Polymarket method signatures
    POLYMARKET_METHODS = {
        '0x96b5a755': 'fillOrder',           # Fill order
        '0x3f7a3e6f': 'fillOrders',          # Fill multiple orders
        '0x6d0d31a6': 'matchOrders',         # Match orders
        '0xf6f8e4f5': 'cancelOrder',         # Cancel order
        '0x8b7a4bca': 'cancelOrders',        # Cancel multiple orders
    }

    # Known Polymarket-related contracts
    POLYMARKET_CONTRACTS = {
        '0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e',  # CTF Exchange
        '0xc5d563a36ae78145c45a50134d48a1215220f80a',  # Neg Risk CTF Exchange
    }

    # Known router contracts that interact with Polymarket
    KNOWN_ROUTERS = {
        '0xb768891e3130f6df18214ac804d4db76c2c37730',  # Common router
    }

    def __init__(
        self,
        rpc_manager,
        database_manager,
        monitored_addresses: List[str],
        polymarket_contract: str,
        poll_interval: int = 12
    ):
        """
        Initialize Polymarket Monitor

        Args:
            rpc_manager: RPC Manager instance
            database_manager: Database Manager instance
            monitored_addresses: List of addresses to monitor
            polymarket_contract: Polymarket CTF Exchange contract address
            poll_interval: Polling interval in seconds
        """
        self.rpc_manager = rpc_manager
        self.db_manager = database_manager
        self.monitored_addresses: Set[str] = {addr.lower() for addr in monitored_addresses}
        self.polymarket_contract = polymarket_contract.lower()
        self.poll_interval = poll_interval
        self.w3 = rpc_manager.get_web3()

        # Initialize event decoder for NegRisk CTF Exchange
        neg_risk_exchange = '0xc5d563a36ae78145c45a50134d48a1215220f80a'
        self.event_decoder = EventDecoder(self.w3, neg_risk_exchange)

        # State
        self.last_block_processed: Optional[int] = None
        self.is_running = False

        logger.info(f"Monitor initialized for {len(self.monitored_addresses)} addresses")
        logger.info(f"Polymarket Contract: {self.polymarket_contract}")
        logger.info(f"Also monitoring Neg Risk CTF and routers")
        logger.info(f"Event decoder initialized for NegRisk CTF Exchange")

    def start(self, start_block: Optional[int] = None):
        """
        Start monitoring

        Args:
            start_block: Block number to start from (None = latest)
        """
        self.is_running = True

        # Determine starting block
        if start_block is None:
            db_last_block = self.db_manager.get_latest_block()
            if db_last_block:
                self.last_block_processed = db_last_block
                logger.info(f"Resuming from database block: {self.last_block_processed}")
            else:
                self.last_block_processed = self.rpc_manager.get_latest_block()
                logger.info(f"Starting from latest block: {self.last_block_processed}")
        else:
            self.last_block_processed = start_block
            logger.info(f"Starting from specified block: {self.last_block_processed}")

        logger.info("=" * 60)
        logger.info("🔍 POLYMARKET MONITOR STARTED")
        logger.info(f"Monitoring addresses: {list(self.monitored_addresses)}")
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info("=" * 60)

        self._monitor_loop()

    def stop(self):
        """Stop monitoring"""
        self.is_running = False
        logger.info("Monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop"""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.is_running:
            try:
                latest_block = self.rpc_manager.get_latest_block()

                # Process new blocks
                if latest_block > self.last_block_processed:
                    blocks_to_process = min(latest_block - self.last_block_processed, 10)  # Process max 10 blocks at a time

                    for block_num in range(self.last_block_processed + 1, self.last_block_processed + blocks_to_process + 1):
                        self._process_block(block_num)

                    self.last_block_processed += blocks_to_process

                    # Reset error counter on success
                    consecutive_errors = 0
                else:
                    # No new blocks, wait
                    time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                self.stop()
                break

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in monitor loop (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"Too many consecutive errors ({max_consecutive_errors}), stopping monitor")
                    self.stop()
                    break

                time.sleep(self.poll_interval * 2)  # Wait longer on error

    def _process_block(self, block_number: int):
        """
        Process a single block

        Args:
            block_number: Block number to process
        """
        try:
            block = self.rpc_manager.get_block(block_number)

            if not block or 'transactions' not in block:
                logger.debug(f"Block {block_number}: No transactions")
                return

            transactions = block['transactions']
            logger.debug(f"Processing block {block_number} with {len(transactions)} transactions")

            for tx in transactions:
                self._process_transaction(tx, block)

        except Exception as e:
            logger.error(f"Error processing block {block_number}: {e}")

    def _process_transaction(self, tx, block):
        """
        Process a single transaction

        Args:
            tx: Transaction data
            block: Block data
        """
        try:
            tx_from = tx.get('from', '').lower()
            tx_to = tx.get('to', '').lower() if tx.get('to') else ''
            tx_hash = tx['hash'].hex() if isinstance(tx['hash'], bytes) else str(tx['hash'])

            # Check if transaction involves monitored addresses and Polymarket ecosystem
            is_from_monitored = tx_from in self.monitored_addresses
            is_to_polymarket = tx_to in self.POLYMARKET_CONTRACTS
            is_to_router = tx_to in self.KNOWN_ROUTERS

            # Strategy 1: Direct transaction from monitored address to Polymarket
            if is_from_monitored and is_to_polymarket:
                self._record_trade(tx, block)
                return

            # Strategy 2: Transaction through router - check event logs
            if is_to_router or is_to_polymarket:
                if self._check_logs_for_monitored_address(tx_hash):
                    self._record_trade(tx, block)
                    return

            # Strategy 3: Check if monitored address appears in FROM field (even if going to router)
            if is_from_monitored and is_to_router:
                # Verify it's actually a Polymarket trade by checking logs
                if self._check_logs_for_polymarket_interaction(tx_hash):
                    self._record_trade(tx, block)
                    return

        except Exception as e:
            logger.error(f"Error processing transaction {tx.get('hash', 'unknown')}: {e}")

    def _check_logs_for_monitored_address(self, tx_hash: str) -> bool:
        """
        Check if transaction logs contain events involving monitored addresses

        Args:
            tx_hash: Transaction hash

        Returns:
            bool: True if monitored address found in logs
        """
        try:
            receipt = self.rpc_manager.get_transaction_receipt(tx_hash)
            if not receipt or 'logs' not in receipt:
                return False

            # Check each log for monitored addresses in topics or data
            for log in receipt['logs']:
                # Check if log is from Polymarket contracts
                log_address = log['address'].lower()
                if log_address not in self.POLYMARKET_CONTRACTS:
                    continue

                # Check topics (indexed parameters)
                for topic in log.get('topics', []):
                    topic_hex = topic.hex() if isinstance(topic, bytes) else str(topic)
                    # Check if any monitored address appears in topic
                    for addr in self.monitored_addresses:
                        # Remove 0x prefix and pad to 64 chars (32 bytes)
                        addr_padded = addr[2:].lower().zfill(64)
                        if addr_padded in topic_hex.lower():
                            logger.debug(f"Found monitored address {addr} in log topic")
                            return True

                # Check data field
                data_hex = log.get('data', '').hex() if isinstance(log.get('data'), bytes) else str(log.get('data', ''))
                for addr in self.monitored_addresses:
                    addr_clean = addr[2:].lower()
                    if addr_clean in data_hex.lower():
                        logger.debug(f"Found monitored address {addr} in log data")
                        return True

            return False

        except Exception as e:
            logger.debug(f"Error checking logs for {tx_hash}: {e}")
            return False

    def _check_logs_for_polymarket_interaction(self, tx_hash: str) -> bool:
        """
        Check if transaction logs indicate Polymarket interaction

        Args:
            tx_hash: Transaction hash

        Returns:
            bool: True if Polymarket interaction detected
        """
        try:
            receipt = self.rpc_manager.get_transaction_receipt(tx_hash)
            if not receipt or 'logs' not in receipt:
                return False

            # Check if any log is from Polymarket contracts
            for log in receipt['logs']:
                log_address = log['address'].lower()
                if log_address in self.POLYMARKET_CONTRACTS:
                    return True

            return False

        except Exception as e:
            logger.debug(f"Error checking Polymarket interaction for {tx_hash}: {e}")
            return False

    def _record_trade(self, tx, block):
        """
        Record a Polymarket trade by decoding events from receipt

        Args:
            tx: Transaction data
            block: Block data
        """
        try:
            tx_hash = tx['hash'].hex() if isinstance(tx['hash'], bytes) else str(tx['hash'])

            # Get transaction receipt
            receipt = self.rpc_manager.get_transaction_receipt(tx_hash)
            if not receipt:
                logger.warning(f"No receipt for transaction {tx_hash}")
                return

            # Decode OrderFilled events from receipt
            decoded_trades = self.event_decoder.decode_trade_events(receipt)

            if not decoded_trades:
                logger.debug(f"No OrderFilled events found in transaction {tx_hash}")
                return

            # Calculate capture delay
            trade_timestamp = block['timestamp']
            current_timestamp = int(datetime.utcnow().timestamp())
            capture_delay_seconds = current_timestamp - trade_timestamp

            # Process each decoded trade event
            for decoded in decoded_trades:
                # Check if this trade involves a monitored address
                if decoded['maker'] not in self.monitored_addresses and decoded['taker'] not in self.monitored_addresses:
                    continue

                # Determine the relevant address (prefer maker if monitored)
                from_address = decoded['maker'] if decoded['maker'] in self.monitored_addresses else decoded['taker']

                # Prepare trade data
                trade_data = {
                    'tx_hash': tx_hash,
                    'block_number': block['number'],
                    'timestamp': block['timestamp'],
                    'from_address': from_address,
                    'to_address': tx['to'].lower() if tx.get('to') else '',
                    'method': decoded['side'],  # Use side (buy/sell) as method
                    'token_id': decoded['token_id'],
                    'amount': decoded['amount'],
                    'price': decoded['price'],
                    'side': decoded['side'],
                    'gas_used': str(receipt.get('gasUsed', 0)),
                    'gas_price': str(tx.get('gasPrice', 0)),
                    'value': str(tx.get('value', 0)),
                    'status': 'success' if receipt.get('status') == 1 else 'failed',
                    'capture_delay_seconds': capture_delay_seconds
                }

                # Save to database
                self.db_manager.insert_trade(trade_data)

                # Log the trade
                logger.info(f"📊 TRADE DETECTED | Block: {block['number']} | "
                           f"From: {from_address[:10]}... | "
                           f"Side: {decoded['side']} | "
                           f"Price: ${decoded['price']} | "
                           f"Status: {trade_data['status']}")

        except Exception as e:
            logger.error(f"Error recording trade: {e}")

    def _determine_trade_side(self, input_data: str) -> str:
        """
        Determine if trade is buy or sell (simplified)

        Args:
            input_data: Transaction input data (HexBytes or str)

        Returns:
            str: 'buy', 'sell', or 'unknown'
        """
        # This is a simplified version
        # Real implementation would need ABI decoding
        try:
            # Convert HexBytes to hex string
            if hasattr(input_data, 'hex'):
                input_hex = input_data.hex()
            else:
                input_hex = str(input_data)

            if len(input_hex) > 10:
                # Check for patterns in input data
                # This is placeholder logic
                return 'unknown'
        except:
            pass
        return 'unknown'

    def _extract_token_id(self, input_data: str) -> Optional[str]:
        """
        Extract token ID from transaction input

        Args:
            input_data: Transaction input data (HexBytes or str)

        Returns:
            Optional[str]: Token ID or None
        """
        try:
            # Convert HexBytes to hex string
            if hasattr(input_data, 'hex'):
                input_hex = input_data.hex()
            else:
                input_hex = str(input_data)

            # Simplified extraction - real implementation needs ABI decoding
            if len(input_hex) > 74:
                # Token ID is typically in the first parameter after method signature
                token_id_hex = input_hex[10:74]
                return f"0x{token_id_hex}"
        except:
            pass
        return None

    def _extract_amount(self, input_data: str) -> Optional[str]:
        """
        Extract trade amount from transaction input

        Args:
            input_data: Transaction input data (HexBytes or str)

        Returns:
            Optional[str]: Amount or None
        """
        try:
            # Convert HexBytes to hex string
            if hasattr(input_data, 'hex'):
                input_hex = input_data.hex()
            else:
                input_hex = str(input_data)

            # Simplified extraction
            if len(input_hex) > 138:
                amount_hex = input_hex[74:138]
                amount = int(amount_hex, 16)
                return str(amount)
        except:
            pass
        return None

    def _extract_price(self, input_data: str) -> Optional[str]:
        """
        Extract price from transaction input

        Args:
            input_data: Transaction input data (HexBytes or str)

        Returns:
            Optional[str]: Price or None
        """
        try:
            # Convert HexBytes to hex string
            if hasattr(input_data, 'hex'):
                input_hex = input_data.hex()
            else:
                input_hex = str(input_data)

            # Simplified extraction
            if len(input_hex) > 202:
                price_hex = input_hex[138:202]
                price = int(price_hex, 16)
                return str(price)
        except:
            pass
        return None

    def get_stats(self) -> Dict:
        """
        Get monitoring statistics

        Returns:
            Dict: Statistics
        """
        return {
            'is_running': self.is_running,
            'last_block_processed': self.last_block_processed,
            'total_trades': self.db_manager.get_trade_count(),
            'monitored_addresses': list(self.monitored_addresses)
        }
