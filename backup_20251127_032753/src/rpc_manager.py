"""
RPC Manager with multiple endpoints and automatic failover
"""
import logging
import time
from typing import List, Optional
from web3 import Web3
from web3.exceptions import Web3Exception
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)


class RPCManager:
    """Manages multiple RPC endpoints with automatic failover"""

    def __init__(self, rpc_endpoints: List[str], max_retry: int = 3, retry_delay: int = 5):
        """
        Initialize RPC Manager

        Args:
            rpc_endpoints: List of RPC endpoint URLs
            max_retry: Maximum number of retries per endpoint
            retry_delay: Delay between retries in seconds
        """
        self.rpc_endpoints = rpc_endpoints
        self.max_retry = max_retry
        self.retry_delay = retry_delay
        self.current_index = 0
        self.w3: Optional[Web3] = None
        self._connect()

    def _connect(self) -> bool:
        """
        Connect to an RPC endpoint

        Returns:
            bool: True if connection successful
        """
        for _ in range(len(self.rpc_endpoints)):
            endpoint = self.rpc_endpoints[self.current_index]
            try:
                logger.info(f"Attempting to connect to RPC: {endpoint}")
                self.w3 = Web3(Web3.HTTPProvider(endpoint, request_kwargs={'timeout': 30}))

                # Inject POA middleware for Polygon compatibility
                self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

                # Test connection
                if self.w3.is_connected():
                    chain_id = self.w3.eth.chain_id
                    logger.info(f"✓ Connected to RPC: {endpoint} (Chain ID: {chain_id})")
                    return True
                else:
                    logger.warning(f"✗ Failed to connect to RPC: {endpoint}")
            except Exception as e:
                logger.warning(f"✗ Error connecting to RPC {endpoint}: {str(e)}")

            # Rotate to next endpoint
            self._rotate_endpoint()

        logger.error("Failed to connect to any RPC endpoint")
        return False

    def _rotate_endpoint(self):
        """Rotate to the next RPC endpoint"""
        self.current_index = (self.current_index + 1) % len(self.rpc_endpoints)
        logger.info(f"Rotating to RPC endpoint {self.current_index + 1}/{len(self.rpc_endpoints)}")

    def execute_with_retry(self, func, *args, **kwargs):
        """
        Execute a function with retry logic and automatic failover

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Result of the function execution
        """
        last_exception = None

        for attempt in range(self.max_retry):
            try:
                if not self.w3 or not self.w3.is_connected():
                    logger.warning("Connection lost, attempting to reconnect...")
                    if not self._connect():
                        raise ConnectionError("Failed to reconnect to RPC")

                result = func(*args, **kwargs)
                return result

            except (Web3Exception, ConnectionError, Exception) as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1}/{self.max_retry} failed: {str(e)}")

                if attempt < self.max_retry - 1:
                    # Try rotating to next endpoint
                    self._rotate_endpoint()
                    self._connect()
                    time.sleep(self.retry_delay)

        # All retries exhausted
        logger.error(f"All retry attempts exhausted. Last error: {str(last_exception)}")
        raise last_exception

    def get_web3(self) -> Web3:
        """
        Get the current Web3 instance

        Returns:
            Web3: Current Web3 instance
        """
        if not self.w3 or not self.w3.is_connected():
            self._connect()
        return self.w3

    def get_latest_block(self) -> int:
        """
        Get the latest block number with retry

        Returns:
            int: Latest block number
        """
        return self.execute_with_retry(lambda: self.w3.eth.block_number)

    def get_block(self, block_number: int):
        """
        Get block by number with retry

        Args:
            block_number: Block number to fetch

        Returns:
            Block data
        """
        return self.execute_with_retry(lambda: self.w3.eth.get_block(block_number, full_transactions=True))

    def get_transaction_receipt(self, tx_hash: str):
        """
        Get transaction receipt with retry

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction receipt
        """
        return self.execute_with_retry(lambda: self.w3.eth.get_transaction_receipt(tx_hash))
